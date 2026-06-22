#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""archive 本体（archive.sh から呼ばれる）。

要約完了済みの raw/ classified/ を月単位で zip 化し archive/YYYY-MM.zip へ退避する。
- 圧縮後に元ファイルを削除（zip 内には必ず残る＝完全消失しない）。
- 実行前に「未要約のログが残っていないか」をチェックし、残っていれば中断・警告する。
  （reports/{progress,deliverables,knowledge}/<pid>_<date>.md が揃っているかで判定）

使い方:
  bin/archive.sh                 # 当月より前の全月を対象（安全）
  bin/archive.sh 2026-05         # 指定月のみ
  bin/archive.sh 2026-05 --force # 未要約があっても強制実行
  bin/archive.sh --check 2026-05 # 退避せず未要約チェックのみ
"""
import glob
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worklog_lib as W  # noqa: E402

FORMATS = ["progress", "deliverables", "knowledge"]
DATE_RE = re.compile(r"(\d{4}-\d{2})-\d{2}\.jsonl$")


def current_month():
    now = datetime.now(timezone(timedelta(hours=9)))
    return "%04d-%02d" % (now.year, now.month)


def months_in_raw(home):
    months = set()
    for f in glob.glob(os.path.join(home, "raw", "*.jsonl")):
        m = DATE_RE.search(os.path.basename(f))
        if m:
            months.add(m.group(1))
    return sorted(months)


def classified_files_for_month(home, month):
    return sorted(glob.glob(os.path.join(home, "classified", "*", "%s-*.jsonl" % month)))


def raw_files_for_month(home, month):
    return sorted(glob.glob(os.path.join(home, "raw", "%s-*.jsonl" % month)))


def find_unsummarized(home, month):
    """要約レポートが揃っていない (pid, date) を返す。"""
    missing = []
    for cf in classified_files_for_month(home, month):
        pid = os.path.basename(os.path.dirname(cf))
        date = os.path.basename(cf)[:-6]
        lack = [fmt for fmt in FORMATS
                if not os.path.isfile(os.path.join(home, "reports", fmt, "%s_%s.md" % (pid, date)))]
        if lack:
            missing.append((pid, date, lack))
    return missing


def archive_month(home, month, force, check_only):
    raw_files = raw_files_for_month(home, month)
    cls_files = classified_files_for_month(home, month)
    if not raw_files and not cls_files:
        sys.stderr.write("[archive] %s: 対象ファイルなし\n" % month)
        return

    missing = find_unsummarized(home, month)
    if missing:
        sys.stderr.write("[archive] %s: 未要約のログがあります:\n" % month)
        for pid, date, lack in missing:
            sys.stderr.write("    - %s/%s 不足: %s\n" % (pid, date, ",".join(lack)))
        if check_only:
            return
        if not force:
            sys.stderr.write("[archive] %s: 中断（先に summarize するか --force を付けてください）\n" % month)
            return
        sys.stderr.write("[archive] %s: --force のため未要約があっても続行します\n" % month)
    if check_only:
        sys.stderr.write("[archive] %s: 未要約なし（チェックのみ・退避はしません）\n" % month)
        return

    archive_dir = os.path.join(home, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    zip_path = os.path.join(archive_dir, "%s.zip" % month)

    all_files = raw_files + cls_files
    mode = "a" if os.path.isfile(zip_path) else "w"
    with zipfile.ZipFile(zip_path, mode, zipfile.ZIP_DEFLATED) as zf:
        existing = set(zf.namelist())
        for f in all_files:
            arc = os.path.relpath(f, home)
            if arc in existing:
                continue
            zf.write(f, arc)

    # 検証: zip 内に全ファイルが入ったことを確認してから元を削除
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
    removed = 0
    for f in all_files:
        arc = os.path.relpath(f, home)
        if arc in names:
            os.remove(f)
            removed += 1
        else:
            sys.stderr.write("[archive] 警告: zip に %s が入らなかったため削除しません\n" % arc)
    sys.stderr.write("[archive] %s: %s へ退避完了（%d ファイル削除）\n" % (month, zip_path, removed))


def main():
    home = W.worklog_home()
    args = sys.argv[1:]
    force = "--force" in args
    check_only = "--check" in args
    months = [a for a in args if re.fullmatch(r"\d{4}-\d{2}", a)]

    if not months:
        cur = current_month()
        months = [m for m in months_in_raw(home) if m < cur]
        if not months:
            sys.stderr.write("[archive] 退避対象月なし（当月分は安全のため対象外）\n")
            return

    for m in months:
        archive_month(home, m, force, check_only)


if __name__ == "__main__":
    main()
