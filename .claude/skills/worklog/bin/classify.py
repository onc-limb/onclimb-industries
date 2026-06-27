#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""classify: raw/*.jsonl を project_id 付きで classified/ へ振り分ける。

分類の手がかり優先順位（worklog_lib.Classifier）:
  ① cwd パス一致 → ② git リポジトリ名 → ③ 本文キーワード → 当たらなければ「未分類」
判定はセッション単位で 1 回行い（同一セッションは同一 cwd のため）、
そのセッションの全エントリに同じ project_id を付与する。
誤分類より未分類を優先する。

出力: classified/<project_id>/YYYY-MM-DD.jsonl  （未分類は classified/_unclassified/）
冪等: 毎回 classified/ を raw/ から再構築する（_unclassified の .gitkeep は残す）。

使い方:
  bin/classify.py                # raw 全体を分類
  bin/classify.py 2026-06-22     # 指定日のみ
"""
import glob
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worklog_lib as W  # noqa: E402


def reset_classified(home):
    cdir = os.path.join(home, "classified")
    if os.path.isdir(cdir):
        for name in os.listdir(cdir):
            p = os.path.join(cdir, name)
            if os.path.isdir(p):
                for f in glob.glob(os.path.join(p, "*.jsonl")):
                    os.remove(f)
    os.makedirs(os.path.join(cdir, "_unclassified"), exist_ok=True)


def main():
    home = W.worklog_home()
    raw_dir = os.path.join(home, "raw")
    cls_dir = os.path.join(home, "classified")
    classifier = W.load_classifier()

    date_filter = sys.argv[1] if len(sys.argv) > 1 else None
    if not date_filter:
        reset_classified(home)
    else:
        # 指定日のみ再分類する場合、その日の既存出力を消してから書き直す（再実行で重複させない）
        for old in glob.glob(os.path.join(cls_dir, "*", "%s.jsonl" % date_filter)):
            os.remove(old)

    pattern = os.path.join(raw_dir, "%s.jsonl" % (date_filter or "*"))
    raw_files = sorted(glob.glob(pattern))
    if not raw_files:
        sys.stderr.write("[classify] 対象 raw なし: %s\n" % pattern)
        return

    counts = {}
    for rf in raw_files:
        date = os.path.basename(rf)[:-6]  # strip .jsonl
        # 1) セッション単位で cwd と本文を集約
        sessions = {}  # sid -> {"cwd":..., "bodies":[...], "entries":[...]}
        with open(rf, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                sid = e.get("session_id") or "_nosession"
                s = sessions.setdefault(sid, {"cwd": None, "source": None, "bodies": [], "entries": []})
                if e.get("cwd") and not s["cwd"]:
                    s["cwd"] = e["cwd"]
                if e.get("source") and not s["source"]:
                    s["source"] = e["source"]
                if e.get("kind") in ("instruction", "response") and len(s["bodies"]) < 30:
                    s["bodies"].append(e.get("body") or "")
                s["entries"].append(e)

        # 2) セッションごとに分類して書き出し
        out_handles = {}

        def handle_for(pid):
            if pid not in out_handles:
                d = os.path.join(cls_dir, pid)
                os.makedirs(d, exist_ok=True)
                out_handles[pid] = open(os.path.join(d, "%s.jsonl" % date), "a", encoding="utf-8")
            return out_handles[pid]

        for sid, s in sessions.items():
            # Claude Desktop（ローカルエージェント）のログは cwd が特殊パスで
            # プロジェクト分類が困難なため、専用の desktop-chat に固定する。
            if s["source"] == "desktop":
                pid, reason = "desktop-chat", "source=desktop"
            else:
                pid, reason = classifier.classify(s["cwd"], s["bodies"])
            out_pid = "_unclassified" if pid == "未分類" else pid
            fh = handle_for(out_pid)
            for e in s["entries"]:
                e["project_id"] = pid
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
            counts[out_pid] = counts.get(out_pid, 0) + len(s["entries"])

        for fh in out_handles.values():
            fh.close()

    summary = ", ".join("%s=%d" % (k, v) for k, v in sorted(counts.items()))
    sys.stderr.write("[classify] %s\n" % (summary or "(0件)"))


if __name__ == "__main__":
    main()
