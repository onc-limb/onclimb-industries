#!/usr/bin/env python3
"""aggregate.py — deterministic timesheet aggregation (stdlib only).

Role separation:
    Claude classifies work into entries (date / project / hours / source).
    This script owns ALL arithmetic (per-project / per-day totals) so that
    aggregated numbers are reproducible and never produced from LLM memory.

Input : JSON array of entries, via --file PATH or --stdin.
        Each entry: {"date": "YYYY-MM-DD", "project": "<project-id>",
                     "hours": <number>, "source": "<worklog|calendar|manual|...>"}
        Optional keys: "note" (free text, ignored by aggregation).

Output: aggregation result as JSON (default) or Markdown (--format markdown).
        Includes by_project / by_day / by_project_day totals, unclassified
        hours, and warnings (duplicates, day total > 24h, unknown source).

Exit codes: 0 = ok, 2 = invalid input (errors printed to stderr as JSON).

Usage:
    python3 aggregate.py --file entries.json
    python3 aggregate.py --stdin --format markdown --round-to 0.25
    python3 aggregate.py --file entries.json --dedupe
"""

import argparse
import json
import sys
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

UNCLASSIFIED = "unclassified"
KNOWN_SOURCES = {"worklog", "calendar", "manual"}
MAX_HOURS_PER_ENTRY = Decimal("24")
MAX_HOURS_PER_DAY = Decimal("24")


def fmt(value):
    """Format a Decimal as a fixed 2-digit string (stable, no float noise)."""
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_entries(raw):
    """Validate raw JSON value; return (entries, errors).

    entries: list of dicts {date: str, project: str, hours: Decimal, source: str}
    errors : list of human-readable strings (index-tagged)
    """
    errors = []
    entries = []
    if not isinstance(raw, list):
        return [], ["input must be a JSON array of entry objects"]
    for i, item in enumerate(raw):
        tag = "entry[%d]" % i
        if not isinstance(item, dict):
            errors.append("%s: not an object" % tag)
            continue
        entry_errors = []

        raw_date = item.get("date")
        parsed_date = None
        if not isinstance(raw_date, str):
            entry_errors.append("date must be a string 'YYYY-MM-DD'")
        else:
            try:
                parsed_date = date.fromisoformat(raw_date)
            except ValueError:
                entry_errors.append("date %r is not a valid ISO date" % raw_date)

        project = item.get("project")
        if not isinstance(project, str) or not project.strip():
            entry_errors.append("project must be a non-empty string")
        else:
            project = project.strip()

        raw_hours = item.get("hours")
        hours = None
        if isinstance(raw_hours, bool) or raw_hours is None:
            entry_errors.append("hours must be a number")
        else:
            try:
                hours = Decimal(str(raw_hours))
            except InvalidOperation:
                entry_errors.append("hours %r is not a number" % raw_hours)
        if hours is not None:
            if hours <= 0:
                entry_errors.append("hours must be > 0 (got %s)" % hours)
            elif hours > MAX_HOURS_PER_ENTRY:
                entry_errors.append(
                    "hours must be <= %s per entry (got %s)"
                    % (MAX_HOURS_PER_ENTRY, hours)
                )

        source = item.get("source")
        if not isinstance(source, str) or not source.strip():
            entry_errors.append("source must be a non-empty string")
        else:
            source = source.strip()

        if entry_errors:
            errors.extend("%s: %s" % (tag, e) for e in entry_errors)
            continue
        entries.append(
            {
                "date": parsed_date.isoformat(),
                "project": project,
                "hours": hours,
                "source": source,
            }
        )
    return entries, errors


def round_entries(entries, step):
    """Round each entry's hours to the nearest `step` (e.g. 0.25 = 15 min)."""
    rounded = []
    for e in entries:
        q = (e["hours"] / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        hours = q * step
        if hours <= 0:
            hours = step  # never round a real entry down to zero
        rounded.append(dict(e, hours=hours))
    return rounded


def find_duplicates(entries):
    """Group indices of exact duplicates (same date+project+hours+source)."""
    seen = {}
    for i, e in enumerate(entries):
        key = (e["date"], e["project"], str(e["hours"]), e["source"])
        seen.setdefault(key, []).append(i)
    return {k: idxs for k, idxs in seen.items() if len(idxs) > 1}


def aggregate(entries):
    by_project = {}
    by_day = {}
    by_project_day = {}
    by_source = {}
    grand_total = Decimal("0")
    for e in entries:
        p, d, h, s = e["project"], e["date"], e["hours"], e["source"]
        by_project[p] = by_project.get(p, Decimal("0")) + h
        by_day[d] = by_day.get(d, Decimal("0")) + h
        by_project_day.setdefault(p, {})
        by_project_day[p][d] = by_project_day[p].get(d, Decimal("0")) + h
        by_source[s] = by_source.get(s, Decimal("0")) + h
        grand_total += h
    return by_project, by_day, by_project_day, by_source, grand_total


def build_result(entries, dedupe):
    warnings = []
    duplicates_removed = 0

    dups = find_duplicates(entries)
    if dups:
        if dedupe:
            drop = set()
            for idxs in dups.values():
                drop.update(idxs[1:])  # keep the first occurrence
            duplicates_removed = len(drop)
            entries = [e for i, e in enumerate(entries) if i not in drop]
            warnings.append(
                "removed %d exact duplicate entrie(s) (--dedupe)" % duplicates_removed
            )
        else:
            for key, idxs in sorted(dups.items()):
                warnings.append(
                    "possible double counting: entry (date=%s, project=%s, "
                    "hours=%s, source=%s) appears %d times; review or use --dedupe"
                    % (key[0], key[1], key[2], key[3], len(idxs))
                )

    unknown_sources = sorted(
        {e["source"] for e in entries if e["source"] not in KNOWN_SOURCES}
    )
    if unknown_sources:
        warnings.append(
            "unknown source(s): %s (expected one of %s)"
            % (", ".join(unknown_sources), ", ".join(sorted(KNOWN_SOURCES)))
        )

    by_project, by_day, by_project_day, by_source, grand_total = aggregate(entries)

    for d in sorted(by_day):
        if by_day[d] > MAX_HOURS_PER_DAY:
            warnings.append(
                "day total exceeds %sh on %s (%s h) — check for double counting"
                % (MAX_HOURS_PER_DAY, d, fmt(by_day[d]))
            )

    unclassified_hours = by_project.get(UNCLASSIFIED, Decimal("0"))
    if unclassified_hours > 0:
        warnings.append(
            "unclassified hours present: %s h — reassign before invoicing"
            % fmt(unclassified_hours)
        )

    days = sorted(by_day)
    result = {
        "period": {
            "start": days[0] if days else None,
            "end": days[-1] if days else None,
            "days_with_entries": len(days),
        },
        "entry_count": len(entries),
        "duplicates_removed": duplicates_removed,
        "grand_total_hours": fmt(grand_total),
        "unclassified_hours": fmt(unclassified_hours),
        "by_project": {
            p: fmt(h)
            for p, h in sorted(by_project.items(), key=lambda kv: (-kv[1], kv[0]))
        },
        "by_day": {d: fmt(by_day[d]) for d in days},
        "by_project_day": {
            p: {d: fmt(h) for d, h in sorted(day_map.items())}
            for p, day_map in sorted(by_project_day.items())
        },
        "by_source": {s: fmt(h) for s, h in sorted(by_source.items())},
        "warnings": warnings,
    }
    return result


def to_markdown(result):
    lines = []
    period = result["period"]
    if period["start"]:
        lines.append(
            "# 稼働集計 %s 〜 %s" % (period["start"], period["end"])
        )
    else:
        lines.append("# 稼働集計 (エントリなし)")
    lines.append("")
    lines.append(
        "- 総稼働: **%s h** / エントリ %d 件 / 稼働日 %d 日"
        % (result["grand_total_hours"], result["entry_count"], period["days_with_entries"])
    )
    lines.append("- 未分類: %s h" % result["unclassified_hours"])
    if result["by_source"]:
        lines.append(
            "- ソース内訳: "
            + ", ".join("%s %s h" % (s, h) for s, h in result["by_source"].items())
        )
    lines.append("")

    lines.append("## 案件別合計")
    lines.append("")
    lines.append("| 案件 | 稼働時間 (h) | 構成比 |")
    lines.append("|---|---:|---:|")
    total = Decimal(result["grand_total_hours"])
    for p, h in result["by_project"].items():
        if total > 0:
            share = (Decimal(h) / total * 100).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
            share_s = "%s%%" % share
        else:
            share_s = "-"
        label = "**(未分類)**" if p == UNCLASSIFIED else p
        lines.append("| %s | %s | %s |" % (label, h, share_s))
    lines.append("| **合計** | **%s** | 100%% |" % result["grand_total_hours"])
    lines.append("")

    lines.append("## 日別 × 案件別")
    lines.append("")
    projects = list(result["by_project"].keys())
    header = (
        "| 日付 | "
        + " | ".join("(未分類)" if p == UNCLASSIFIED else p for p in projects)
        + " | 日合計 |"
    )
    lines.append(header)
    lines.append("|---|" + "---:|" * (len(projects) + 1))
    for d, day_total in result["by_day"].items():
        cells = []
        for p in projects:
            cells.append(result["by_project_day"].get(p, {}).get(d, ""))
        lines.append("| %s | %s | %s |" % (d, " | ".join(cells), day_total))
    lines.append("")

    if result["warnings"]:
        lines.append("## 警告 (要確認)")
        lines.append("")
        for w in result["warnings"]:
            lines.append("- %s" % w)
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Aggregate timesheet entries (per-project / per-day totals)."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="path to a JSON file with an entry array")
    src.add_argument("--stdin", action="store_true", help="read JSON from stdin")
    parser.add_argument(
        "--format", choices=["json", "markdown"], default="json",
        help="output format (default: json)",
    )
    parser.add_argument(
        "--round-to", type=str, default=None, metavar="H",
        help="round each entry's hours to the nearest H hours (e.g. 0.25 = 15 min)",
    )
    parser.add_argument(
        "--dedupe", action="store_true",
        help="drop exact duplicate entries (same date+project+hours+source)",
    )
    args = parser.parse_args(argv)

    try:
        if args.file:
            with open(args.file, encoding="utf-8") as f:
                raw = json.load(f)
        else:
            raw = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"errors": ["cannot read input: %s" % exc]}), file=sys.stderr)
        return 2

    entries, errors = parse_entries(raw)
    if errors:
        print(json.dumps({"errors": errors}, ensure_ascii=False, indent=2),
              file=sys.stderr)
        return 2

    if args.round_to:
        try:
            step = Decimal(args.round_to)
        except InvalidOperation:
            print(json.dumps({"errors": ["--round-to %r is not a number" % args.round_to]}),
                  file=sys.stderr)
            return 2
        if step <= 0:
            print(json.dumps({"errors": ["--round-to must be > 0"]}), file=sys.stderr)
            return 2
        entries = round_entries(entries, step)

    result = build_result(entries, dedupe=args.dedupe)
    if args.format == "markdown":
        print(to_markdown(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
