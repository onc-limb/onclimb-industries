#!/usr/bin/env python3
"""CLI コマンド品質分析器 (edith-cli-command-quality)。

Claude が実行した Bash コマンドのログ (jarvis-worklog の raw、または素の CLI
トランスクリプト ~/.claude/projects) を読み、以下を **決定論的に** 集計して
ダッシュボード連携用の metrics.json を出力する。LLM は合計を暗算しない。

  1. コマンド使用頻度ランキング（人間もよく使うコマンドに品質チェック観点を付与）
  2. 品質アンチパターンの検出（references/command_catalog.json 由来）
  3. 危険コマンドの出現チェック（references/dangerous_patterns.json 由来）

カタログ (references/*.json) は辞書資産であり、育てていく前提で外部ファイル化している。

使い方:
  python3 analyze_commands.py <log-root> [--out <dir>] [--date YYYY-MM-DD] [--top N]

  <log-root>: worklog-data/raw か ~/.claude/projects などのディレクトリ
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date as date_cls
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REF = _HERE.parent / "references"

# パイプ / 連結の区切り（$(...) や引用符内は簡易処理で先頭語を拾う割り切り）
SPLIT = re.compile(r"[|&;]{1,2}|\n")
# 先頭に付く環境変数代入 (FOO=bar) や sudo / env / time などの前置きを読み飛ばす
SKIP_PREFIX = re.compile(r"^(sudo|env|time|nohup|command|exec|\S+=\S+)$")
NAME_OK = re.compile(r"^[A-Za-z0-9._-]+$")
SUBCMD_OK = re.compile(r"^[a-z][A-Za-z0-9._-]*$")
EXAMPLE_CAP = 3          # アンチパターンの実例保持数
OCCURRENCE_CAP = 15      # 危険コマンドの occurrence 保持数


# --------------------------------------------------------------------------
# ログ抽出（jarvis-worklog raw / CLI native の両フォーマット対応）
# --------------------------------------------------------------------------
def iter_bash_commands(root: Path):
    """(command_str, source_file) を yield する。"""
    for fp in sorted(root.rglob("*.jsonl")):
        try:
            text = fp.read_text(errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            for cmd in _extract(obj):
                if cmd.strip():
                    yield cmd, str(fp)


def _extract(obj):
    # jarvis-worklog raw: {"type":"tool_use","name":"Bash","body":"# desc\ncmd..."}
    if obj.get("type") == "tool_use" and obj.get("name") == "Bash":
        body = obj.get("body", "")
        yield "\n".join(l for l in body.splitlines() if not l.startswith("# "))
        return
    # CLI native: message.content[] の tool_use(name=Bash).input.command
    msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, list):
        for it in content:
            if isinstance(it, dict) and it.get("type") == "tool_use" and it.get("name") == "Bash":
                cmd = (it.get("input") or {}).get("command", "")
                if cmd:
                    yield cmd


# --------------------------------------------------------------------------
# コマンド名の抽出（複合コマンドを個々のコマンドへ分解）
# --------------------------------------------------------------------------
def command_units(cmd: str):
    """(head, subcommand|None) のリストを返す。1 つの複合コマンドを分解。"""
    units = []
    for seg in SPLIT.split(cmd):
        toks = seg.strip().split()
        i = 0
        while i < len(toks) and SKIP_PREFIX.match(toks[i]):
            i += 1
        if i >= len(toks):
            continue
        head = toks[i]
        if "/" in head:               # パス実行はベース名に寄せる
            head = head.split("/")[-1]
        if not NAME_OK.match(head) or head.startswith("-"):
            continue
        sub = None
        if i + 1 < len(toks) and SUBCMD_OK.match(toks[i + 1]):
            sub = toks[i + 1]
        units.append((head, sub))
    return units


# --------------------------------------------------------------------------
# カタログ読み込み
# --------------------------------------------------------------------------
def load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"warn: {path} を読めませんでした ({e})", file=sys.stderr)
        return default


def compile_patterns(entries):
    """[{regex, ...}] を (compiled, entry) にコンパイル。壊れた regex はスキップ。"""
    out = []
    for e in entries:
        try:
            out.append((re.compile(e["regex"]), e))
        except (re.error, KeyError) as err:
            print(f"warn: 不正なパターン {e!r} をスキップ ({err})", file=sys.stderr)
    return out


# --------------------------------------------------------------------------
# 本体
# --------------------------------------------------------------------------
def analyze(root: Path, top: int, gen_date: str):
    catalog = load_json(_REF / "command_catalog.json", {})
    dangerous_defs = load_json(_REF / "dangerous_patterns.json", [])
    dangerous = compile_patterns(dangerous_defs)

    head_counts = Counter()
    sub_counts = defaultdict(Counter)
    raw_by_head = defaultdict(list)          # head -> [raw command strings]
    danger_hits = defaultdict(lambda: {"count": 0, "occurrences": []})

    files = set()
    n_invocations = 0
    n_segments = 0

    for cmd, src in iter_bash_commands(root):
        files.add(src)
        n_invocations += 1
        # 危険コマンドは複合コマンド全体に対して照合（パイプ to sh 等を拾うため）
        for rx, entry in dangerous:
            if rx.search(cmd):
                pid = entry["id"]
                h = danger_hits[pid]
                h["count"] += 1
                if len(h["occurrences"]) < OCCURRENCE_CAP:
                    h["occurrences"].append({"command": cmd.strip()[:300],
                                             "file": Path(src).name})
        for head, sub in command_units(cmd):
            n_segments += 1
            head_counts[head] += 1
            if sub:
                sub_counts[head][sub] += 1
            if head in catalog and len(raw_by_head[head]) < 500:
                raw_by_head[head].append(cmd)

    total = sum(head_counts.values()) or 1
    commands = []
    for rank, (head, count) in enumerate(head_counts.most_common(top), 1):
        meta = catalog.get(head, {})
        entry = {
            "rank": rank,
            "command": head,
            "count": count,
            "share": round(count / total, 4),
            "category": meta.get("category", "uncategorized"),
            "human_common": bool(meta.get("human_common", False)),
            "in_catalog": head in catalog,
            "subcommands": [{"name": s, "count": c}
                            for s, c in sub_counts[head].most_common(8)],
            "quality_checkpoints": meta.get("checkpoints", []),
            "antipatterns_found": [],
        }
        # アンチパターン照合（このコマンドを含む raw 群に対して）
        for ap in compile_patterns(meta.get("antipatterns", [])):
            rx, adef = ap
            hits = [c for c in raw_by_head[head] if rx.search(c)]
            if hits:
                entry["antipatterns_found"].append({
                    "label": adef.get("label", ""),
                    "advice": adef.get("advice", ""),
                    "count": len(hits),
                    "examples": [h.strip()[:200] for h in hits[:EXAMPLE_CAP]],
                })
        commands.append(entry)

    danger_by_id = {e["id"]: e for e in dangerous_defs}
    dangerous_out = []
    for pid, h in sorted(danger_hits.items(), key=lambda kv: -kv[1]["count"]):
        d = danger_by_id.get(pid, {})
        dangerous_out.append({
            "pattern_id": pid,
            "label": d.get("label", pid),
            "severity": d.get("severity", "unknown"),
            "advice": d.get("advice", ""),
            "count": h["count"],
            "occurrences": h["occurrences"],
        })

    human_common = sum(1 for c in commands if c["human_common"])
    return {
        "schema_version": "1.0",
        "generated_at": gen_date,
        "source": {
            "root": str(root),
            "files_scanned": len(files),
            "bash_invocations": n_invocations,
            "segments_analyzed": n_segments,
        },
        "coverage": {
            "scanned_glob": "**/*.jsonl",
            "notes": [
                "worklog-data/raw と ~/.claude/projects の両フォーマットに対応。",
                "Web 版(claude.ai)はローカルにログが無いため対象外。",
                "パイプ/連結/サブシェルは簡易分解のため、$(...) 内の入れ子コマンドは一部取りこぼす。",
            ],
        },
        "summary": {
            "unique_commands": len(head_counts),
            "ranked_commands": len(commands),
            "human_common_in_top": human_common,
            "dangerous_hit_kinds": len(dangerous_out),
            "dangerous_hit_total": sum(d["count"] for d in dangerous_out),
        },
        "commands": commands,
        "dangerous": dangerous_out,
    }


def print_summary(m):
    s, src = m["summary"], m["source"]
    print(f"# CLI コマンド品質分析  ({m['generated_at']})")
    print(f"# source: {src['root']}")
    print(f"# files={src['files_scanned']} bash_invocations={src['bash_invocations']} "
          f"unique_commands={s['unique_commands']}\n")
    print("## 使用ランキング（上位）")
    for c in m["commands"]:
        tags = []
        if c["human_common"]:
            tags.append("human-common")
        if c["antipatterns_found"]:
            tags.append(f"antipattern×{sum(a['count'] for a in c['antipatterns_found'])}")
        tag = ("  [" + ", ".join(tags) + "]") if tags else ""
        print(f"{c['rank']:>3}. {c['command']:<12} {c['count']:>5}{tag}")
    if m["dangerous"]:
        print("\n## 危険コマンド出現")
        for d in m["dangerous"]:
            print(f"  [{d['severity']}] {d['label']} : {d['count']} 件")
    else:
        print("\n## 危険コマンド出現: なし")


def main():
    ap = argparse.ArgumentParser(description="CLI コマンド品質分析器")
    ap.add_argument("root", help="ログのルート (worklog-data/raw か ~/.claude/projects)")
    ap.add_argument("--out", help="metrics.json の出力先ディレクトリ（省略時は書き出さない）")
    ap.add_argument("--date", default=None, help="generated_at に入れる日付 (既定: 今日)")
    ap.add_argument("--top", type=int, default=40, help="ランキング上位件数 (既定 40)")
    args = ap.parse_args()

    root = Path(args.root).expanduser()
    if not root.exists():
        sys.exit(f"not found: {root}")
    gen_date = args.date or date_cls.today().isoformat()

    metrics = analyze(root, args.top, gen_date)
    print_summary(metrics)

    if args.out:
        out_dir = Path(args.out).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "command-metrics.json"
        out_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
        print(f"\n-> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
