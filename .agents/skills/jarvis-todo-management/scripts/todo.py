#!/usr/bin/env python3
"""todo.py — task ledger CLI for jarvis-todo-management.

Single source of truth: todo-data/todos.json (current state snapshot).
Every mutation is also appended to todo-data/events.jsonl (append-only log).
Design doc: docs/todo-management-redesign-2026-07-02.md (schema_version 2).

Data dir resolution order (same convention as other skills):
  1. TODO_DATA environment variable
  2. <git repo root>/todo-data (walk up from cwd looking for .git)
  3. <cwd>/todo-data
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

SCHEMA_VERSION = 2
# v1 -> v2 is additive (optional per-task "priority" object), so v1 ledgers load as-is.
SUPPORTED_SCHEMA_VERSIONS = (1, 2)
STATUSES = ("inbox", "todo", "in_progress", "done", "dropped")
SOURCE_TYPES = ("user", "session", "worklog", "giziroku", "research", "google-tasks")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def resolve_data_dir() -> Path:
    env = os.environ.get("TODO_DATA")
    if env:
        return Path(env).expanduser().resolve()
    cur = Path.cwd().resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / ".git").exists():
            return candidate / "todo-data"
    return cur / "todo-data"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Ledger:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.todos_path = data_dir / "todos.json"
        self.events_path = data_dir / "events.jsonl"
        self.data = self._load()

    def _load(self) -> dict:
        if self.todos_path.exists():
            with self.todos_path.open(encoding="utf-8") as f:
                data = json.load(f)
            if data.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS:
                sys.exit(
                    f"error: unsupported schema_version {data.get('schema_version')!r} "
                    f"(this CLI supports {SUPPORTED_SCHEMA_VERSIONS})"
                )
            data["schema_version"] = SCHEMA_VERSION  # upgrade on next save (additive change)
            return data
        return {"schema_version": SCHEMA_VERSION, "updated_at": now_iso(), "tasks": []}

    def save(self) -> None:
        self.data["updated_at"] = now_iso()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # atomic replace so a crash never leaves a truncated ledger
        fd, tmp = tempfile.mkstemp(dir=self.data_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(tmp, self.todos_path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def log_event(self, task_id: str, event: str, detail: dict) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        line = {"ts": now_iso(), "task_id": task_id, "event": event, "detail": detail}
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    def get(self, task_id: str) -> dict:
        for t in self.data["tasks"]:
            if t["id"] == task_id:
                return t
        sys.exit(f"error: task not found: {task_id}")

    def new_id(self) -> str:
        prefix = f"t-{date.today().strftime('%Y%m%d')}-"
        nums = [
            int(t["id"][len(prefix):])
            for t in self.data["tasks"]
            if t["id"].startswith(prefix) and t["id"][len(prefix):].isdigit()
        ]
        return f"{prefix}{max(nums, default=0) + 1:03d}"

    def new_task(self, args: argparse.Namespace, parent_id: str | None = None) -> dict:
        ts = now_iso()
        status = getattr(args, "status", None) or "todo"
        return {
            "id": self.new_id(),
            "project": args.project or "_unclassified",
            "title": args.title,
            "description": getattr(args, "description", None),
            "status": status,
            "estimate_min": getattr(args, "estimate", None),
            "parent_id": parent_id,
            "due": getattr(args, "due", None),
            "source": {
                "type": getattr(args, "source_type", None) or "user",
                "ref": getattr(args, "source_ref", None),
            },
            "created_at": ts,
            "updated_at": ts,
            "started_at": ts if status == "in_progress" else None,
            "completed_at": ts if status == "done" else None,
            "google": {"task_id": None, "synced_at": None, "dirty": True},
            "note": getattr(args, "note", None),
            "priority": None,
        }


def touch(task: dict, dirty: bool = True) -> None:
    task["updated_at"] = now_iso()
    if dirty:
        task["google"]["dirty"] = True


def set_status(ledger: Ledger, task: dict, status: str, note: str | None = None) -> None:
    old = task["status"]
    task["status"] = status
    if status == "in_progress" and not task["started_at"]:
        task["started_at"] = now_iso()
    if status == "done":
        task["completed_at"] = now_iso()
    if note:
        task["note"] = note
    touch(task)
    ledger.log_event(task["id"], "status_changed", {"from": old, "to": status, "note": note})


def maybe_complete_parent(ledger: Ledger, task: dict) -> str | None:
    """Auto-complete the parent when its last open subtask is done (fact recording)."""
    pid = task.get("parent_id")
    if not pid:
        return None
    siblings = [t for t in ledger.data["tasks"] if t.get("parent_id") == pid]
    if not all(t["status"] in ("done", "dropped") for t in siblings):
        return None
    parent = ledger.get(pid)
    if parent["status"] in ("done", "dropped"):
        return None
    set_status(ledger, parent, "done", note="all subtasks done (auto-completed)")
    return pid


def validate_due(value: str | None) -> str | None:
    if value is None:
        return None
    if not DATE_RE.match(value):
        sys.exit(f"error: invalid due date (expected YYYY-MM-DD): {value!r}")
    date.fromisoformat(value)
    return value


def priority_score(t: dict) -> int:
    """impact × urgency (0 when unprioritized). Deterministic ranking key."""
    p = t.get("priority")
    if not p:
        return 0
    return p["impact"] * p["urgency"]


def fmt_task(t: dict) -> str:
    est = f"{t['estimate_min']}m" if t.get("estimate_min") else "-"
    flags = []
    p = t.get("priority")
    if p:
        flags.append(f"prio I{p['impact']}×U{p['urgency']}={priority_score(t)}")
    if t.get("parent_id"):
        flags.append(f"sub of {t['parent_id']}")
    if t["google"]["dirty"]:
        flags.append("dirty")
    if t.get("due"):
        flags.append(f"due {t['due']}")
    suffix = f" [{', '.join(flags)}]" if flags else ""
    return f"{t['id']}  {t['status']:<11} {t['project']:<20} {est:>5}  {t['title']}{suffix}"


def cmd_add(ledger: Ledger, args: argparse.Namespace) -> None:
    validate_due(args.due)
    task = ledger.new_task(args)
    ledger.data["tasks"].append(task)
    ledger.log_event(task["id"], "created", {"source": task["source"], "status": task["status"], "title": task["title"]})
    ledger.save()
    print(fmt_task(task))


def cmd_split(ledger: Ledger, args: argparse.Namespace) -> None:
    parent = ledger.get(args.task_id)
    if parent["status"] in ("done", "dropped"):
        sys.exit(f"error: cannot split a {parent['status']} task")
    created = []
    for spec in args.sub:
        title, _, est = spec.partition("|")
        sub_args = argparse.Namespace(
            project=parent["project"], title=title.strip(),
            description=None, estimate=int(est) if est.strip() else None,
            due=parent.get("due"), status="todo",
            source_type=parent["source"]["type"], source_ref=parent["source"]["ref"],
            note=None,
        )
        task = ledger.new_task(sub_args, parent_id=parent["id"])
        ledger.data["tasks"].append(task)
        ledger.log_event(task["id"], "created", {"source": task["source"], "status": task["status"], "title": task["title"], "parent_id": parent["id"]})
        created.append(task)
    touch(parent)
    ledger.log_event(parent["id"], "split", {"subtasks": [t["id"] for t in created]})
    ledger.save()
    for t in created:
        print(fmt_task(t))


def cmd_start(ledger: Ledger, args: argparse.Namespace) -> None:
    task = ledger.get(args.task_id)
    set_status(ledger, task, "in_progress")
    ledger.save()
    print(fmt_task(task))


def cmd_done(ledger: Ledger, args: argparse.Namespace) -> None:
    task = ledger.get(args.task_id)
    set_status(ledger, task, "done", note=args.note)
    parent_done = maybe_complete_parent(ledger, task)
    ledger.save()
    print(fmt_task(task))
    if parent_done:
        print(f"parent auto-completed: {fmt_task(ledger.get(parent_done))}")


def cmd_drop(ledger: Ledger, args: argparse.Namespace) -> None:
    task = ledger.get(args.task_id)
    set_status(ledger, task, "dropped", note=args.reason)
    ledger.save()
    print(fmt_task(task))


def cmd_promote(ledger: Ledger, args: argparse.Namespace) -> None:
    task = ledger.get(args.task_id)
    if task["status"] != "inbox":
        sys.exit(f"error: promote is inbox-only (task is {task['status']})")
    if args.project:
        task["project"] = args.project
    if args.estimate is not None:
        task["estimate_min"] = args.estimate
    if args.due:
        task["due"] = validate_due(args.due)
    set_status(ledger, task, "todo")
    ledger.save()
    print(fmt_task(task))


def cmd_edit(ledger: Ledger, args: argparse.Namespace) -> None:
    task = ledger.get(args.task_id)
    changed = {}
    for field in ("title", "description", "project"):
        value = getattr(args, field)
        if value is not None:
            changed[field] = {"from": task[field], "to": value}
            task[field] = value
    if args.estimate is not None:
        changed["estimate_min"] = {"from": task["estimate_min"], "to": args.estimate}
        task["estimate_min"] = args.estimate
    if args.due is not None:
        changed["due"] = {"from": task["due"], "to": validate_due(args.due)}
        task["due"] = args.due
    if not changed:
        sys.exit("error: nothing to edit (pass --title/--description/--project/--estimate/--due)")
    touch(task)
    ledger.log_event(task["id"], "edited", changed)
    ledger.save()
    print(fmt_task(task))


def cmd_note(ledger: Ledger, args: argparse.Namespace) -> None:
    task = ledger.get(args.task_id)
    task["note"] = args.text
    touch(task, dirty=False)  # notes are internal context, not synced to Google
    ledger.log_event(task["id"], "note", {"text": args.text})
    ledger.save()
    print(fmt_task(task))


def cmd_prioritize(ledger: Ledger, args: argparse.Namespace) -> None:
    """Record an impact/urgency assessment (jarvis-todo-prioritizer writes via this only).

    Intent decision: the caller must have user-confirmed values before invoking
    ("スキルは提案、確定はユーザー" principle). rationale is required so the
    assessment stays auditable in events.jsonl.
    """
    task = ledger.get(args.task_id)
    if task["status"] in ("done", "dropped"):
        sys.exit(f"error: cannot prioritize a {task['status']} task")
    old = task.get("priority")
    task["priority"] = {
        "impact": args.impact,
        "urgency": args.urgency,
        "rationale": args.rationale,
        "assessed_at": now_iso(),
    }
    touch(task, dirty=False)  # internal ranking context; Google Tasks has no priority field
    ledger.log_event(task["id"], "prioritized", {"from": old, "to": task["priority"]})
    ledger.save()
    print(fmt_task(task))


def cmd_sync_mark(ledger: Ledger, args: argparse.Namespace) -> None:
    task = ledger.get(args.task_id)
    if args.google_task_id:
        task["google"]["task_id"] = args.google_task_id
    task["google"]["synced_at"] = now_iso()
    task["google"]["dirty"] = False
    task["updated_at"] = now_iso()
    ledger.log_event(task["id"], "synced", {"google_task_id": task["google"]["task_id"]})
    ledger.save()
    print(fmt_task(task))


def cmd_list(ledger: Ledger, args: argparse.Namespace) -> None:
    tasks = ledger.data["tasks"]
    if args.status:
        tasks = [t for t in tasks if t["status"] in args.status]
    elif not args.all:
        tasks = [t for t in tasks if t["status"] not in ("done", "dropped")]
    if args.project:
        tasks = [t for t in tasks if t["project"] == args.project]
    if args.dirty:
        tasks = [t for t in tasks if t["google"]["dirty"]]
    if args.sort == "priority":
        # prioritized first (score desc, urgency as tie-breaker), unprioritized keep input order
        tasks = sorted(
            tasks,
            key=lambda t: (
                -priority_score(t),
                -(t.get("priority") or {}).get("urgency", 0),
            ),
        )
    if args.json:
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
        return
    if not tasks:
        print("(no matching tasks)")
        return
    for t in tasks:
        print(fmt_task(t))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add", help="register a task")
    p.add_argument("--title", required=True)
    p.add_argument("--project", help="project id (jarvis-worklog projects.yaml vocabulary); default _unclassified")
    p.add_argument("--description")
    p.add_argument("--estimate", type=int, help="estimate in minutes (target granularity: 30-60)")
    p.add_argument("--due", help="YYYY-MM-DD")
    p.add_argument("--status", choices=("inbox", "todo", "in_progress", "done"), default="todo",
                   help="inbox for harvested candidates; done for retroactive fact recording")
    p.add_argument("--source-type", choices=SOURCE_TYPES, default="user")
    p.add_argument("--source-ref", help="path or reference explaining where this came from")
    p.add_argument("--parent", dest="parent_id", help="(rare) attach to an existing parent task")
    p.add_argument("--note")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("split", help="split a task into 30-60min subtasks")
    p.add_argument("task_id")
    p.add_argument("--sub", action="append", required=True, metavar="TITLE[|EST_MIN]",
                   help="repeatable; e.g. --sub 'write schema|30' --sub 'wire CLI|60'")
    p.set_defaults(func=cmd_split)

    p = sub.add_parser("start", help="mark in_progress (sets started_at)")
    p.add_argument("task_id")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("done", help="mark done (sets completed_at; may auto-complete parent)")
    p.add_argument("task_id")
    p.add_argument("--note")
    p.set_defaults(func=cmd_done)

    p = sub.add_parser("drop", help="drop instead of delete (reason required)")
    p.add_argument("task_id")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_drop)

    p = sub.add_parser("promote", help="inbox -> todo (user-confirmed commitment)")
    p.add_argument("task_id")
    p.add_argument("--project")
    p.add_argument("--estimate", type=int)
    p.add_argument("--due")
    p.set_defaults(func=cmd_promote)

    p = sub.add_parser("edit", help="edit fields")
    p.add_argument("task_id")
    p.add_argument("--title")
    p.add_argument("--description")
    p.add_argument("--project")
    p.add_argument("--estimate", type=int)
    p.add_argument("--due")
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("note", help="record context (goal/plan change) as a note event")
    p.add_argument("task_id")
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_note)

    p = sub.add_parser("prioritize", help="record impact/urgency assessment (user-confirmed; see jarvis-todo-prioritizer)")
    p.add_argument("task_id")
    p.add_argument("--impact", type=int, choices=range(1, 6), required=True, metavar="1-5",
                   help="project impact (5 = direct hit on success/income/trust)")
    p.add_argument("--urgency", type=int, choices=range(1, 6), required=True, metavar="1-5",
                   help="time pressure (5 = overdue / immediate)")
    p.add_argument("--rationale", required=True,
                   help="why these scores (evidence + user agreement summary)")
    p.set_defaults(func=cmd_prioritize)

    p = sub.add_parser("sync-mark", help="record a successful Google Tasks push (clears dirty)")
    p.add_argument("task_id")
    p.add_argument("--google-task-id")
    p.set_defaults(func=cmd_sync_mark)

    p = sub.add_parser("list", help="list tasks (default: open tasks only)")
    p.add_argument("--status", action="append", choices=STATUSES, help="repeatable")
    p.add_argument("--project")
    p.add_argument("--dirty", action="store_true", help="only tasks pending Google sync")
    p.add_argument("--all", action="store_true", help="include done/dropped")
    p.add_argument("--sort", choices=("priority",), help="priority: impact×urgency desc, unprioritized last")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    ledger = Ledger(resolve_data_dir())
    if getattr(args, "parent_id", None) and args.command == "add":
        ledger.get(args.parent_id)  # fail fast on unknown parent
        task = ledger.new_task(args, parent_id=args.parent_id)
        ledger.data["tasks"].append(task)
        ledger.log_event(task["id"], "created", {"source": task["source"], "status": task["status"], "title": task["title"], "parent_id": args.parent_id})
        ledger.save()
        print(fmt_task(task))
        return
    args.func(ledger, args)


if __name__ == "__main__":
    main()
