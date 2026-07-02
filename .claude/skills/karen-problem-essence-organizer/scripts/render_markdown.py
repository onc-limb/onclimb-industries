#!/usr/bin/env python3
"""自分用 Markdown を 4 フェーズ × 重要/付随 で出力する。

仕様の単一情報源は `references/output_formats.md`。本スクリプトはそれに従ったテンプレを描画する。
進化対象 (使用ログから章立てやラベル順を最適化する余地あり)。

入力:
  --input <yaml|json>  : 4 フェーズの中身を構造化したファイル
  --topic <slug>       : kebab-case のトピック名
  --out-dir <path>     : 出力先ディレクトリ (既定: ./out)
  --phase-at-close     : セッション終了時のフェーズ (F1/F2/F3/F4)
  --mode               : realtime|postmortem|retrospective

入力スキーマ (YAML 例):

  summary: "1 行サマリー"
  F1:
    important:
      - "..."
    auxiliary:
      - "..."
  F2: { important: [...], auxiliary: [...] }
  F3: { important: [...], auxiliary: [...] }
  F4: { important: [...], auxiliary: [...] }
  open_questions:        # 批判的指摘・未回答のオープン質問 (未解決の問い章になる)
    - "..."
  retrospective:
    - "..."
  split:
    - issue_slug: "..."
      F1: ...
      F2: ...
      F3: ...
      F4: ...

`split` があれば複数課題として `<topic>__<issue-slug>.md` で分割書き出し。

`--mode retrospective` のときは振り返りレポート専用スキーマ (`<topic>__retrospective.md`):

  facts: ["..."]        # 起きたこと
  drift: ["..."]        # 目的を見失った瞬間
  means_first: ["..."]  # 手段に飛びついた瞬間
  learning: ["..."]     # 学び
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None


PHASES = [
    ("F1", "課題発見 (Discovery)"),
    ("F2", "課題整理 (Structuring)"),
    ("F3", "解決定義 (Done Definition)"),
    ("F4", "手段検討 (Solution)"),
]


def load_input(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        if yaml is None:
            print("error: PyYAML が必要です (pip install pyyaml)", file=sys.stderr)
            sys.exit(2)
        return yaml.safe_load(text) or {}
    return json.loads(text)


def render_bullet_list(items: list[str] | None) -> str:
    if not items:
        return "- (未記入)\n"
    return "".join(f"- {item}\n" for item in items)


def render_phase(phase_key: str, phase_label: str, payload: dict[str, Any] | None) -> str:
    payload = payload or {}
    important = payload.get("important") or []
    auxiliary = payload.get("auxiliary") or []
    return (
        f"## {phase_key}. {phase_label}\n\n"
        f"### 重要 (中心)\n\n{render_bullet_list(important)}\n"
        f"### 付随 (脇に置く)\n\n{render_bullet_list(auxiliary)}\n"
    )


def render_retrospective(items: list[str] | None) -> str:
    if not items:
        return ""
    return "## 振り返り\n\n" + render_bullet_list(items) + "\n"


def render_open_questions(items: list[str] | None) -> str:
    """批判的指摘とオープン質問のうち、未回答のまま残ったものを章として残す。"""
    if not items:
        return ""
    return "## 未解決の問い (Open Questions)\n\n" + render_bullet_list(items) + "\n"


RETRO_SECTIONS = [
    ("facts", "起きたこと (Facts)"),
    ("drift", "目的を見失った瞬間 (Drift Detection)"),
    ("means_first", "手段に飛びついた瞬間 (Means-First Detection)"),
    ("learning", "学び (Learning)"),
]


def render_retrospective_document(
    topic: str,
    data: dict[str, Any],
    phase_at_close: str,
) -> str:
    """モード (c) 振り返りレポート。references/output_formats.md §3 準拠。"""
    created = dt.date.today().isoformat()
    front_matter = (
        "---\n"
        f"topic: {topic}\n"
        f"created: {created}\n"
        f"phase_at_close: {phase_at_close}\n"
        "mode: retrospective\n"
        "---\n\n"
    )
    body = f"# 振り返り {topic}\n\n"
    for key, label in RETRO_SECTIONS:
        body += f"## {label}\n\n{render_bullet_list(data.get(key))}\n"
    body += render_open_questions(data.get("open_questions"))
    return front_matter + body


def render_document(
    topic: str,
    data: dict[str, Any],
    phase_at_close: str,
    mode: str,
) -> str:
    if mode == "retrospective":
        return render_retrospective_document(topic, data, phase_at_close)

    created = dt.date.today().isoformat()
    summary = data.get("summary", "(1 行サマリー未記入)")

    front_matter = (
        "---\n"
        f"topic: {topic}\n"
        f"created: {created}\n"
        f"phase_at_close: {phase_at_close}\n"
        f"mode: {mode}\n"
        "---\n\n"
    )
    body = f"# {topic}\n\n> {summary}\n\n"
    for key, label in PHASES:
        body += render_phase(key, label, data.get(key))
    body += render_open_questions(data.get("open_questions"))
    body += render_retrospective(data.get("retrospective"))
    return front_matter + body


def write_one(
    out_dir: Path,
    topic: str,
    data: dict[str, Any],
    phase_at_close: str,
    mode: str,
    issue_slug: str | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    file_topic = f"{topic}__{issue_slug}" if issue_slug else topic
    # 振り返りレポートは `<date>__retrospective.md` (--topic に日付を渡す想定)
    file_name = f"{file_topic}__retrospective.md" if mode == "retrospective" else f"{file_topic}.md"
    path = out_dir / file_name
    path.write_text(render_document(file_topic, data, phase_at_close, mode), encoding="utf-8")
    return path


def cmd_render(args: argparse.Namespace) -> int:
    data = load_input(Path(args.input))
    out_dir = Path(args.out_dir).expanduser().resolve()
    written: list[str] = []

    splits = data.get("split")
    if isinstance(splits, list) and splits:
        for issue in splits:
            slug = issue.get("issue_slug") or "unnamed"
            path = write_one(out_dir, args.topic, issue, args.phase_at_close, args.mode, slug)
            written.append(str(path))
    else:
        path = write_one(out_dir, args.topic, data, args.phase_at_close, args.mode)
        written.append(str(path))

    print(json.dumps({"written": written}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="構造化入力ファイル (yaml or json)")
    parser.add_argument("--topic", required=True, help="kebab-case トピック名")
    parser.add_argument("--out-dir", default="./out", help="出力先ディレクトリ")
    parser.add_argument("--phase-at-close", default="F1", choices=["F1", "F2", "F3", "F4"])
    parser.add_argument(
        "--mode",
        default="postmortem",
        choices=["realtime", "postmortem", "retrospective"],
    )
    parser.set_defaults(func=cmd_render)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
