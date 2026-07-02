#!/usr/bin/env python3
"""Append a time-stamped line to journal/YYYY-MM-DD/memo.md (append-only).

Usage:
  python3 append_memo.py "ゴールを X から Y に変更 (理由: ...)" [--date YYYY-MM-DD] [--time HH:MM]

Environment:
  JOURNAL_DIR  Override the journal base directory.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime

from journal_paths import parse_date, resolve_journal_dir

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

MEMO_HEADER = """# Memo — {date}

"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", help="追記する内容 (1 行)")
    parser.add_argument("--date", default=None, help="対象日 (YYYY-MM-DD, 既定: 今日)")
    parser.add_argument("--time", default=None, help="時刻 (HH:MM, 既定: 現在時刻)")
    args = parser.parse_args(argv)

    try:
        day = parse_date(args.date)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    stamp = args.time or datetime.now().strftime("%H:%M")
    if not TIME_RE.match(stamp):
        print(f"error: invalid time (expected HH:MM): {stamp!r}", file=sys.stderr)
        return 2

    text = " ".join(args.text.split())  # collapse newlines/extra spaces into one line
    if not text:
        print("error: empty memo text", file=sys.stderr)
        return 2

    memo_path = resolve_journal_dir() / day / "memo.md"
    memo_path.parent.mkdir(parents=True, exist_ok=True)
    if not memo_path.exists():
        memo_path.write_text(MEMO_HEADER.format(date=day), encoding="utf-8")

    with memo_path.open("a", encoding="utf-8") as f:
        f.write(f"- {stamp} {text}\n")

    print(f"appended: {memo_path}")
    print(f"- {stamp} {text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
