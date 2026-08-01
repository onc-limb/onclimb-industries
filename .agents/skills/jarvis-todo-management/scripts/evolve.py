#!/usr/bin/env python3
"""Self-evolution reviewer.

`logs/pipeline.jsonl` を読んで自己進化レビューを実行し、提案を `EVOLUTION.md` に追記する。
このスクリプトは「機械的な検出」と「人間 / Claude が判断する素材」を分離する。
SKILL.md の書き換え自体は人手承認 (auto_apply=false の既定) または別の Edit 操作で行う。

サブコマンド:
  review     直近 N 件のログを分析し EVOLUTION.md に提案を追記。
  snapshot   進化前のディレクトリスナップショットを logs/evolutions/<ts>/ に保存。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# pipeline.py を sibling import するため scripts/ を sys.path に追加 (import より前で行う)
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from pipeline import (  # type: ignore[import-not-found]  # noqa: E402
    COMPLETION_STATES,
    iter_jsonl,
    load_config,
    resolve_skill_root,
    utc_now_iso,
)


def recent_completed_cycles(jsonl_path: Path, limit: int) -> list[dict]:
    cycles: list[dict] = []
    for entry in iter_jsonl(jsonl_path):
        if entry.get("__broken__"):
            continue
        if entry.get("event") == "end":
            cycles.append(entry)
    return cycles[-limit:]


def cluster_signals(cycles: list[dict], recurrence_window: int) -> list[dict]:
    """recurrence_window 回以上再発した signal を抽出する。

    現実装は完了条件・主要 action・followup_feedback の有無を粗くまとめる。
    深い意味解析は Claude (この skill の利用者) に任せる前提。
    """
    state_counter = Counter(c.get("completion_state") for c in cycles)
    action_counter: Counter = Counter()
    feedback_counter = 0
    for c in cycles:
        for action in c.get("actions") or []:
            if isinstance(action, dict):
                tool = action.get("tool")
            else:
                tool = action
            if tool:
                action_counter[tool] += 1
        if c.get("followup_feedback"):
            feedback_counter += 1

    signals: list[dict] = []

    failures = state_counter.get("failure", 0) + state_counter.get("error", 0)
    if failures >= recurrence_window:
        signals.append({
            "type": "high_failure_rate",
            "detail": f"failure/error が {failures} 件 (window 内)",
            "frequency": failures,
            "generality_hint": "失敗パターンを SKILL.md に予防策として書き出すべきか検討",
        })

    unknowns = state_counter.get("unknown", 0)
    if unknowns >= recurrence_window:
        signals.append({
            "type": "high_unknown_rate",
            "detail": f"unknown が {unknowns} 件",
            "frequency": unknowns,
            "generality_hint": "達成基準の文言が曖昧。SKILL.md に判定基準セクションを追加検討。",
        })

    if feedback_counter >= recurrence_window:
        signals.append({
            "type": "frequent_followup",
            "detail": f"followup_feedback が {feedback_counter} 件",
            "frequency": feedback_counter,
            "generality_hint": "ユーザー追記が頻発 = 初回出力の網羅性に課題。",
        })

    for tool, count in action_counter.most_common():
        if count >= recurrence_window * 2 and tool not in ("Read", "Bash"):
            signals.append({
                "type": "repeated_action",
                "detail": f"{tool} を {count} 回使用",
                "frequency": count,
                "generality_hint": "繰り返し利用するなら scripts/ にヘルパーを切り出すべきか検討。",
            })

    return signals


def render_evolution_entry(skill_name: str, signals: list[dict], cycles_window: int) -> str:
    ts = utc_now_iso()
    lines = [
        f"## {ts} — auto-review",
        "",
        f"- **対象**: `{skill_name}`",
        f"- **観測サイクル数 (window)**: {cycles_window}",
        f"- **検出 signal 数**: {len(signals)}",
        "",
    ]
    if not signals:
        lines.append("シグナルなし: 改善候補は見つかりませんでした。")
        lines.append("")
        lines.append(
            "メモ: 進化レビューを 1 サイクルとして pipeline.jsonl に記録すること (actions に `evolve.py` を含める)。"
        )
        return "\n".join(lines) + "\n"

    lines.append("### 検出シグナル (採用候補・要人手判断)")
    lines.append("")
    for i, sig in enumerate(signals, start=1):
        lines.append(f"{i}. **{sig['type']}** — {sig['detail']}")
        lines.append(f"   - 一般性ヒント: {sig.get('generality_hint', '-')}")
        lines.append(
            "   - 採用条件: `references/evolution_principles.md` の原則 1 (頻度 × 一般性) "
            "と原則 2 (公的ベストプラクティス整合) を確認し、出典を明記すること。"
        )
        lines.append("")
    lines.append("### 次のアクション")
    lines.append("")
    lines.append("1. 上記シグナルに対応する SKILL.md / scripts の修正案を起草。")
    lines.append("2. 公的知識との整合を 1 行で記載 (出典なき改善は不採用)。")
    lines.append("3. 適用前に `evolve.py snapshot` を実行してロールバック点を確保。")
    lines.append("4. 適用後、進化レビュー自体を `pipeline.py log-end` で 1 サイクルとして記録。")
    lines.append("")
    return "\n".join(lines) + "\n"


def cmd_review(args: argparse.Namespace) -> int:
    skill_root = resolve_skill_root(args.skill_path)
    jsonl = skill_root / "logs" / "pipeline.jsonl"
    if not jsonl.exists():
        print("no pipeline.jsonl; run pipeline.py first", file=sys.stderr)
        return 1
    config = load_config(skill_root)
    window = args.window or int(config.get("evolution_threshold", 10))
    recurrence = int(config.get("recurrence_window", 3))
    cycles = recent_completed_cycles(jsonl, window)
    signals = cluster_signals(cycles, recurrence)

    evolution_md = skill_root / "EVOLUTION.md"
    skill_name = skill_root.name
    entry = render_evolution_entry(skill_name, signals, len(cycles))

    header = "" if evolution_md.exists() else "# EVOLUTION\n\n進化レビューの提案・適用履歴 (append-only)\n\n"
    with evolution_md.open("a", encoding="utf-8") as f:
        if header:
            f.write(header)
        f.write(entry)

    print(
        json.dumps(
            {
                "skill_root": str(skill_root),
                "cycles_analyzed": len(cycles),
                "signals_detected": len(signals),
                "evolution_md": str(evolution_md),
                "auto_apply": bool(config.get("auto_apply", False)),
                "next_step": "Edit SKILL.md / scripts based on EVOLUTION.md, then log this evolution cycle.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    skill_root = resolve_skill_root(args.skill_path)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = skill_root / "logs" / "evolutions" / ts / "before"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("SKILL.md", "pipeline.config.json", "EVOLUTION.md"):
        src = skill_root / name
        if src.exists():
            shutil.copy2(src, dest / name)
    # scripts と references はディレクトリごとコピー
    for dirname in ("scripts", "references"):
        src_dir = skill_root / dirname
        if src_dir.exists():
            shutil.copytree(src_dir, dest / dirname, dirs_exist_ok=True)
    print(json.dumps({"snapshot": str(dest)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_review = sub.add_parser("review", help="自己進化レビューを実行し EVOLUTION.md に提案を追記")
    p_review.add_argument("--skill-path", default=".", help="対象スキルのルート")
    p_review.add_argument("--window", type=int, default=0, help="観測する直近サイクル数 (0=しきい値を流用)")
    p_review.set_defaults(func=cmd_review)

    p_snap = sub.add_parser("snapshot", help="現行 SKILL.md / scripts / references のスナップショットを保存")
    p_snap.add_argument("--skill-path", default=".")
    p_snap.set_defaults(func=cmd_snapshot)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
