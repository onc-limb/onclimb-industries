#!/usr/bin/env python3
"""report-record Stage1 入力ロケーター.

指定日(+任意で案件)について、報告記録の生成に必要な入力を集めて JSON で出力する。
- worklog の project digest (主入力)
- 同案件の前日までの記録 (継続性のため)
- 記録の出力先パス
- _unclassified フラグ (報告に含めるかは都度ユーザー確認するため明示する)

使い方:
    python3 locate.py 2026-06-27            # その日の digest がある全案件
    python3 locate.py 2026-06-27 jarvis     # 案件を限定
"""
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SUFFIX_LEN = len("_YYYY-MM-DD.md")  # = 14


def repo_root():
    try:
        out = subprocess.check_output(
            ["git", "-C", HERE, "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.dirname(SKILL_DIR)))


def main():
    if len(sys.argv) < 2 or not DATE_RE.match(sys.argv[1]):
        sys.exit("usage: locate.py YYYY-MM-DD [project]")
    date = sys.argv[1]
    only = sys.argv[2] if len(sys.argv) > 2 else None

    repo = repo_root()
    worklog_data = os.environ.get("WORKLOG_DATA") or os.path.join(repo, "worklog-data")
    record_dir = os.environ.get("REPORT_RECORD_DIR") or os.path.join(repo, "report-record")

    digest_dir = os.path.join(worklog_data, "digests", "project")
    pattern = os.path.join(digest_dir, "*_{}.md".format(date))

    projects = []
    for path in sorted(glob.glob(pattern)):
        name = os.path.basename(path)[:-SUFFIX_LEN]  # 末尾 _<date>.md を除去
        if only and name != only:
            continue
        # 同案件の前日までの記録のうち最新を拾う
        prev = None
        recs = sorted(glob.glob(os.path.join(record_dir, name, "*.md")))
        for r in recs:
            d = os.path.basename(r)[:-3]  # strip .md
            if DATE_RE.match(d) and d < date:
                prev = r  # sorted 昇順なので最後に残るのが最新
        projects.append({
            "project": name,
            "is_unclassified": name.startswith("_unclassified"),
            "digest": path,
            "prev_record": prev,
            "record_out": os.path.join(record_dir, name, "{}.md".format(date)),
        })

    print(json.dumps({
        "date": date,
        "repo": repo,
        "worklog_data": worklog_data,
        "record_dir": record_dir,
        "found": len(projects),
        "projects": projects,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
