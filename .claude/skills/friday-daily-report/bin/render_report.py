#!/usr/bin/env python3
"""個人の日次作業報告レンダラー(Markdown + HTML を同時生成).

payload(JSON) から、同一内容の Markdown(メール/チャット貼り付け用)と
自己完結 HTML(印刷・配布用)を生成する。内容の整形・対話確定は呼び出し側
(エージェント)が済ませた前提。ここは決定論的な差し込みのみ。

使い方:
    python3 render_report.py --in payload.json
    python3 render_report.py --in payload.json --stdout md    # 書き込まず確認
    python3 render_report.py --in payload.json --stdout html

payload schema:
{
  "date": "2026-08-08",                    # 報告日 YYYY-MM-DD 必須
  "reporter": "担当者名",
  "client": "案件・契約名",                 # 任意
  "period": {"start": "2026-08-07T18:12+09:00",   # 対象期間(報告窓)必須
             "end":   "2026-08-08T17:03+09:00"},
  "hours": {"start": "09:12", "end": "17:03",     # 稼働情報 必須
            "breaks": [{"start": "12:00", "end": "13:00"}],  # 任意
            "note": "前日夜の作業 1.5h を含む"},               # 任意
  "tasks": [                               # 1件以上必須
    {"title": "ログイン画面の実装", "ticket": "PROJ-123",     # ticket 任意
     "kind": "planned|unplanned",           # planned=予定タスク(既定)/unplanned=当日突発
     "status": "done|wip|todo|pause",
     "did": "どのような作業をしたか(必須。1〜2行で簡潔に)",
     "result": "どういう結果・状況になったか",                 # 任意
     "links": ["PR/チケット等の URL"],       # 任意。ファイルパス・関数名等の実装詳細は書かない
     "remaining": "あと0.5日",              # 任意(進行中のみ)
     "plan_gap": "仕様確認に半日要したため0.5日遅れ"}          # 任意(ズレ無しは省略)
  ],
  "blockers": [{"text": "詰まっている事項", "waiting_on": "誰の何を待っているか",
                "impact": "スケジュールへの影響"}],            # 空可
  "asks":     [{"text": "確認したい事項", "due": "8/12中に回答希望"}],  # 空可
  "decisions": ["今日決まったこと・この認識で進めます"],        # 空可
  "tomorrow":  ["翌営業日に着手する予定のタスク"],              # 空可(空は要再考)
  "notes":     ["休暇予定・稼働変更などの連絡"]                 # 空可
}

実稼働時間は start/end/breaks から自動計算する(手計算のミスを排除)。
出力先: <REPORT_DAILY_DIR or repo>/report-daily/<YYYY-MM>/<date>.md と .html
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
TEMPLATE = os.path.join(SKILL_DIR, "templates", "report.html")

STATUS = {
    "done": "完了",
    "wip": "進行中",
    "todo": "未着手",
    "pause": "中断",
}
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]


def repo_root():
    try:
        out = subprocess.check_output(
            ["git", "-C", HERE, "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.dirname(SKILL_DIR)))


def esc(s):
    return html.escape(str(s), quote=False)


def parse_hm(s):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(s).strip())
    if not m:
        sys.exit("error: 時刻は HH:MM 形式で指定してください (got: {!r})".format(s))
    return int(m.group(1)) * 60 + int(m.group(2))


def fmt_minutes(total):
    h, m = divmod(int(total), 60)
    return "{}時間{:02d}分".format(h, m)


def span_minutes(start, end):
    a, b = parse_hm(start), parse_hm(end)
    if b < a:
        b += 24 * 60  # 日をまたぐ稼働(深夜作業)
    return b - a


def fmt_period_ts(s):
    dt = datetime.fromisoformat(str(s))
    return dt.strftime("%m/%d %H:%M")


def date_label(date):
    dt = datetime.strptime(date, "%Y-%m-%d")
    return "{}({})".format(date, WEEKDAYS[dt.weekday()])


def work_summary(hours):
    """稼働情報から (開始, 終了, 休憩合計, 実稼働, 休憩内訳) を計算する。"""
    start, end = hours["start"], hours["end"]
    breaks = hours.get("breaks", [])
    brk_total = sum(span_minutes(b["start"], b["end"]) for b in breaks)
    worked = span_minutes(start, end) - brk_total
    if worked < 0:
        sys.exit("error: 休憩合計が稼働時間を超えています")
    detail = "、".join("{}〜{}".format(b["start"], b["end"]) for b in breaks)
    return start, end, brk_total, worked, detail


def task_label(t):
    label = t.get("title", "(無題)")
    if t.get("ticket"):
        label += "({})".format(t["ticket"])
    return label


def status_of(t):
    st = t.get("status")
    if st not in STATUS:
        sys.exit("error: 未知の status {!r} (done/wip/todo/pause のいずれか)".format(st))
    return STATUS[st]


def split_tasks(tasks):
    """予定タスクと突発タスクに分ける(表示順もこの順で固定)。"""
    planned, unplanned = [], []
    for t in tasks:
        kind = t.get("kind", "planned")
        if kind == "planned":
            planned.append(t)
        elif kind == "unplanned":
            unplanned.append(t)
        else:
            sys.exit("error: 未知の kind {!r} (planned/unplanned のいずれか)".format(kind))
    return planned, unplanned


# ---------------------------------------------------------------- Markdown

def md_items(items, empty="なし"):
    if not items:
        return "- {}".format(empty)
    return "\n".join("- {}".format(x) for x in items)


def render_md(data):
    date = data["date"]
    period = "{} 〜 {}".format(
        fmt_period_ts(data["period"]["start"]), fmt_period_ts(data["period"]["end"]))
    start, end, brk, worked, brk_detail = work_summary(data["hours"])

    out = []
    out.append("# 日次作業報告 {}".format(date_label(date)))
    out.append("")
    out.append("- 報告者: {}".format(data.get("reporter", "")))
    if data.get("client"):
        out.append("- 案件: {}".format(data["client"]))
    out.append("- 対象期間: {}".format(period))
    out.append("")

    out.append("## 1. 稼働情報")
    out.append("")
    out.append("| 開始 | 終了 | 休憩 | 実稼働 |")
    out.append("|---|---|---|---|")
    out.append("| {} | {} | {} | {} |".format(start, end, fmt_minutes(brk), fmt_minutes(worked)))
    if brk_detail:
        out.append("")
        out.append("- 休憩内訳: {}".format(brk_detail))
    if data["hours"].get("note"):
        out.append("- 備考: {}".format(data["hours"]["note"]))
    out.append("")

    planned, unplanned = split_tasks(data["tasks"])

    out.append("## 2. 進捗状況")
    out.append("")
    out.append("| タスク | 区分 | 状態 | 残作業見込み | 予定とのズレ |")
    out.append("|---|---|---|---|---|")
    for kind_label, group_tasks in (("予定", planned), ("突発", unplanned)):
        for t in group_tasks:
            out.append("| {} | {} | {} | {} | {} |".format(
                task_label(t), kind_label, status_of(t),
                t.get("remaining", "—"), t.get("plan_gap", "—")))
    out.append("")

    out.append("## 3. 本日の作業内容")
    out.append("")
    for heading, group_tasks in (("予定していたタスク", planned), ("突発で発生したタスク", unplanned)):
        out.append("### {}".format(heading))
        out.append("")
        if not group_tasks:
            out.append("- なし")
        for t in group_tasks:
            out.append("- **{}【{}】**".format(task_label(t), status_of(t)))
            out.append("  - 【作業】")
            out.append("    {}".format(t["did"]))
            if t.get("result"):
                out.append("  - 【結果】")
                out.append("    {}".format(t["result"]))
            for link in t.get("links", []):
                out.append("  - {}".format(link))
        out.append("")

    out.append("## 4. 課題・ブロッカー")
    out.append("")
    blockers = []
    for b in data.get("blockers", []):
        line = b["text"]
        if b.get("waiting_on"):
            line += "(待ち先: {})".format(b["waiting_on"])
        if b.get("impact"):
            line += " — 影響: {}".format(b["impact"])
        blockers.append(line)
    out.append(md_items(blockers))
    out.append("")

    out.append("## 5. 相談・確認事項")
    out.append("")
    asks = []
    for a in data.get("asks", []):
        line = a["text"]
        if a.get("due"):
            line += "(回答希望: {})".format(a["due"])
        asks.append(line)
    out.append(md_items(asks))
    out.append("")

    out.append("## 6. 決定事項・認識合わせ")
    out.append("")
    out.append(md_items(data.get("decisions", [])))
    out.append("")

    out.append("## 7. 翌営業日の予定")
    out.append("")
    out.append(md_items(data.get("tomorrow", [])))
    out.append("")

    out.append("## 8. その他連絡")
    out.append("")
    out.append(md_items(data.get("notes", [])))
    out.append("")
    return "\n".join(out)


# -------------------------------------------------------------------- HTML

def ul(items, empty="なし"):
    if not items:
        return "      <ul><li>{}</li></ul>".format(empty)
    return "      <ul>\n{}\n      </ul>".format(
        "\n".join("        <li>{}</li>".format(x) for x in items))


def section(num, title, body, ask=False):
    cls = "sec ask" if ask else "sec"
    return (
        '    <section class="{cls}">\n'
        '      <h2><span class="num">{num}</span>{title}</h2>\n'
        '{body}\n'
        '    </section>'
    ).format(cls=cls, num=num, title=esc(title), body=body)


def render_html(data):
    date = data["date"]
    period = "{} 〜 {}".format(
        fmt_period_ts(data["period"]["start"]), fmt_period_ts(data["period"]["end"]))
    start, end, brk, worked, brk_detail = work_summary(data["hours"])

    secs = []

    rows = ("        <tr><th>開始</th><th>終了</th><th>休憩</th><th>実稼働</th></tr>\n"
            "        <tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>").format(
        esc(start), esc(end), esc(fmt_minutes(brk)), esc(fmt_minutes(worked)))
    body = "      <table>\n{}\n      </table>".format(rows)
    extras = []
    if brk_detail:
        extras.append("休憩内訳: {}".format(esc(brk_detail)))
    if data["hours"].get("note"):
        extras.append("備考: {}".format(esc(data["hours"]["note"])))
    if extras:
        body += "\n      <p class=\"sub\">{}</p>".format(" / ".join(extras))
    secs.append(section(1, "稼働情報", body))

    def task_list(group_tasks):
        if not group_tasks:
            return "      <ul><li>なし</li></ul>"
        items = []
        for t in group_tasks:
            subs = ['<div class="lbl">【作業】</div><div class="detail">{}</div>'.format(
                esc(t["did"]))]
            if t.get("result"):
                subs.append('<div class="lbl">【結果】</div><div class="detail">{}</div>'.format(
                    esc(t["result"])))
            subs += ['<div><a href="{0}">{0}</a></div>'.format(html.escape(str(u), quote=True))
                     for u in t.get("links", [])]
            items.append(
                '        <li><b>{title}</b><span class="status st-{st}">{label}</span>'
                '\n          <div class="subs">{subs}</div></li>'.format(
                    st=t.get("status"), label=status_of(t), title=esc(task_label(t)),
                    subs="".join(subs)))
        return "      <ul class=\"tasks\">\n{}\n      </ul>".format("\n".join(items))

    planned, unplanned = split_tasks(data["tasks"])

    rows = ["        <tr><th>タスク</th><th>区分</th><th>状態</th><th>残作業見込み</th><th>予定とのズレ</th></tr>"]
    for kind_label, group_tasks in (("予定", planned), ("突発", unplanned)):
        for t in group_tasks:
            rows.append("        <tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                esc(task_label(t)), kind_label, status_of(t),
                esc(t.get("remaining", "—")), esc(t.get("plan_gap", "—"))))
    secs.append(section(2, "進捗状況", "      <table>\n{}\n      </table>".format("\n".join(rows))))

    body = ("      <h3>予定していたタスク</h3>\n{}\n"
            "      <h3>突発で発生したタスク</h3>\n{}").format(
        task_list(planned), task_list(unplanned))
    secs.append(section(3, "本日の作業内容", body))

    blockers = []
    for b in data.get("blockers", []):
        line = esc(b["text"])
        if b.get("waiting_on"):
            line += "(待ち先: {})".format(esc(b["waiting_on"]))
        if b.get("impact"):
            line += " — 影響: {}".format(esc(b["impact"]))
        blockers.append(line)
    secs.append(section(4, "課題・ブロッカー", ul(blockers)))

    asks = []
    for a in data.get("asks", []):
        line = esc(a["text"])
        if a.get("due"):
            line += "(回答希望: {})".format(esc(a["due"]))
        asks.append(line)
    secs.append(section(5, "相談・確認事項", ul(asks), ask=True))

    secs.append(section(6, "決定事項・認識合わせ", ul([esc(x) for x in data.get("decisions", [])])))
    secs.append(section(7, "翌営業日の予定", ul([esc(x) for x in data.get("tomorrow", [])])))
    secs.append(section(8, "その他連絡", ul([esc(x) for x in data.get("notes", [])])))

    tpl = open(TEMPLATE, encoding="utf-8").read()
    tpl = (tpl.replace("{{date}}", esc(date_label(date)))
              .replace("{{reporter}}", esc(data.get("reporter", "")))
              .replace("{{client}}", esc(data.get("client", "")))
              .replace("{{period}}", esc(period)))
    tpl = re.sub(
        r"(<!-- SECTIONS_START -->).*?(<!-- SECTIONS_END -->)",
        lambda m: m.group(1) + "\n" + "\n\n".join(secs) + "\n    " + m.group(2),
        tpl, count=1, flags=re.DOTALL,
    )
    return tpl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", help="payload JSON path (省略時 stdin)")
    ap.add_argument("--stdout", choices=["md", "html"], help="ファイルに書かず標準出力へ")
    args = ap.parse_args()

    raw = open(args.infile, encoding="utf-8").read() if args.infile else sys.stdin.read()
    data = json.loads(raw)

    date = data.get("date")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
        sys.exit("error: date は YYYY-MM-DD 形式で指定してください (got: {!r})".format(date))
    for key in ("period", "hours"):
        if key not in data:
            sys.exit("error: {} がありません".format(key))
    if not data.get("tasks"):
        sys.exit("error: tasks が空です。作業内容を1件以上含めてください")
    for t in data["tasks"]:
        if not t.get("did"):
            sys.exit("error: 各タスクに did(どのような作業をしたか)が必要です (task: {!r})".format(
                t.get("title")))

    md = render_md(data)
    page = render_html(data)

    if args.stdout:
        sys.stdout.write(md if args.stdout == "md" else page)
        return

    base = os.environ.get("REPORT_DAILY_DIR") or os.path.join(repo_root(), "report-daily")
    out_dir = os.path.join(base, date[:7])
    os.makedirs(out_dir, exist_ok=True)
    md_path = os.path.join(out_dir, date + ".md")
    html_path = os.path.join(out_dir, date + ".html")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page)
    print(md_path)
    print(html_path)


if __name__ == "__main__":
    main()
