#!/usr/bin/env python3
"""Self-reporting pipeline for self-evolving skills.

このスクリプトは「子スキル」と「自分自身 (メタスキル)」の両方で使う薄いラッパ。
SKILL.md / references/pipeline_spec.md と整合した append-only ロガーを提供する。

サブコマンド:
  log-start      サイクル開始イベントを追記し、cycle_id を stdout に出力
  log-end        サイクル終了イベントを追記し、進化トリガー判定を返す
  validate       pipeline.jsonl の構造を検証し、破損行を隔離
  status         直近 N サイクルの完了条件ヒストグラム
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

COMPLETION_STATES = ("success", "failure", "unknown", "error")
DEFAULT_CONFIG = {
    "evolution_threshold": 10,
    "completion_states": list(COMPLETION_STATES),
    "recurrence_window": 3,
    "auto_apply": False,
}


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_cycle_id() -> str:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = secrets.token_hex(2)
    return f"{stamp}-{suffix}"


def resolve_skill_root(skill_path: str | None) -> Path:
    if skill_path:
        return Path(skill_path).expanduser().resolve()
    # default: current working directory
    return Path.cwd().resolve()


def load_config(skill_root: Path) -> dict:
    config_path = skill_root / "pipeline.config.json"
    if not config_path.exists():
        return dict(DEFAULT_CONFIG)
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"warning: pipeline.config.json is invalid JSON ({exc}); using defaults", file=sys.stderr)
        return dict(DEFAULT_CONFIG)
    merged = dict(DEFAULT_CONFIG)
    merged.update(data or {})
    return merged


def ensure_log_dirs(skill_root: Path) -> Path:
    logs_dir = skill_root / "logs"
    (logs_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (logs_dir / "evolutions").mkdir(parents=True, exist_ok=True)
    jsonl = logs_dir / "pipeline.jsonl"
    if not jsonl.exists():
        jsonl.touch()
    return jsonl


def append_jsonl(jsonl_path: Path, payload: dict) -> None:
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def iter_jsonl(jsonl_path: Path) -> Iterable[dict]:
    if not jsonl_path.exists():
        return
    with jsonl_path.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError as exc:
                yield {"__broken__": True, "__lineno__": lineno, "__raw__": raw, "__error__": str(exc)}


# --- subcommands ---------------------------------------------------------


def cmd_log_start(args: argparse.Namespace) -> int:
    skill_root = resolve_skill_root(args.skill_root)
    jsonl = ensure_log_dirs(skill_root)
    cycle_id = args.cycle_id or generate_cycle_id()
    payload = {
        "event": "start",
        "cycle_id": cycle_id,
        "parent_cycle_id": args.parent_cycle_id,
        "skill_name": args.skill_name,
        "started_at": utc_now_iso(),
        "instruction": args.instruction,
    }
    if args.context_hash:
        payload["context_hash"] = args.context_hash
    append_jsonl(jsonl, payload)
    print(cycle_id)
    return 0


def cmd_log_end(args: argparse.Namespace) -> int:
    if args.completion_state not in COMPLETION_STATES:
        print(
            f"error: --completion-state must be one of {COMPLETION_STATES}",
            file=sys.stderr,
        )
        return 2
    skill_root = resolve_skill_root(args.skill_root)
    jsonl = ensure_log_dirs(skill_root)
    config = load_config(skill_root)

    actions: list[dict] = []
    if args.action:
        for raw in args.action:
            try:
                actions.append(json.loads(raw))
            except json.JSONDecodeError:
                actions.append({"tool": raw})

    assumption_notes: list[str] = list(args.assumption_note or [])

    payload = {
        "event": "end",
        "cycle_id": args.cycle_id,
        "skill_name": args.skill_name,
        "ended_at": utc_now_iso(),
        "reasoning_summary": args.reasoning_summary or "",
        "actions": actions,
        "output_summary": args.output_summary or "",
        "followup_feedback": args.followup_feedback,
        "completion_state": args.completion_state,
        "completion_reason": args.completion_reason or "",
        "assumption_notes": assumption_notes,
    }
    append_jsonl(jsonl, payload)

    # 進化トリガー判定 = 最後の "evolution-review" 以降の start イベント数
    cycles_since_review = 0
    for entry in iter_jsonl(jsonl):
        if entry.get("__broken__"):
            continue
        if entry.get("event") == "start":
            cycles_since_review += 1
        # evolution-review が end として記録される (actions に "evolve.py" / target=review を含む)
        if entry.get("event") == "end":
            actions_ = entry.get("actions") or []
            if any(
                (isinstance(a, dict) and a.get("tool") in ("evolve.py", "evolution-review"))
                or (isinstance(a, str) and a in ("evolve.py", "evolution-review"))
                for a in actions_
            ):
                cycles_since_review = 0

    threshold = int(config.get("evolution_threshold", 10))
    evolution_due = cycles_since_review >= threshold

    result = {
        "cycle_id": args.cycle_id,
        "completion_state": args.completion_state,
        "cycles_since_review": cycles_since_review,
        "evolution_threshold": threshold,
        "evolution_due": evolution_due,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    skill_root = resolve_skill_root(args.skill_root)
    jsonl = skill_root / "logs" / "pipeline.jsonl"
    if not jsonl.exists():
        print("no log file")
        return 0
    broken_path = skill_root / "logs" / "pipeline.broken.jsonl"
    starts: dict[str, dict] = {}
    ends: dict[str, dict] = {}
    broken: list[dict] = []
    problems: list[str] = []
    for entry in iter_jsonl(jsonl):
        if entry.get("__broken__"):
            broken.append(entry)
            continue
        event = entry.get("event")
        cid = entry.get("cycle_id")
        if not cid:
            problems.append(f"entry without cycle_id: {entry}")
            continue
        if event == "start":
            starts[cid] = entry
        elif event == "end":
            ends[cid] = entry
            if entry.get("completion_state") not in COMPLETION_STATES:
                problems.append(f"cycle {cid}: invalid completion_state {entry.get('completion_state')!r}")
    unpaired_starts = set(starts) - set(ends)
    unpaired_ends = set(ends) - set(starts)
    for cid in unpaired_starts:
        problems.append(f"cycle {cid}: start without end")
    for cid in unpaired_ends:
        problems.append(f"cycle {cid}: end without start")

    if broken:
        with broken_path.open("a", encoding="utf-8") as f:
            for entry in broken:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    summary = {
        "starts": len(starts),
        "ends": len(ends),
        "broken_lines": len(broken),
        "problems": problems,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not problems and not broken else 1


def cmd_status(args: argparse.Namespace) -> int:
    skill_root = resolve_skill_root(args.skill_root)
    jsonl = skill_root / "logs" / "pipeline.jsonl"
    counts = {state: 0 for state in COMPLETION_STATES}
    total = 0
    recent = []
    for entry in iter_jsonl(jsonl) if jsonl.exists() else []:
        if entry.get("__broken__"):
            continue
        if entry.get("event") == "end":
            state = entry.get("completion_state")
            if state in counts:
                counts[state] += 1
            total += 1
            recent.append({
                "cycle_id": entry.get("cycle_id"),
                "completion_state": state,
                "output_summary": entry.get("output_summary"),
            })
    recent = recent[-args.last :]
    config = load_config(skill_root)
    print(
        json.dumps(
            {
                "skill_root": str(skill_root),
                "total_completed_cycles": total,
                "by_completion_state": counts,
                "recent": recent,
                "config": config,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skill-root", help="スキルのルートディレクトリ (既定: カレント)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("log-start", help="サイクル開始を記録")
    p_start.add_argument("--skill-name", required=True)
    p_start.add_argument("--instruction", required=True, help="指示の要約 (PII マスク済み)")
    p_start.add_argument("--parent-cycle-id", default=None)
    p_start.add_argument("--cycle-id", default=None, help="明示指定 (省略時は自動採番)")
    p_start.add_argument("--context-hash", default=None)
    p_start.set_defaults(func=cmd_log_start)

    p_end = sub.add_parser("log-end", help="サイクル終了を記録し進化トリガー判定")
    p_end.add_argument("--skill-name", required=True)
    p_end.add_argument("--cycle-id", required=True)
    p_end.add_argument("--completion-state", required=True, choices=COMPLETION_STATES)
    p_end.add_argument("--completion-reason", default="")
    p_end.add_argument("--reasoning-summary", default="")
    p_end.add_argument("--output-summary", default="")
    p_end.add_argument("--followup-feedback", default=None)
    p_end.add_argument(
        "--action",
        action="append",
        help="行為。JSON 文字列か単純な tool 名。複数指定可。",
    )
    p_end.add_argument(
        "--assumption-note",
        action="append",
        help="推測した箇所の要約。複数指定可。",
    )
    p_end.set_defaults(func=cmd_log_end)

    p_validate = sub.add_parser("validate", help="pipeline.jsonl の整合性を検証")
    p_validate.set_defaults(func=cmd_validate)

    p_status = sub.add_parser("status", help="直近のサイクル状況を要約")
    p_status.add_argument("--last", type=int, default=10)
    p_status.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
