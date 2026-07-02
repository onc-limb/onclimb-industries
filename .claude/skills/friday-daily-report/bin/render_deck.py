#!/usr/bin/env python3
"""report-deck Stage2 レンダラー.

payload(JSON) + templates/deck.html から、フォーマット固定の日次報告スライド HTML を生成する。
脱専門用語の変換は呼び出し側(エージェント)が済ませた前提。ここは決定論的な差し込みのみ。

使い方:
    python3 render_deck.py --in payload.json
    cat payload.json | python3 render_deck.py
    python3 render_deck.py --in payload.json --stdout   # 書き込まず標準出力に

payload schema:
{
  "date": "2026-06-27",              # YYYY-MM-DD 必須(出力パス決定用。形式を検証する)
  "date_label": "6/23〜6/27",        # 任意。表紙・タイトル表示用(省略時は date を表示)
  "reporter": "○○",
  "highlights": ["...", "..."],
  "projects": [                      # 1件以上必須
    {
      "name": "会員向けサービス",
      "did":    [{"status": "done|wip|todo|pause", "text": "..."}, "テキストだけでも可"],
      "status": ["..."],             # status/next/ask は常に出力(空は「なし」)
      "next":   ["..."],
      "ask":    ["..."]
    }
  ]
}

出力先: <REPORT_DECK_DIR or repo>/report-deck/<YYYY-MM>/<date>.html
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
TEMPLATE = os.path.join(SKILL_DIR, "templates", "deck.html")

STATUS = {
    "done":  ("完了",   "status done"),
    "wip":   ("進行中", "status"),
    "todo":  ("着手のみ", "status"),
    "pause": ("中断",   "status"),
}


def repo_root():
    try:
        out = subprocess.check_output(
            ["git", "-C", HERE, "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        # git 配下でなければスキルから 3 つ上 (.claude/skills/friday-daily-report -> repo)
        return os.path.dirname(os.path.dirname(os.path.dirname(SKILL_DIR)))


def esc(s):
    return html.escape(str(s), quote=False)


def li_plain(items):
    if not items:
        return "        <li>なし</li>"
    return "\n".join("        <li>{}</li>".format(esc(x)) for x in items)


def li_did(items):
    if not items:
        return "        <li>なし</li>"
    out = []
    for it in items:
        if isinstance(it, dict):
            text = it.get("text", "")
            st = it.get("status")
            if st in STATUS:
                label, cls = STATUS[st]
                out.append('        <li><span class="{}">{}</span>{}</li>'.format(
                    cls, label, esc(text)))
            else:
                if st is not None:
                    print("warning: 未知の status {!r} を無視しました (text: {})".format(
                        st, text), file=sys.stderr)
                out.append("        <li>{}</li>".format(esc(text)))
        else:
            out.append("        <li>{}</li>".format(esc(it)))
    return "\n".join(out)


def group(title, body_html, ask=False):
    cls = "group ask" if ask else "group"
    return (
        '    <div class="{cls}">\n'
        '      <div class="h">{title}</div>\n'
        '      <ul>\n{body}\n      </ul>\n'
        '    </div>'
    ).format(cls=cls, title=esc(title), body=body_html)


def render_project(p):
    blocks = [group("やったこと", li_did(p.get("did", [])))]
    blocks.append(group("今どうなっているか", li_plain(p.get("status", []))))
    blocks.append(group("この先", li_plain(p.get("next", []))))
    blocks.append(group("ご相談", li_plain(p.get("ask", [])), ask=True))
    return (
        '  <section class="slide">\n'
        '    <span class="label">案件</span>\n'
        '    <h2>{name}</h2>\n\n'
        '{blocks}\n'
        '  </section>'
    ).format(name=esc(p.get("name", "(無題)")), blocks="\n\n".join(blocks))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", help="payload JSON path (省略時 stdin)")
    ap.add_argument("--stdout", action="store_true", help="ファイルに書かず標準出力へ")
    args = ap.parse_args()

    raw = open(args.infile, encoding="utf-8").read() if args.infile else sys.stdin.read()
    data = json.loads(raw)

    date = data["date"]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
        sys.exit("error: date は YYYY-MM-DD 形式で指定してください (got: {!r})".format(date))
    date_label = data.get("date_label") or date
    reporter = data.get("reporter", "")
    highlights = data.get("highlights", [])
    projects = data.get("projects", [])
    if not projects:
        sys.exit("error: projects が空です。案件を1件以上含めてください")

    tpl = open(TEMPLATE, encoding="utf-8").read()

    # 1) 表紙・タイトルのプレースホルダ(表示は date_label、出力パスは date)
    tpl = tpl.replace("{{date}}", esc(date_label)).replace("{{reporter}}", esc(reporter))

    # 2) サマリの差し替え (HL_START ... HL_END の間)
    hl_html = "\n      <ul>\n{}\n      </ul>\n      ".format(li_plain(highlights))
    tpl = re.sub(
        r"(<!-- HL_START.*?-->).*?(<!-- HL_END -->)",
        lambda m: m.group(1) + hl_html + m.group(2),
        tpl, count=1, flags=re.DOTALL,
    )

    # 3) 案件スライドの差し替え (PROJECT_SLIDES ここから ... ここまで の間)
    proj_html = "\n" + "\n\n".join(render_project(p) for p in projects) + "\n  "
    tpl = re.sub(
        r"(<!-- PROJECT_SLIDES ここから.*?-->).*?(<!-- PROJECT_SLIDES ここまで -->)",
        lambda m: m.group(1) + proj_html + m.group(2),
        tpl, count=1, flags=re.DOTALL,
    )

    if args.stdout:
        sys.stdout.write(tpl)
        return

    base = os.environ.get("REPORT_DECK_DIR") or os.path.join(repo_root(), "report-deck")
    month = date[:7]  # YYYY-MM
    out_dir = os.path.join(base, month)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "{}.html".format(date))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(tpl)
    print(out_path)


if __name__ == "__main__":
    main()
