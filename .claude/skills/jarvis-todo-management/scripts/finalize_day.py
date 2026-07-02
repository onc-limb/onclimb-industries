#!/usr/bin/env python3
"""Generate the end-of-day report.md skeleton (fixed 4 sections).

The skeleton is filled in by the skill during the closing check-in:
  ## 完了 / ## 未完了 / ## 見積と実績の差分 / ## 翌日への申し送り

An existing report.md is never overwritten (append-only journal policy);
rerun with a different date or edit the existing file instead.

Usage:
  python3 finalize_day.py [--date YYYY-MM-DD]

Environment:
  JOURNAL_DIR  Override the journal base directory.
"""
from __future__ import annotations

import argparse
import sys

from journal_paths import parse_date, resolve_journal_dir

REPORT_TEMPLATE = """# Report — {date}

## 完了

<!-- - タスク名 (見積: 30m / 実績: 20m) -->

## 未完了

<!-- - タスク名 (状態: 進行中 / 振り分け: 翌日繰越 | backlog 戻し | 廃棄 / 理由: ...) -->

## 見積と実績の差分

<!-- - タスク名: 見積 30m → 実績 60m (+30m) 要因: ... -->

## 翌日への申し送り

<!-- - 繰越タスク・注意点・朝いちでやること -->
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

    day_dir = resolve_journal_dir() / day
    report_path = day_dir / "report.md"
    if report_path.exists():
        print(f"exists (kept as-is): {report_path}", file=sys.stderr)
        print("report.md は上書きしない (追記・手動編集で更新すること)", file=sys.stderr)
        return 1

    todo_path = day_dir / "todo.md"
    if not todo_path.exists():
        print(f"warning: {todo_path} not found — 当日の todo.md なしで report を作る", file=sys.stderr)

    day_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(REPORT_TEMPLATE.format(date=day), encoding="utf-8")
    print(f"created: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
