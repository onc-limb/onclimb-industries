#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""suggest_projects: classified/_unclassified に溜まったログを調査し、
projects.yaml に未登録のプロジェクト候補を JSON で提案する（読み取り専用）。

classify は「誤分類より未分類優先」のため、projects.yaml に定義の無いプロジェクトは
_unclassified に落ちる。本ツールはその _unclassified を cwd / git リポジトリ単位で集計し、
「projects.yaml にこういう id で足せばよい」という候補を提示する。

実際の追記はしない（Claude が候補を確認し、ユーザー合意のうえ projects.yaml を編集する）。

使い方:
  bin/suggest_projects.py             # _unclassified 全体から候補を出す
  bin/suggest_projects.py 2026-06-27  # 指定日のみ

出力(JSON): { "candidates": [ {id, path_glob, repo, entries, sessions, dates, sample_bodies}, ... ] }
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worklog_lib as W  # noqa: E402


def git_toplevel(cwd):
    """cwd から上方向に .git を探し、そのディレクトリ(リポジトリのトップ)を返す。"""
    d = cwd or ""
    while d and d != os.path.dirname(d):
        if os.path.isdir(os.path.join(d, ".git")):
            return d
        d = os.path.dirname(d)
    return None


def known_keys(cfg):
    """既に projects.yaml で押さえている path_glob / repo / id を集める。"""
    ids, globs, repos = set(), set(), set()
    for p in cfg.get("projects") or []:
        ids.add(p.get("id"))
        for g in (p.get("path_globs") or []):
            globs.add(g.rstrip("/"))
        for r in (p.get("repos") or []):
            repos.add(r)
    return ids, globs, repos


def main():
    date_filter = sys.argv[1] if len(sys.argv) > 1 else None
    home = W.worklog_home()
    cfg = W.load_config("projects.yaml")
    ids, known_globs, known_repos = known_keys(cfg)

    unc_dir = os.path.join(home, "classified", "_unclassified")
    pattern = os.path.join(unc_dir, "%s.jsonl" % (date_filter or "*"))

    # cwd 単位で集計
    groups = {}  # cwd -> {entries, sessions:set, dates:set, bodies:[]}
    for jf in sorted(glob.glob(pattern)):
        date = os.path.basename(jf)[:-6]
        with open(jf, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                cwd = e.get("cwd")
                if not cwd:
                    continue
                g = groups.setdefault(cwd, {"entries": 0, "sessions": set(), "dates": set(), "bodies": []})
                g["entries"] += 1
                if e.get("session_id"):
                    g["sessions"].add(e["session_id"])
                g["dates"].add(date)
                if e.get("kind") in ("instruction", "response") and len(g["bodies"]) < 3:
                    b = (e.get("body") or "").strip().replace("\n", " ")
                    if b:
                        g["bodies"].append(b[:160])

    candidates = []
    for cwd, g in sorted(groups.items(), key=lambda kv: -kv[1]["entries"]):
        top = git_toplevel(cwd)
        path_glob = top or cwd
        repo = os.path.basename(top) if top else (W.git_repo_name(cwd) or os.path.basename(cwd))
        # 既に projects.yaml で押さえているなら候補にしない（誤って未分類になった残骸対策）
        if path_glob.rstrip("/") in known_globs or repo in known_repos:
            continue
        sug_id = repo
        candidates.append({
            "suggested_id": sug_id,
            "id_conflict": sug_id in ids,   # 既存 id と衝突するなら別名を要検討
            "cwd": cwd,
            "path_glob": path_glob,
            "repo": repo,
            "is_git_repo": top is not None,
            "entries": g["entries"],
            "sessions": len(g["sessions"]),
            "dates": sorted(g["dates"]),
            "sample_bodies": g["bodies"],
        })

    print(json.dumps({
        "date": date_filter,
        "unclassified_dir": unc_dir,
        "found": len(candidates),
        "candidates": candidates,
        "note": "実際の追記はしない。Claude が候補を確認し、ユーザー合意のうえ projects.yaml を編集して再分類する。",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
