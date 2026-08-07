#!/usr/bin/env python3
"""worklog record — エージェント申告の構造化イベントを events/<日付>.jsonl に追記する。

作業の区切り(milestone)と障害遭遇(blocker)の 2 種を、複数エージェントの
並行書き込みに安全な形（flock + O_APPEND の単一 write）で記録する。
マスキングは collect を通らない経路のため、ここで適用する。

スキーマ（Issue: issues/2026-08-07_worklog-event-recorder.md の契約。
変更時は MCP ラッパー・summarize 側と同時に揃えること）:
  ts / agent / project / kind / background / did / blocker / result / refs
"""
import argparse
import fcntl
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worklog_lib as W  # noqa: E402

KINDS = ("milestone", "blocker")


def record_event(kind, project=None, agent=None, background=None, did=None,
                 blocker=None, result=None, refs=None, redactor=None):
    """イベントを 1 件記録し (path, event) を返す。CLI と MCP ラッパー共用の入口。

    必須フィールド検証もここで行う（CLI は argparse でも弾くが、MCP 経由は
    この検証だけが砦になる）。"""
    if kind not in KINDS:
        raise ValueError("kind は %s のいずれか: %r" % ("/".join(KINDS), kind))
    if kind == "milestone" and not did:
        raise ValueError("milestone には did（実施内容）が必須です")
    if kind == "blocker" and not blocker:
        raise ValueError("blocker には blocker（症状・エラー原文）が必須です")

    redactor = redactor or W.load_redactor()
    ts = datetime.now(W.JST).isoformat(timespec="seconds")
    ev = {
        "ts": ts,
        "agent": agent or "claude-code",
        "project": project or "?",
        "kind": kind,
    }
    for field, val in (("background", background), ("did", did),
                       ("blocker", blocker), ("result", result)):
        if val:
            ev[field] = redactor.apply(val)
    clean_refs = [redactor.apply(r) for r in (refs or []) if r]
    if clean_refs:
        ev["refs"] = clean_refs

    events_dir = os.path.join(W.data_home(), "events")
    os.makedirs(events_dir, exist_ok=True)
    path = os.path.join(events_dir, "%s.jsonl" % ts[:10])
    append_event(path, ev)
    return path, ev


def append_event(path, ev):
    """1 行 1 JSON を flock + O_APPEND の単一 write で追記する。

    行全体を 1 回の os.write() で書き切ることで、ロック非対応の読み手からも
    行の途中が観測されないようにする（flock は書き手同士の直列化）。
    """
    line = (json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            os.write(fd, line)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def build_parser():
    p = argparse.ArgumentParser(
        prog="record.py",
        description="作業イベント(milestone/blocker)を events/<日付>.jsonl に追記する")
    sub = p.add_subparsers(dest="kind", required=True)

    def common(sp):
        # ASSUMPTION: project は妥当性検証しない（誤分類より未分類優先の原則。
        # 未登録プロジェクトの作業も弾かず、特定できないときの既定値だけ "?" とする）
        sp.add_argument("--project", default="?",
                        help="projects.yaml の id。特定できなければ省略（既定 ?）")
        sp.add_argument("--agent", default="claude-code",
                        help="記録主体 (claude-code / codex など。既定 claude-code)")
        sp.add_argument("--result", help="結果・現状")
        sp.add_argument("--refs", action="append", metavar="REF",
                        help="関連パス・PR URL 等（複数指定可）")

    sp_m = sub.add_parser("milestone", help="作業の区切りの申告（背景・実施・結果）")
    common(sp_m)
    sp_m.add_argument("--background", help="なぜやったか・文脈")
    sp_m.add_argument("--did", required=True, help="実施内容")
    sp_m.add_argument("--blocker", help="途中で遭遇した障害（あれば）")

    sp_b = sub.add_parser("blocker", help="障害遭遇の即時申告（エラー原文を要約せず残す）")
    common(sp_b)
    sp_b.add_argument("--background", help="何をしていて遭遇したか")
    sp_b.add_argument("--blocker", required=True,
                      help="症状・エラー原文（原料保全のため要約しない）")
    sp_b.add_argument("--did", help="試したこと（あれば）")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    path, ev = record_event(
        kind=args.kind, project=args.project, agent=args.agent,
        background=getattr(args, "background", None),
        did=getattr(args, "did", None),
        blocker=getattr(args, "blocker", None),
        result=args.result, refs=args.refs)
    print("[record] %s project=%s agent=%s -> %s"
          % (ev["kind"], ev["project"], ev["agent"], path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
