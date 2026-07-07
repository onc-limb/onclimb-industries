#!/usr/bin/env python3
"""griot-explain-coach: 指摘台帳 (review-log.jsonl) の操作スクリプト。

台帳は追記のみ。エージェントは JSONL を直接編集せず、必ずこのスクリプトを経由する。

  add   --file entries.json   指摘エントリを検証して追記(- で stdin)
  stats [--from D] [--to D]   期間集計(カテゴリ別・重大度別・月次推移・ペルソナ別)
  list  [--category C] [--session S] [--limit N]   エントリの一覧表示

データ配置: <repo>/explain-practice-data/review-log.jsonl
上書き: 環境変数 EXPLAIN_PRACTICE_DATA_DIR
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

CATEGORIES = {
    "conclusion-first": "結論の先出し",
    "structure": "構成・順序",
    "audience-fit": "聞き手適合",
    "concreteness": "具体性・例示",
    "logic": "論理のつながり",
    "completeness": "情報の欠落",
    "brevity": "冗長さ・話量",
    "clarity": "表現・言葉選び",
    "delivery": "話し方",
}
SEVERITIES = ("major", "minor")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REQUIRED = ("date", "session", "persona", "category", "severity", "summary")


def data_dir() -> Path:
    env = os.environ.get("EXPLAIN_PRACTICE_DATA_DIR")
    if env:
        return Path(env)
    # <repo>/.claude/skills/griot-explain-coach/scripts/review_log.py -> <repo>
    return Path(__file__).resolve().parents[4] / "explain-practice-data"


def log_path() -> Path:
    return data_dir() / "review-log.jsonl"


def load_entries():
    path = log_path()
    if not path.exists():
        return []
    entries = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"警告: {path}:{lineno} を JSON として読めないためスキップ", file=sys.stderr)
    return entries


def validate(entry, idx):
    errors = []
    for key in REQUIRED:
        if not str(entry.get(key, "")).strip():
            errors.append(f"必須フィールド '{key}' が空")
    if entry.get("date") and not DATE_RE.match(str(entry["date"])):
        errors.append(f"date は YYYY-MM-DD 形式: {entry['date']!r}")
    if entry.get("category") and entry["category"] not in CATEGORIES:
        errors.append(
            f"category が固定語彙にない: {entry['category']!r} (許可: {', '.join(CATEGORIES)})"
        )
    if entry.get("severity") and entry["severity"] not in SEVERITIES:
        errors.append(f"severity は major/minor のみ: {entry['severity']!r}")
    unknown = set(entry) - set(REQUIRED) - {"advice"}
    if unknown:
        errors.append(f"未知のフィールド: {', '.join(sorted(unknown))}")
    return [f"entries[{idx}]: {e}" for e in errors]


def cmd_add(args):
    raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    entries = json.loads(raw)
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list) or not entries:
        sys.exit("エラー: 入力は 1 件以上のエントリの JSON 配列")
    errors = [msg for i, e in enumerate(entries) for msg in validate(e, i)]
    if errors:
        sys.exit("エラー: 追記を中止しました\n" + "\n".join(f"  - {m}" for m in errors))
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    total = sum(1 for line in path.open(encoding="utf-8") if line.strip())
    print(f"{len(entries)} 件を追記しました → {path} (累計 {total} 件)")


def in_range(entry, date_from, date_to):
    d = entry.get("date", "")
    return (not date_from or d >= date_from) and (not date_to or d <= date_to)


def cmd_stats(args):
    entries = [e for e in load_entries() if in_range(e, args.date_from, args.date_to)]
    period = f"{args.date_from or '(最初)'} 〜 {args.date_to or '(最新)'}"
    if not entries:
        print(f"期間 {period}: エントリなし ({log_path()})")
        return
    if args.json:
        by_cat = Counter(e["category"] for e in entries)
        print(json.dumps({
            "period": {"from": args.date_from, "to": args.date_to},
            "total": len(entries),
            "sessions": len({e["session"] for e in entries}),
            "by_category": dict(by_cat.most_common()),
            "by_severity": dict(Counter(e["severity"] for e in entries)),
        }, ensure_ascii=False, indent=2))
        return

    sessions = {e["session"] for e in entries}
    print(f"# 指摘台帳の集計  期間: {period}")
    print(f"指摘 {len(entries)} 件 / セッション {len(sessions)} 回 "
          f"(1 回あたり平均 {len(entries) / len(sessions):.1f} 件)\n")

    print("## カテゴリ別 (件数の多い順 = 苦手の候補)")
    by_cat = Counter(e["category"] for e in entries)
    for cat, n in by_cat.most_common():
        majors = sum(1 for e in entries if e["category"] == cat and e["severity"] == "major")
        bar = "#" * n
        print(f"  {CATEGORIES[cat]:<8} ({cat:<16}) {n:3d} 件 (major {majors}) {bar}")

    print("\n## 月次推移 (月 × カテゴリ件数)")
    by_month = defaultdict(Counter)
    for e in entries:
        by_month[e["date"][:7]][e["category"]] += 1
    for month in sorted(by_month):
        items = "  ".join(f"{CATEGORIES[c]}:{n}" for c, n in by_month[month].most_common())
        print(f"  {month}: 計 {sum(by_month[month].values())} 件  {items}")

    print("\n## ペルソナ別")
    by_persona = defaultdict(list)
    for e in entries:
        by_persona[e["persona"]].append(e)
    for persona, es in sorted(by_persona.items(), key=lambda kv: -len(kv[1])):
        top = Counter(e["category"] for e in es).most_common(2)
        tops = ", ".join(f"{CATEGORIES[c]} {n}" for c, n in top)
        print(f"  {persona}: {len(es)} 件 (多い指摘: {tops})")


def cmd_list(args):
    entries = load_entries()
    if args.category:
        if args.category not in CATEGORIES:
            sys.exit(f"エラー: 未知の category: {args.category!r} (許可: {', '.join(CATEGORIES)})")
        entries = [e for e in entries if e["category"] == args.category]
    if args.session:
        entries = [e for e in entries if e["session"] == args.session]
    entries.sort(key=lambda e: e.get("date", ""))
    shown = entries[-args.limit:]
    if not shown:
        print("該当エントリなし")
        return
    for e in shown:
        print(f"[{e['date']}] {e['session']}  ({CATEGORIES[e['category']]}/{e['severity']})  "
              f"聞き手: {e['persona']}")
        print(f"    {e['summary']}")
        if e.get("advice"):
            print(f"    → {e['advice']}")
    print(f"\n{len(shown)} 件表示 (絞り込み後 {len(entries)} 件中)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="指摘エントリを追記")
    p_add.add_argument("--file", required=True, help="エントリ配列の JSON ファイル (- で stdin)")
    p_add.set_defaults(func=cmd_add)

    p_stats = sub.add_parser("stats", help="期間集計")
    p_stats.add_argument("--from", dest="date_from", help="YYYY-MM-DD (含む)")
    p_stats.add_argument("--to", dest="date_to", help="YYYY-MM-DD (含む)")
    p_stats.add_argument("--json", action="store_true", help="機械可読 JSON で出力")
    p_stats.set_defaults(func=cmd_stats)

    p_list = sub.add_parser("list", help="エントリ一覧")
    p_list.add_argument("--category", help="カテゴリで絞り込み")
    p_list.add_argument("--session", help="セッション名で絞り込み")
    p_list.add_argument("--limit", type=int, default=20, help="表示件数 (既定 20)")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
