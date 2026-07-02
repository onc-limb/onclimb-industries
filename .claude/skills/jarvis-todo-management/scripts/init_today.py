#!/usr/bin/env python3
"""Create journal/YYYY-MM-DD/ with todo.md and memo.md for a new working day.

- Existing files are never overwritten (append-only journal policy).
- Prints the previous journal day's report.md path so the skill can pick up
  the「翌日への申し送り」section.

Usage:
  python3 init_today.py [--date YYYY-MM-DD]

Environment:
  JOURNAL_DIR  Override the journal base directory.
"""
from __future__ import annotations

import argparse
import sys

from journal_paths import parse_date, previous_day_dir, resolve_journal_dir

TODO_TEMPLATE = """# Todo — {date}

<!-- - [ ] タスク名 (見積: 30m / 実績: - / 状態: 未着手) -->
"""

MEMO_TEMPLATE = """# Memo — {date}

<!-- - HH:MM 内容 (append_memo.py で追記する) -->
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=None, help="対象日 (YYYY-MM-DD, 既定: 今日)")
    args = parser.parse_args(argv)

    try:
        day = parse_date(args.date)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    journal_dir = resolve_journal_dir()
    day_dir = journal_dir / day
    day_dir.mkdir(parents=True, exist_ok=True)

    created = []
    skipped = []
    for name, template in (("todo.md", TODO_TEMPLATE), ("memo.md", MEMO_TEMPLATE)):
        path = day_dir / name
        if path.exists():
            skipped.append(path)
        else:
            path.write_text(template.format(date=day), encoding="utf-8")
            created.append(path)

    print(f"journal_dir: {journal_dir}")
    print(f"day_dir: {day_dir}")
    for path in created:
        print(f"created: {path}")
    for path in skipped:
        print(f"exists (kept as-is): {path}")

    prev_dir = previous_day_dir(journal_dir, day)
    if prev_dir is None:
        print("previous_report: (none — 過去の記録なし)")
    else:
        prev_report = prev_dir / "report.md"
        status = "" if prev_report.exists() else " (file missing)"
        print(f"previous_report: {prev_report}{status}")

    backlog = journal_dir / "backlog.md"
    print(f"backlog: {backlog}{'' if backlog.exists() else ' (not created yet)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
