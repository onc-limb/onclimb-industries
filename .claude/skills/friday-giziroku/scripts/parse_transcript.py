#!/usr/bin/env python3
"""transcript → 話者集計 / 抜粋 / タイムブロック分割 / 話者なし推定。

giziroku スキルの Phase A（一次パース・機械処理）を担う決定的処理。
構造抽出・要約・補正・最終的な話者推定は LLM 側（SKILL.md の手順）が行う。
ここでは「LLM が Phase B の対話を組み立てるために必要な素材」を JSON で吐く。

対応する入力書式（揺れを吸収する）:
  1. Plaud 形式 : "HH:MM:SS Speaker N" のヘッダ行 + 次行以降に発言（サンプルがこれ）
  2. ラベル付き : "[HH:MM(:SS)] 名前:" / "名前 HH:MM" / "名前: 発言" など
  3. 話者分離なし: ヘッダが検出できないベタ書き。段落単位で暫定ターンに割り、
                   話者は "推定話者?" として LLM の確認（Phase B）に回す。

標準ライブラリのみ。Python 3.9+ 。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── ヘッダ行（話者ターンの開始）を検出するパターン群 ──────────────────
# 上から順に試し、最初に当たったものを採用する。
TIME = r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?)"
NAME = r"(?P<name>Speaker\s*\d+|[^\n:：]{1,40}?)"
HEADER_PATTERNS = [
    # "00:00:06 Speaker 1"  /  "00:00 なお"
    re.compile(rf"^{TIME}\s+{NAME}\s*$"),
    # "[00:00:06] Speaker 1:"  /  "[00:00] なお:"
    re.compile(rf"^\[{TIME}\]\s*{NAME}\s*[:：]?\s*$"),
    # "Speaker 1 00:00:06"  /  "なお 00:00"
    re.compile(rf"^{NAME}\s+{TIME}\s*$"),
    # 行頭インライン: "Speaker 1: 発言…" / "なお： 発言…"（発言が同一行に続く）
    re.compile(rf"^(?P<name>Speaker\s*\d+)\s*[:：]\s*(?P<inline>.+)$"),
]


def _norm_speaker(raw: str) -> str:
    """話者ラベルを正規化する（"Speaker  1" → "Speaker 1"）。"""
    raw = raw.strip().strip("：:").strip()
    m = re.match(r"^Speaker\s*(\d+)$", raw, re.IGNORECASE)
    if m:
        return f"Speaker {m.group(1)}"
    return raw


def _match_header(line: str):
    """ヘッダ行なら (speaker, time, inline_text|None) を返す。違えば None。"""
    s = line.strip()
    if not s:
        return None
    for pat in HEADER_PATTERNS:
        m = pat.match(s)
        if not m:
            continue
        gd = m.groupdict()
        name = gd.get("name") or ""
        # 純粋な名前がタイムスタンプや空でないこと（誤検出を抑制）
        speaker = _norm_speaker(name)
        if not speaker:
            return None
        return speaker, gd.get("time"), gd.get("inline")
    return None


def parse_labeled(lines: list[str]) -> list[dict]:
    """ヘッダ行で話者ターンが切れている前提でセグメントに分ける。"""
    segments: list[dict] = []
    cur = None
    for line in lines:
        hit = _match_header(line)
        if hit:
            speaker, time, inline = hit
            if cur:
                segments.append(cur)
            cur = {"speaker": speaker, "time": time, "text": ""}
            if inline:
                cur["text"] = inline.strip()
            continue
        if cur is None:
            # ヘッダ前の前文（メタ情報など）はスキップ
            if line.strip():
                cur = {"speaker": None, "time": None, "text": line.strip()}
            continue
        if line.strip():
            cur["text"] = (cur["text"] + " " + line.strip()).strip()
    if cur:
        segments.append(cur)
    # 話者 None のダミー先頭を除去
    return [s for s in segments if s.get("speaker") or s.get("text")]


# ── 話者分離なし（ベタ書き）の暫定ターン推定 ─────────────────────────
# 句点で文に割り、「呼びかけ」「敬体/常体の転換」を弱い境界シグナルにする。
# あくまで暫定（LLM が Phase B で確認）。過分割を避け、保守的に切る。
CALL_OUT = re.compile(r"(さん|くん|ちゃん)[、, ]")  # 「なおさん、」等の呼びかけ
SENT_SPLIT = re.compile(r"(?<=[。！？])\s*")


def parse_undiarized(text: str) -> list[dict]:
    """ベタ書きを段落→文に割り、暫定話者 A/B… を交互寄りに割り当てる。"""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) <= 1:
        # 段落区切りも無い 1 塊 → 文単位で粗くターン候補化
        sents = [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]
        paras = []
        buf = []
        for s in sents:
            buf.append(s)
            # 呼びかけが出たら話者交代の候補として区切る
            if CALL_OUT.search(s) and len(buf) >= 1:
                paras.append(" ".join(buf))
                buf = []
        if buf:
            paras.append(" ".join(buf))
    segments = []
    label_ord = 0
    for i, p in enumerate(paras):
        # 呼びかけ／逆接の冒頭で話者交代したと“仮定”してラベルを回す
        if i > 0 and (CALL_OUT.search(p[:20]) or p[:6].startswith(("でも", "いや", "あの", "はい"))):
            label_ord += 1
        speaker = f"推定話者{chr(ord('A') + (label_ord % 8))}"
        segments.append({"speaker": speaker, "time": None, "text": p, "estimated": True})
    return segments


# ── 集計・抜粋 ──────────────────────────────────────────────────────
def excerpt(text: str, limit: int = 70) -> str:
    t = re.sub(r"\s+", "", text)
    return t if len(t) <= limit else t[:limit] + "…"


def summarize(segments: list[dict], estimated: bool) -> dict:
    speakers: dict[str, dict] = {}
    for seg in segments:
        sp = seg.get("speaker") or "(不明)"
        info = speakers.setdefault(
            sp, {"turns": 0, "chars": 0, "first_time": seg.get("time"),
                 "last_time": None, "excerpts": []}
        )
        info["turns"] += 1
        info["chars"] += len(re.sub(r"\s+", "", seg.get("text", "")))
        if seg.get("time"):
            info["last_time"] = seg["time"]
        # 役割推定の手がかりになりそうな“具体的に長い”発言を最大3件保持
        if len(info["excerpts"]) < 3 and len(seg.get("text", "")) >= 25:
            info["excerpts"].append(excerpt(seg["text"]))

    # タイムブロック（時間が取れるなら 0:00-, 5:00- … の粗い塊で並びを残す）
    blocks = []
    for seg in segments:
        blocks.append({
            "time": seg.get("time"),
            "speaker": seg.get("speaker"),
            "preview": excerpt(seg.get("text", ""), 50),
        })

    return {
        "diarization": "estimated" if estimated else "labeled",
        "segment_count": len(segments),
        "speaker_count": len(speakers),
        "speakers": speakers,
        "timeline": blocks,
    }


def detect_and_parse(raw: str) -> tuple[list[dict], bool]:
    """ヘッダ行が十分にあれば labeled、無ければ undiarized で解析。"""
    lines = raw.splitlines()
    header_hits = sum(1 for ln in lines if _match_header(ln))
    # ヘッダが本文行数に対して十分にある → 話者分離ありとみなす
    nonempty = sum(1 for ln in lines if ln.strip())
    labeled = header_hits >= 2 and (nonempty == 0 or header_hits / max(nonempty, 1) >= 0.1)
    if labeled:
        return parse_labeled(lines), False
    return parse_undiarized(raw), True


def main() -> int:
    ap = argparse.ArgumentParser(description="transcript を話者集計/抜粋/分割する（giziroku Phase A）")
    ap.add_argument("path", help="文字起こしファイルのパス")
    ap.add_argument("--json", action="store_true", help="JSON のみ出力（既定は人間可読サマリも添える）")
    args = ap.parse_args()

    p = Path(args.path)
    if not p.is_file():
        print(f"error: ファイルが見つかりません: {p}", file=sys.stderr)
        return 1
    raw = p.read_text(encoding="utf-8", errors="replace")

    segments, estimated = detect_and_parse(raw)
    result = summarize(segments, estimated)
    result["source"] = str(p)
    result["char_total"] = len(re.sub(r"\s+", "", raw))

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.json:
        print("", file=sys.stderr)
        mode = "話者分離あり（ラベル）" if not estimated else "話者分離なし → 暫定推定（要 Phase B 確認）"
        print(f"# 解析モード: {mode}", file=sys.stderr)
        print(f"# 話者 {result['speaker_count']} 名 / セグメント {result['segment_count']} / 総 {result['char_total']} 字", file=sys.stderr)
        for sp, info in result["speakers"].items():
            print(f"#  - {sp}: 発言{info['turns']}回 / {info['chars']}字 / {info['first_time']}〜{info['last_time']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
