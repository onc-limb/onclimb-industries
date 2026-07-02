#!/usr/bin/env python3
"""Shared helpers for locating the journal directory.

Resolution order:
  1. JOURNAL_DIR environment variable
  2. <git repo root>/journal (walk up from cwd looking for .git)
  3. <cwd>/journal
"""
from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def resolve_journal_dir() -> Path:
    env = os.environ.get("JOURNAL_DIR")
    if env:
        return Path(env).expanduser().resolve()
    cur = Path.cwd().resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / ".git").exists():
            return candidate / "journal"
    return cur / "journal"


def parse_date(value: str | None) -> str:
    """Validate/normalize a YYYY-MM-DD string; default to today (local)."""
    if value is None:
        return date.today().isoformat()
    if not DATE_RE.match(value):
        raise ValueError(f"invalid date (expected YYYY-MM-DD): {value!r}")
    # raises ValueError for impossible dates like 2026-02-30
    date.fromisoformat(value)
    return value


def previous_day_dir(journal_dir: Path, today: str) -> Path | None:
    """Return the latest existing journal/YYYY-MM-DD/ directory before `today`.

    # ASSUMPTION: 「前日」は暦日ではなく「直近の記録が存在する日」とする
    # (週末・休暇明けでも申し送りを拾えるようにするため)。
    """
    if not journal_dir.exists():
        return None
    candidates = sorted(
        p for p in journal_dir.iterdir()
        if p.is_dir() and DATE_RE.match(p.name) and p.name < today
    )
    return candidates[-1] if candidates else None
