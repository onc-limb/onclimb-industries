#!/usr/bin/env python3
"""friday-daily-report の報告窓・材料抽出・作成履歴 CLI.

個人の日次作業報告は「前回の報告作成時刻 〜 今回の作成時刻」を対象窓とする
(ウォーターマーク方式)。固定 cutoff を持たないため、金曜夜の作業は自動的に
次に報告を作った日(=翌営業日)の報告に入る。

サブコマンド:
  window   報告窓を算出して JSON 出力(作成履歴の最終エントリ → 窓の始点)
  activity 窓内の worklog events / 生ログを集め、稼働推定の材料を JSON 出力
  commit   報告の確定時に作成履歴(.report-log.jsonl)へ 1 行追記する
           (ユーザーが報告を承認してから呼ぶ。窓の終点が次回の始点になる)

使い方:
  python3 report_tool.py window [--redo]
  python3 report_tool.py activity --start <ISO8601> --end <ISO8601> [--gap-min 45]
  python3 report_tool.py commit --date <YYYY-MM-DD> --start <ISO> --end <ISO> \
      --md <path> --html <path>

作成履歴: <REPORT_DAILY_DIR or repo>/report-daily/.report-log.jsonl
worklog データ: jarvis-worklog の worklog_lib.data_home() に従う(WORKLOG_DATA で上書き可)
"""
import argparse
import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
JST = timezone(timedelta(hours=9), "JST")

# 同一リポジトリ内の jarvis-worklog をデータ源として参照する(スキル間依存は
# この読み取りのみ。worklog 側のスキーマ変更時は本ファイルも合わせて見直す)
WORKLOG_BIN = os.path.join(os.path.dirname(SKILL_DIR), "jarvis-worklog", "bin")
sys.path.insert(0, WORKLOG_BIN)
try:
    import worklog_lib as W
except ImportError:
    W = None


def repo_root():
    try:
        out = subprocess.check_output(
            ["git", "-C", HERE, "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.dirname(SKILL_DIR)))


def out_root():
    return os.environ.get("REPORT_DAILY_DIR") or os.path.join(repo_root(), "report-daily")


def log_path():
    return os.path.join(out_root(), ".report-log.jsonl")


def worklog_home():
    if W is not None:
        return W.data_home()
    env = os.environ.get("WORKLOG_DATA") or os.environ.get("WORKLOG_HOME")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.join(repo_root(), "worklog-data")


def parse_ts(s):
    dt = datetime.fromisoformat(str(s))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def last_log_entry():
    path = log_path()
    if not os.path.exists(path):
        return None
    last = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                last = json.loads(line)
            except json.JSONDecodeError:
                continue
    return last


def cmd_window(args):
    now = datetime.now(JST).replace(microsecond=0)
    prev = last_log_entry()
    if prev and args.redo:
        # やり直し: 直前の報告の窓の始点から引き直す(前回分を作り直して上書き)
        start = parse_ts(prev["window_start"])
        mode = "redo"
    elif prev:
        start = parse_ts(prev["window_end"])
        mode = "normal"
    else:
        # 初回はウォーターマークが無いので当日 0:00 から(必要なら対話で調整)
        start = now.replace(hour=0, minute=0, second=0)
        mode = "first"
    print(json.dumps({
        "mode": mode,
        "report_date": now.date().isoformat(),
        "window_start": start.isoformat(),
        "window_end": now.isoformat(),
        "previous": prev,
    }, ensure_ascii=False, indent=2))


def iter_jsonl(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def dates_between(start, end):
    d = start.date()
    while d <= end.date():
        yield d.isoformat()
        d += timedelta(days=1)


def cmd_activity(args):
    start = parse_ts(args.start)
    end = parse_ts(args.end)
    home = worklog_home()

    events = []
    stamps = []
    sources = {}
    for day in dates_between(start, end):
        for ev in iter_jsonl(os.path.join(home, "events", day + ".jsonl")):
            try:
                ts = parse_ts(ev.get("ts"))
            except (ValueError, TypeError):
                continue
            if start < ts <= end:
                events.append(ev)
        for row in iter_jsonl(os.path.join(home, "raw", day + ".jsonl")):
            try:
                ts = parse_ts(row.get("ts"))
            except (ValueError, TypeError):
                continue
            if start < ts <= end:
                stamps.append(ts)
                src = row.get("source") or "?"
                sources[src] = sources.get(src, 0) + 1

    stamps.sort()
    gaps = []
    gap_min = timedelta(minutes=args.gap_min)
    for a, b in zip(stamps, stamps[1:]):
        if b - a >= gap_min:
            gaps.append({
                "from": a.isoformat(),
                "to": b.isoformat(),
                "minutes": int((b - a).total_seconds() // 60),
            })

    by_project = {}
    for ev in events:
        by_project.setdefault(ev.get("project") or "?", []).append(ev)

    print(json.dumps({
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "activity": {
            "entries": len(stamps),
            "first": stamps[0].isoformat() if stamps else None,
            "last": stamps[-1].isoformat() if stamps else None,
            "sources": sources,
            # 休憩の候補(gap_min 分以上ログが途切れた区間)。確定はユーザーとの対話で行う
            "gaps": gaps,
        },
        "events": events,
        "events_by_project": {k: len(v) for k, v in by_project.items()},
    }, ensure_ascii=False, indent=2))


def cmd_commit(args):
    entry = {
        "report_date": args.date,
        "window_start": parse_ts(args.start).isoformat(),
        "window_end": parse_ts(args.end).isoformat(),
        "created_at": datetime.now(JST).replace(microsecond=0).isoformat(),
        "out_md": args.md,
        "out_html": args.html,
    }
    path = log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = (json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            os.write(fd, line)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    print("[report-log] {} window {} -> {}".format(args.date, entry["window_start"], entry["window_end"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("window", help="報告窓を算出").add_argument(
        "--redo", action="store_true", help="直前の報告の窓を引き直す(作り直し用)")

    p_act = sub.add_parser("activity", help="窓内の events/生ログを集約")
    p_act.add_argument("--start", required=True)
    p_act.add_argument("--end", required=True)
    p_act.add_argument("--gap-min", type=int, default=45, help="休憩候補とみなす無活動分数(既定 45)")

    p_com = sub.add_parser("commit", help="報告確定を作成履歴に追記")
    p_com.add_argument("--date", required=True)
    p_com.add_argument("--start", required=True)
    p_com.add_argument("--end", required=True)
    p_com.add_argument("--md", required=True)
    p_com.add_argument("--html", required=True)

    args = ap.parse_args()
    {"window": cmd_window, "activity": cmd_activity, "commit": cmd_commit}[args.cmd](args)


if __name__ == "__main__":
    main()
