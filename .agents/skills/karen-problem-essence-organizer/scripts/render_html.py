#!/usr/bin/env python3
"""クライアント向け HTML を Minto Pyramid / SCQA 流で出力する。

仕様の単一情報源は `references/output_formats.md`。進化対象。

入力スキーマ (YAML 例):

  topic: "..."
  conclusion:
    problem: "..."       # 各フィールドは str または list を受け付ける。
    done: "..."          #   str  : "\n\n" 区切りで複数段落 <p> に分割
    proposal: "..."      #   list : <ul><li> の箇条書き
  reasoning:             #   空値 : (未記入) と明示表示
    situation: "..."
    complication: "..."
  proposal:
    done_detail: "..."
    solution: "..."
    retreat: "..."
  call_to_action:
    decisions: ["...", "..."]
    missing_info:
      - what: "決められないこと"
        needs: "必要な情報"
        who: "誰が"
        deadline: "いつまでに"
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None


CSS = """
:root { --fg: #111; --muted: #666; --accent: #205080; --warn: #b04020; --bg: #fff; }
body { font-family: -apple-system, BlinkMacSystemFont, "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif;
       color: var(--fg); background: var(--bg); max-width: 880px; margin: 2em auto; padding: 0 1em;
       line-height: 1.7; }
h1 { border-bottom: 3px solid var(--accent); padding-bottom: .3em; }
h2 { color: var(--accent); margin-top: 2em; }
h3 { color: var(--muted); }
section { page-break-inside: avoid; margin-bottom: 2em; }
.conclusion { background: #f4f8fb; padding: 1em 1.4em; border-left: 6px solid var(--accent); }
.missing-info table { border-collapse: collapse; width: 100%; margin-top: .5em; }
.missing-info th, .missing-info td { border: 1px solid #ccc; padding: .4em .8em; text-align: left; }
.missing-info th { background: #fff3e6; color: var(--warn); }
.muted { color: var(--muted); }
ul { padding-left: 1.2em; }
@media print {
  body { margin: 0; max-width: none; }
  h2 { page-break-before: auto; }
  section { page-break-inside: avoid; }
}
"""


def esc(s: Any) -> str:
    return html.escape(str(s)) if s is not None else ""


def render_rich(value: Any, indent: str = "  ") -> str:
    """str | list | None を HTML ブロックに変換する。

    - None / 空値: (未記入) を明示表示 (無言で空にしない)
    - list      : <ul><li> の箇条書き
    - str       : "\\n\\n" 区切りで複数の <p> に分割
    """
    if isinstance(value, list):
        if not value:
            return f"{indent}<p class=\"muted\">(未記入)</p>\n"
        items = "".join(f"{indent}  <li>{esc(v)}</li>\n" for v in value)
        return f"{indent}<ul>\n{items}{indent}</ul>\n"
    paragraphs = [p.strip() for p in str(value or "").split("\n\n") if p.strip()]
    if not paragraphs:
        return f"{indent}<p class=\"muted\">(未記入)</p>\n"
    return "".join(f"{indent}<p>{esc(p)}</p>\n" for p in paragraphs)


def load_input(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        if yaml is None:
            print("error: PyYAML が必要です (pip install pyyaml)", file=sys.stderr)
            sys.exit(2)
        return yaml.safe_load(text) or {}
    return json.loads(text)


def render_conclusion(payload: dict[str, Any]) -> str:
    p = payload.get("conclusion") or {}
    return (
        "<section class=\"conclusion\">\n"
        "  <h2>結論</h2>\n"
        "  <h3>課題</h3>\n" + render_rich(p.get("problem")) +
        "  <h3>解決状態 (Done)</h3>\n" + render_rich(p.get("done")) +
        "  <h3>提案</h3>\n" + render_rich(p.get("proposal")) +
        "</section>\n"
    )


def render_reasoning(payload: dict[str, Any]) -> str:
    p = payload.get("reasoning") or {}
    return (
        "<section>\n"
        "  <h2>根拠</h2>\n"
        "  <h3>現状 (Situation)</h3>\n" + render_rich(p.get("situation")) +
        "  <h3>何が問題か (Complication)</h3>\n" + render_rich(p.get("complication")) +
        "</section>\n"
    )


def render_proposal(payload: dict[str, Any]) -> str:
    p = payload.get("proposal") or {}
    return (
        "<section>\n"
        "  <h2>提案</h2>\n"
        "  <h3>目指す Done 状態</h3>\n" + render_rich(p.get("done_detail")) +
        "  <h3>手段</h3>\n" + render_rich(p.get("solution")) +
        "  <h3>撤退条件 / 不確実性</h3>\n" + render_rich(p.get("retreat")) +
        "</section>\n"
    )


def render_call_to_action(payload: dict[str, Any]) -> str:
    p = payload.get("call_to_action") or {}
    decisions = p.get("decisions") or []
    missing = p.get("missing_info") or []

    decisions_html = "".join(f"    <li>{esc(d)}</li>\n" for d in decisions) or "    <li class=\"muted\">(未記入)</li>\n"

    rows_html = ""
    for row in missing:
        rows_html += (
            "      <tr>"
            f"<td>{esc(row.get('what'))}</td>"
            f"<td>{esc(row.get('needs'))}</td>"
            f"<td>{esc(row.get('who'))}</td>"
            f"<td>{esc(row.get('deadline'))}</td>"
            "</tr>\n"
        )
    if not rows_html:
        rows_html = "      <tr><td colspan=\"4\" class=\"muted\">(未記入)</td></tr>\n"

    return (
        "<section>\n"
        "  <h2>何をしてほしいか</h2>\n"
        "  <h3>意思決定の依頼</h3>\n"
        f"  <ul>\n{decisions_html}  </ul>\n"
        "  <div class=\"missing-info\">\n"
        "    <h3>今、決められないこと (不足情報の可視化)</h3>\n"
        "    <table>\n"
        "      <tr><th>決められないこと</th><th>必要な情報</th><th>誰が</th><th>いつまでに</th></tr>\n"
        f"{rows_html}"
        "    </table>\n"
        "  </div>\n"
        "</section>\n"
    )


def render_document(data: dict[str, Any]) -> str:
    topic = data.get("topic") or "untitled"
    today = dt.date.today().isoformat()
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"ja\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        f"<title>{esc(topic)} — 提案</title>\n"
        f"<style>{CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        f"<h1>{esc(topic)}</h1>\n"
        f"<p class=\"muted\">作成日: {today}</p>\n"
        + render_conclusion(data)
        + render_reasoning(data)
        + render_proposal(data)
        + render_call_to_action(data)
        + "</body>\n</html>\n"
    )


def cmd_render(args: argparse.Namespace) -> int:
    data = load_input(Path(args.input))
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    topic = data.get("topic") or args.topic
    if not topic:
        print("error: input.topic か --topic が必要", file=sys.stderr)
        return 2
    path = out_dir / f"{topic}__client-proposal.html"
    path.write_text(render_document(data), encoding="utf-8")
    print(json.dumps({"written": [str(path)]}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="構造化入力ファイル (yaml or json)")
    parser.add_argument("--topic", help="トピック名 (入力に topic が無い場合)")
    parser.add_argument("--out-dir", default="./out", help="出力先ディレクトリ")
    parser.set_defaults(func=cmd_render)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
