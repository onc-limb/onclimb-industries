#!/usr/bin/env python3
"""Monthly personal budget aggregator (deterministic; stdlib only).

Reads, under the data dir (--data-dir > $BUDGET_DATA > ./budget-data):
  - entries/YYYY-MM.json   variable expenses (receipt / gmail / manual entries)
  - config/fixed-costs.json fixed costs (rent, utilities, subscriptions, ...)
  - config/income.json      income (default monthly list + per-month overrides)

Computes:
  - income total / fixed total / variable total / balance (income - fixed - variable)
  - variable expenses grouped by category (amount + count)
  - fixed costs applied to the target month (active_from / active_until filter)
  - duplicate suspicions: 2nd+ entry with same (date, amount, normalized store),
    and 2nd+ entry with same non-null gmail_message_id
  - previous-month comparison when entries/<prev-month>.json exists
  - warnings: unknown category, invalid amount, entry date outside target month

Emits JSON (default) or Markdown (--markdown). The LLM must transcribe these
numbers verbatim and never compute totals itself.

Usage:
  python3 aggregate.py --month 2026-07 [--data-dir DIR] [--markdown] [--out FILE]
"""

import argparse
import json
import os
import sys
from collections import OrderedDict
from pathlib import Path

DISCLAIMER = (
    "本レポートは家計情報の機械的な整理であり、金融助言・投資助言・節約指導ではありません。"
    "金額は読み取り元（レシート・メール等）との照合を推奨します。"
)

# Must stay in sync with references/categories.md (manual updates only).
KNOWN_CATEGORIES = [
    "食費",
    "日用品",
    "交通",
    "医療",
    "交際",
    "趣味・娯楽",
    "衣服・美容",
    "教育",
    "住居",
    "水道光熱",
    "通信",
    "保険",
    "サブスク",
    "特別支出",
    "その他",
]

PAYMENT_METHODS = ["cash", "credit", "e-money", "bank_transfer", "unknown"]


def resolve_data_dir(cli_value):
    if cli_value:
        return Path(cli_value)
    env = os.environ.get("BUDGET_DATA")
    if env:
        return Path(env)
    return Path.cwd() / "budget-data"


def prev_month_of(month):
    year, mon = month.split("-")
    y, m = int(year), int(mon)
    if m == 1:
        y, m = y - 1, 12
    else:
        m -= 1
    return f"{y:04d}-{m:02d}"


def load_json(path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def valid_amount(value):
    """Amount must be a positive int (yen). Floats allowed only if integral."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float) and value.is_integer():
        return int(value) if value > 0 else None
    return None


def load_entries(data_dir, month, warnings):
    path = data_dir / "entries" / f"{month}.json"
    raw = load_json(path)
    if raw is None:
        warnings.append(f"エントリファイルがありません: entries/{month}.json（変動費 0 円として扱います）")
        return []
    entries = raw.get("entries", raw) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        warnings.append(f"entries/{month}.json の形式が不正です（list でも {{'entries': [...]}} でもない）")
        return []
    return entries


def aggregate_entries(entries, month, warnings):
    by_category = {}
    total = 0
    valid = []
    dup_map = {}
    gmail_map = {}
    duplicates = []

    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            warnings.append(f"エントリ #{i + 1}: dict ではないためスキップしました")
            continue
        eid = e.get("id") or f"(index {i + 1})"
        amount = valid_amount(e.get("amount"))
        if amount is None:
            warnings.append(f"エントリ {eid}: 金額が不正です ({e.get('amount')!r})。合計から除外しました")
            continue
        date = str(e.get("date", ""))
        if not date.startswith(month):
            warnings.append(f"エントリ {eid}: 日付 {date!r} が対象月 {month} 外です（合計には含めています）")
        category = e.get("category") or "その他"
        if category not in KNOWN_CATEGORIES:
            warnings.append(
                f"エントリ {eid}: 未知のカテゴリ {category!r} です（references/categories.md を確認）"
            )
        pm = e.get("payment_method", "unknown")
        if pm not in PAYMENT_METHODS:
            warnings.append(f"エントリ {eid}: 未知の payment_method {pm!r} です")

        store_norm = str(e.get("store", "")).strip().casefold()
        key = (date, amount, store_norm)
        if key in dup_map:
            duplicates.append(
                {
                    "reason": "同一の日付・金額・店舗",
                    "date": date,
                    "store": e.get("store", ""),
                    "amount": amount,
                    "entry_ids": [dup_map[key], eid],
                }
            )
        else:
            dup_map[key] = eid

        gmail_id = e.get("gmail_message_id")
        if gmail_id:
            if gmail_id in gmail_map:
                duplicates.append(
                    {
                        "reason": "同一の gmail_message_id",
                        "date": date,
                        "store": e.get("store", ""),
                        "amount": amount,
                        "entry_ids": [gmail_map[gmail_id], eid],
                    }
                )
            else:
                gmail_map[gmail_id] = eid

        bucket = by_category.setdefault(category, {"amount": 0, "count": 0})
        bucket["amount"] += amount
        bucket["count"] += 1
        total += amount
        valid.append(e)

    ordered = OrderedDict(
        sorted(by_category.items(), key=lambda kv: kv[1]["amount"], reverse=True)
    )
    return total, ordered, duplicates, len(valid)


def load_fixed_costs(data_dir, month, warnings):
    raw = load_json(data_dir / "config" / "fixed-costs.json")
    if raw is None:
        warnings.append("config/fixed-costs.json がありません（固定費 0 円として扱います）")
        return 0, []
    items = raw.get("fixed_costs", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        warnings.append("fixed-costs.json の形式が不正です（固定費 0 円として扱います）")
        return 0, []
    total = 0
    applied = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            warnings.append(f"固定費 #{i + 1}: dict ではないためスキップしました")
            continue
        name = item.get("name", f"(index {i + 1})")
        active_from = item.get("active_from")
        active_until = item.get("active_until")
        if active_from and month < str(active_from):
            continue
        if active_until and month > str(active_until):
            continue
        amount = valid_amount(item.get("amount"))
        if amount is None:
            warnings.append(f"固定費 {name}: 金額が不正です ({item.get('amount')!r})。合計から除外しました")
            continue
        category = item.get("category") or "その他"
        if category not in KNOWN_CATEGORIES:
            warnings.append(f"固定費 {name}: 未知のカテゴリ {category!r} です")
        total += amount
        applied.append({"name": name, "category": category, "amount": amount})
    return total, applied


def load_income(data_dir, month, warnings):
    raw = load_json(data_dir / "config" / "income.json")
    if raw is None:
        warnings.append("config/income.json がありません（収入 0 円として扱います）")
        return 0, []
    if not isinstance(raw, dict):
        warnings.append("income.json の形式が不正です（収入 0 円として扱います）")
        return 0, []
    overrides = raw.get("overrides") or {}
    items = overrides.get(month, raw.get("default") or [])
    if not isinstance(items, list):
        warnings.append(f"income.json の {month} 分の形式が不正です（収入 0 円として扱います）")
        return 0, []
    total = 0
    applied = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            warnings.append(f"収入 #{i + 1}: dict ではないためスキップしました")
            continue
        name = item.get("name", f"(index {i + 1})")
        amount = valid_amount(item.get("amount"))
        if amount is None:
            warnings.append(f"収入 {name}: 金額が不正です ({item.get('amount')!r})。合計から除外しました")
            continue
        total += amount
        applied.append({"name": name, "amount": amount})
    return total, applied


def summarize(data_dir, month, warnings):
    entries = load_entries(data_dir, month, warnings)
    variable_total, by_category, duplicates, valid_count = aggregate_entries(
        entries, month, warnings
    )
    fixed_total, fixed_items = load_fixed_costs(data_dir, month, warnings)
    income_total, income_items = load_income(data_dir, month, warnings)
    expense_total = fixed_total + variable_total
    return {
        "month": month,
        "totals": {
            "income": income_total,
            "fixed": fixed_total,
            "variable": variable_total,
            "expense": expense_total,
            "balance": income_total - expense_total,
        },
        "variable_by_category": by_category,
        "fixed_items": fixed_items,
        "income_items": income_items,
        "duplicates_suspected": duplicates,
        "counts": {
            "entries_total": len(entries),
            "entries_aggregated": valid_count,
            "duplicates_suspected": len(duplicates),
        },
    }


def build_result(data_dir, month):
    warnings = []
    current = summarize(data_dir, month, warnings)

    prev = None
    prev_month = prev_month_of(month)
    if (data_dir / "entries" / f"{prev_month}.json").exists():
        prev_warnings = []  # previous month's issues are not this report's warnings
        prev_summary = summarize(data_dir, prev_month, prev_warnings)
        diff_totals = {
            k: current["totals"][k] - prev_summary["totals"][k]
            for k in current["totals"]
        }
        cat_keys = set(current["variable_by_category"]) | set(
            prev_summary["variable_by_category"]
        )
        diff_categories = {}
        for k in cat_keys:
            cur_amt = current["variable_by_category"].get(k, {}).get("amount", 0)
            prev_amt = prev_summary["variable_by_category"].get(k, {}).get("amount", 0)
            diff_categories[k] = cur_amt - prev_amt
        prev = {
            "month": prev_month,
            "totals": prev_summary["totals"],
            "diff_totals": diff_totals,
            "diff_variable_by_category": diff_categories,
        }
    else:
        warnings.append(
            f"前月ファイル entries/{prev_month}.json が無いため前月比は省略しました"
        )

    result = OrderedDict()
    result["disclaimer"] = DISCLAIMER
    result.update(current)
    result["prev_month"] = prev
    result["warnings"] = warnings
    return result


def yen(n):
    sign = "-" if n < 0 else ""
    return f"{sign}¥{abs(n):,}"


def signed_yen(n):
    return f"+¥{n:,}" if n >= 0 else f"-¥{abs(n):,}"


def to_markdown(r):
    t = r["totals"]
    lines = []
    lines.append(f"# 家計 月次レポート {r['month']}")
    lines.append("")
    lines.append(f"> 免責: {r['disclaimer']}")
    lines.append("")
    lines.append("## サマリ")
    lines.append("")
    lines.append("| 項目 | 金額 |")
    lines.append("|---|---:|")
    lines.append(f"| 収入 | {yen(t['income'])} |")
    lines.append(f"| 固定費 | {yen(t['fixed'])} |")
    lines.append(f"| 変動費 | {yen(t['variable'])} |")
    lines.append(f"| 支出合計 | {yen(t['expense'])} |")
    lines.append(f"| **収支（収入 − 支出）** | **{yen(t['balance'])}** |")
    lines.append("")

    lines.append("## 変動費 カテゴリ別内訳")
    lines.append("")
    if r["variable_by_category"]:
        prev_diff = (r["prev_month"] or {}).get("diff_variable_by_category", {})
        lines.append("| カテゴリ | 金額 | 件数 | 前月比 |")
        lines.append("|---|---:|---:|---:|")
        for cat, v in r["variable_by_category"].items():
            diff = signed_yen(prev_diff[cat]) if cat in prev_diff else "—"
            lines.append(f"| {cat} | {yen(v['amount'])} | {v['count']} | {diff} |")
    else:
        lines.append("（変動費エントリなし）")
    lines.append("")

    lines.append("## 固定費 内訳")
    lines.append("")
    if r["fixed_items"]:
        lines.append("| 名目 | カテゴリ | 金額 |")
        lines.append("|---|---|---:|")
        for item in r["fixed_items"]:
            lines.append(f"| {item['name']} | {item['category']} | {yen(item['amount'])} |")
    else:
        lines.append("（対象月に適用される固定費なし）")
    lines.append("")

    lines.append("## 収入 内訳")
    lines.append("")
    if r["income_items"]:
        lines.append("| 名目 | 金額 |")
        lines.append("|---|---:|")
        for item in r["income_items"]:
            lines.append(f"| {item['name']} | {yen(item['amount'])} |")
    else:
        lines.append("（収入設定なし）")
    lines.append("")

    lines.append("## 前月比")
    lines.append("")
    if r["prev_month"]:
        p = r["prev_month"]
        lines.append(f"| 項目 | 今月 ({r['month']}) | 先月 ({p['month']}) | 差 |")
        lines.append("|---|---:|---:|---:|")
        for key, label in [
            ("income", "収入"),
            ("fixed", "固定費"),
            ("variable", "変動費"),
            ("balance", "収支"),
        ]:
            lines.append(
                f"| {label} | {yen(t[key])} | {yen(p['totals'][key])} | {signed_yen(p['diff_totals'][key])} |"
            )
    else:
        lines.append("（前月のエントリファイルが無いため省略）")
    lines.append("")

    dups = r["duplicates_suspected"]
    lines.append(f"## 重複疑い（{len(dups)} 件）")
    lines.append("")
    if dups:
        lines.append("以下は二重計上の可能性があります。**合計には含めたまま**警告しています。確認してください。")
        lines.append("")
        lines.append("| 理由 | 日付 | 店舗 | 金額 | エントリ ID |")
        lines.append("|---|---|---|---:|---|")
        for d in dups:
            ids = " / ".join(str(x) for x in d["entry_ids"])
            lines.append(
                f"| {d['reason']} | {d['date']} | {d['store']} | {yen(d['amount'])} | {ids} |"
            )
        lines.append("")
        lines.append("> 重複疑いが残っている間、この収支は**未確定**です。")
    else:
        lines.append("なし")
    lines.append("")

    lines.append("## 警告")
    lines.append("")
    if r["warnings"]:
        for w in r["warnings"]:
            lines.append(f"- {w}")
    else:
        lines.append("なし")
    lines.append("")

    c = r["counts"]
    lines.append(
        f"---\n集計対象: エントリ {c['entries_total']} 件中 {c['entries_aggregated']} 件 / "
        f"重複疑い {c['duplicates_suspected']} 件"
    )
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Aggregate monthly personal budget.")
    parser.add_argument("--month", required=True, help="target month, YYYY-MM")
    parser.add_argument(
        "--data-dir", help="budget data dir (default: $BUDGET_DATA or ./budget-data)"
    )
    parser.add_argument(
        "--markdown", action="store_true", help="emit Markdown instead of JSON"
    )
    parser.add_argument("--out", help="output file path (default: stdout)")
    args = parser.parse_args(argv)

    month = args.month
    if len(month) != 7 or month[4] != "-" or not (month[:4] + month[5:]).isdigit():
        parser.error(f"--month must be YYYY-MM, got {month!r}")

    data_dir = resolve_data_dir(args.data_dir)
    if not data_dir.exists():
        print(f"error: data dir not found: {data_dir}", file=sys.stderr)
        return 1

    result = build_result(data_dir, month)
    if args.markdown:
        text = to_markdown(result)
    else:
        text = json.dumps(result, ensure_ascii=False, indent=2)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
        print(f"written: {out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
