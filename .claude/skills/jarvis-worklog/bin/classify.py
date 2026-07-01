#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""classify: raw/*.jsonl を project_id 付きで classified/ へ振り分ける。

分類の手がかり優先順位（セッション単位で 1 回判定）:
  ① cwd パス一致 → ② git リポジトリ名      … 決定論（確実）
  ③ LLM 判定（claude -p / Sonnet）          … ①② を外したセッションのみ、まとめて 1 回
  ④ 本文キーワード部分一致                  … claude 不在/失敗/--no-llm 時のオフライン fallback
  どれも当たらなければ「未分類」（誤分類より未分類を優先）

LLM は既知プロジェクト一覧（id/パス/キーワード/説明）と各セッションの cwd・本文抜粋を見て、
確信が持てる場合だけ既知 id を返す。確信が低い/未知のものは「未分類」に倒す。
未分類に未登録プロジェクトが残った場合は suggest_projects.py で候補を出し、登録を確認する。

出力: classified/<project_id>/YYYY-MM-DD.jsonl  （未分類は classified/_unclassified/）
冪等: 毎回 classified/ を raw/ から再構築する（_unclassified の .gitkeep は残す）。

使い方:
  bin/classify.py                # raw 全体を分類
  bin/classify.py 2026-06-22     # 指定日のみ
  bin/classify.py --no-llm       # LLM を使わず決定論+キーワードのみ（cron 無人運用・検証用）
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worklog_lib as W  # noqa: E402

# LLM 判定の設定
LLM_MODEL = "sonnet"          # 現行 Sonnet に追従（summarize と同方針）
LLM_CONFIDENCE_MIN = 0.6      # この確信度未満は採用せず「未分類」に倒す
LLM_BODY_LIMIT = 1500         # 1 セッションあたり LLM に渡す本文抜粋の最大文字数
LLM_MAX_SESSIONS = 40         # 1 回の claude 呼び出しに載せるセッション数の上限（超過分はチャンク分割）


def reset_classified(home):
    cdir = os.path.join(home, "classified")
    if os.path.isdir(cdir):
        for name in os.listdir(cdir):
            p = os.path.join(cdir, name)
            if os.path.isdir(p):
                for f in glob.glob(os.path.join(p, "*.jsonl")):
                    os.remove(f)
    os.makedirs(os.path.join(cdir, "_unclassified"), exist_ok=True)


def _session_excerpt(bodies):
    """セッション本文を LLM 用に 1 本へまとめてトリムする。"""
    blob = "\n".join(b.strip() for b in bodies if b and b.strip())
    if len(blob) > LLM_BODY_LIMIT:
        blob = blob[:LLM_BODY_LIMIT] + "…(省略)"
    return blob


def build_llm_prompt(hints, items):
    """既知プロジェクト一覧と未確定セッション群から claude へ渡すプロンプトを作る。
    items: [{"index":int, "cwd":str, "excerpt":str}, ...]"""
    known = json.dumps(hints, ensure_ascii=False, indent=2)
    sessions = json.dumps(
        [{"index": it["index"], "cwd": it["cwd"], "body": it["excerpt"]} for it in items],
        ensure_ascii=False, indent=2,
    )
    return (
        "あなたは作業ログをプロジェクトへ振り分ける分類器です。\n"
        "各セッションについて、下記『既知プロジェクト』の中から最も合致する id を 1 つ選んでください。\n"
        "判断材料は cwd（作業ディレクトリ）と本文の話題です。path_globs / repos / keywords / description が手がかりです。\n\n"
        "重要な原則:\n"
        "- 確信が持てない場合や、どの既知プロジェクトにも当てはまらない場合は必ず \"未分類\" を返す。\n"
        "- 誤分類より未分類を優先する（曖昧なら未分類）。\n"
        "- 既知プロジェクト一覧に無い id を新しく作らない。該当が無ければ \"未分類\"。\n"
        "- confidence は 0.0〜1.0 で、その id だと言い切れる度合い。\n\n"
        "出力は JSON 配列のみ（前後に説明やコードフェンスを付けない）:\n"
        '[{"index": 0, "project_id": "<既知id または 未分類>", "confidence": 0.0}, ...]\n\n'
        "=== 既知プロジェクト ===\n" + known + "\n\n"
        "=== 分類対象セッション ===\n" + sessions + "\n\n"
        "=== 出力(JSON配列のみ) ===\n"
    )


def parse_llm_response(text, known_ids):
    """claude の出力から index -> (project_id, confidence) のマップを取り出す。
    パース不能・未知 id・確信度不足は採用しない（呼び出し側で未分類 fallback）。"""
    if not text:
        return {}
    s = text.strip()
    # コードフェンス除去
    if s.startswith("```"):
        s = s.strip("`")
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1:]
    # 最初の '[' から最後の ']' までを JSON とみなす
    lo, hi = s.find("["), s.rfind("]")
    if lo == -1 or hi == -1 or hi <= lo:
        return {}
    try:
        arr = json.loads(s[lo:hi + 1])
    except Exception:
        return {}
    known = set(known_ids)
    out = {}
    for rec in arr if isinstance(arr, list) else []:
        if not isinstance(rec, dict):
            continue
        try:
            idx = int(rec.get("index"))
        except (TypeError, ValueError):
            continue
        pid = rec.get("project_id")
        try:
            conf = float(rec.get("confidence", 0))
        except (TypeError, ValueError):
            conf = 0.0
        if pid and pid != "未分類" and pid in known and conf >= LLM_CONFIDENCE_MIN:
            out[idx] = (pid, conf)
    return out


def llm_classify(classifier, items):
    """①② を外したセッション群を LLM でまとめて判定する。
    items: [{"index", "cwd", "excerpt"}]  -> {index: (project_id, reason)}
    claude 不在/失敗時は空 dict（呼び出し側がキーワード fallback する）。"""
    if not items or not W.claude_available():
        return {}
    hints = classifier.project_hints()
    known_ids = classifier.known_ids()
    resolved = {}
    # 件数が多い場合はチャンク分割（プロンプト肥大とタイムアウトを避ける）
    for start in range(0, len(items), LLM_MAX_SESSIONS):
        chunk = items[start:start + LLM_MAX_SESSIONS]
        prompt = build_llm_prompt(hints, chunk)
        ok, out = W.run_claude(prompt, model=LLM_MODEL)
        if not ok:
            sys.stderr.write("[classify] LLM 判定スキップ（%s）。キーワード fallback します。\n" % out)
            continue
        mapping = parse_llm_response(out, known_ids)
        for idx, (pid, conf) in mapping.items():
            resolved[idx] = (pid, "llm:%s(%.2f)" % (pid, conf))
    return resolved


def main():
    home = W.worklog_home()
    raw_dir = os.path.join(home, "raw")
    cls_dir = os.path.join(home, "classified")
    classifier = W.load_classifier()

    args = sys.argv[1:]
    use_llm = "--no-llm" not in args
    pos = [a for a in args if not a.startswith("--")]
    date_filter = pos[0] if pos else None
    if use_llm and not W.claude_available():
        sys.stderr.write("[classify] claude CLI が無いため LLM 判定は行わず、決定論+キーワードで分類します。\n")
        use_llm = False
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

        # 2) 第1パス: 決定論（①cwd→②repo）と desktop 固定。外れたら LLM 用バケットへ。
        decided = {}        # sid -> (pid, reason)
        pending = []        # [{"sid", "index", "cwd", "excerpt"}]  ①② を外したもの
        for sid, s in sessions.items():
            # Claude Desktop（ローカルエージェント）のログは cwd が特殊パスで
            # プロジェクト分類が困難なため、専用の desktop-chat に固定する。
            if s["source"] == "desktop":
                decided[sid] = ("desktop-chat", "source=desktop")
                continue
            hit = classifier.classify_strong(s["cwd"])
            if hit:
                decided[sid] = hit
                continue
            pending.append({
                "sid": sid,
                "index": len(pending),
                "cwd": s["cwd"] or "",
                "excerpt": _session_excerpt(s["bodies"]),
            })

        # 3) 第2パス: ①② を外したセッションを LLM でまとめて判定（claude 不在/失敗時は空）。
        llm_resolved = llm_classify(classifier, pending) if (use_llm and pending) else {}

        # 4) LLM で決まらなかったものは ④キーワード fallback → それも外れたら未分類。
        for it in pending:
            sid = it["sid"]
            if it["index"] in llm_resolved:
                decided[sid] = llm_resolved[it["index"]]
                continue
            kw = classifier.classify_keyword(sessions[sid]["bodies"])
            decided[sid] = kw if kw else ("未分類", "no-match")

        # 5) 書き出し
        out_handles = {}

        def handle_for(pid):
            if pid not in out_handles:
                d = os.path.join(cls_dir, pid)
                os.makedirs(d, exist_ok=True)
                out_handles[pid] = open(os.path.join(d, "%s.jsonl" % date), "a", encoding="utf-8")
            return out_handles[pid]

        for sid, s in sessions.items():
            pid, reason = decided[sid]
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
