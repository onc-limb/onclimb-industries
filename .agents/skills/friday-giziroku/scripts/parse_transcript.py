#!/usr/bin/env python3
"""transcript → 話者集計 / 抜粋 / タイムブロック分割 / 話者なし推定。

giziroku スキルの Phase A（一次パース・機械処理）を担う決定的処理。
構造抽出・要約・補正・最終的な話者推定は LLM 側（SKILL.md の手順）が行う。
ここでは「LLM が Phase B の対話を組み立てるために必要な素材」を JSON で吐く。

対応する入力書式（揺れを吸収する）:
  1. Plaud 形式 : "HH:MM:SS Speaker N" のヘッダ行 + 次行以降に発言（サンプルがこれ）
  2. ラベル付き : "[HH:MM(:SS)] 名前:" / "名前 HH:MM" など
  3. インライン : "Speaker 1: 発言" / "名前: 発言"。Speaker N 以外の名前は、
                   同一名が 2 回以上現れたときだけ話者として扱う（頻度フィルタ）。
  4. 話者分離なし: ヘッダが検出できないベタ書き。段落単位で暫定ターンに割り、
                   話者は "推定話者?" として LLM の確認（Phase B）に回す。

標準ライブラリのみ。Python 3.9+ 。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

# ── ヘッダ行（話者ターンの開始）を検出するパターン群 ──────────────────
# 上から順に試し、最初に当たったものを採用する。
TIME = r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?)"
NAME = r"(?P<name>Speaker\s*\d+|[^\s:：]{1,20})"
HEADER_PATTERNS = [
    # "00:00:06 Speaker 1"  /  "00:00 なお"
    re.compile(rf"^{TIME}\s+{NAME}\s*$"),
    # "[00:00:06] Speaker 1:"  /  "[00:00] なお:"
    re.compile(rf"^\[{TIME}\]\s*{NAME}\s*[:：]?\s*$"),
    # "Speaker 1 00:00:06"  /  "なお 00:00"
    re.compile(rf"^{NAME}\s+{TIME}\s*$"),
]
# 行頭インライン: "Speaker 1: 発言…" / "なお： 発言…"（発言が同一行に続く）。
# Speaker N 以外の名前は _collect_inline_names の頻度フィルタを通ったものだけ採用する。
INLINE_PATTERN = re.compile(rf"^{NAME}\s*[:：]\s*(?P<inline>.+)$")

# ── 話者名らしさの検証（本文行をヘッダと誤認しない）────────────────
_SPEAKER_N = re.compile(r"^Speaker\s*\d+$", re.IGNORECASE)
_PARTICLES = "はがをにへでとものや"
_SENT_END = re.compile(r"(です|ます|でした|ました|ません|ください|します|しよう)")


def _valid_name(name: str) -> bool:
    """話者名として妥当なら True。文の断片らしきものは棄却する。"""
    if not name or len(name) > 20:
        return False
    if _SPEAKER_N.match(name):
        return True
    # 先頭が文字（英字・かな・漢字）でない（数字・記号始まり）は棄却
    if not re.match(r"^[^\W\d_]", name):
        return False
    # 助詞始まり・文末表現含みは本文の断片とみなして棄却
    if name[0] in _PARTICLES:
        return False
    if _SENT_END.search(name):
        return False
    # ASSUMPTION: 5 文字以上で助詞を含む語は文の断片（「次回の定例は明日」等）とみなす
    if len(name) >= 5 and any(c in _PARTICLES for c in name):
        return False
    return True


def _norm_speaker(raw: str) -> str:
    """話者ラベルを正規化する（"Speaker  1" → "Speaker 1"）。"""
    raw = raw.strip().strip("：:").strip()
    m = re.match(r"^Speaker\s*(\d+)$", raw, re.IGNORECASE)
    if m:
        return f"Speaker {m.group(1)}"
    return raw


def _match_header(line: str, inline_names: frozenset = frozenset()):
    """ヘッダ行なら (speaker, time, inline_text|None) を返す。違えば None。

    inline_names: 「名前: 発言」形式で話者として認める名前の集合
    （_collect_inline_names の頻度フィルタを通ったもの。Speaker N は常に認める）。
    """
    s = line.strip()
    if not s:
        return None
    for pat in HEADER_PATTERNS:
        m = pat.match(s)
        if not m:
            continue
        gd = m.groupdict()
        name = (gd.get("name") or "").strip()
        # 名前らしくないもの（本文の断片・数字始まり等）は棄却（誤検出を抑制）
        if not _valid_name(name):
            continue
        speaker = _norm_speaker(name)
        if not speaker:
            continue
        return speaker, gd.get("time"), None
    m = INLINE_PATTERN.match(s)
    if m:
        name = m.group("name").strip()
        if _valid_name(name):
            speaker = _norm_speaker(name)
            if _SPEAKER_N.match(name) or speaker in inline_names:
                return speaker, None, m.group("inline")
    return None


def _collect_inline_names(lines: list[str]) -> frozenset:
    """「名前: 発言」形式のインライン話者候補を数え、2 回以上現れた名前だけ返す。

    1 回きりの「なお: …」は本文の見出し等の可能性が高いので話者として扱わない。
    Speaker N はこのフィルタに関係なく常に有効（_match_header 側で許可）。
    """
    counts: dict[str, int] = {}
    for line in lines:
        s = line.strip()
        if not s or any(pat.match(s) for pat in HEADER_PATTERNS):
            continue
        m = INLINE_PATTERN.match(s)
        if not m:
            continue
        name = m.group("name").strip()
        if _SPEAKER_N.match(name) or not _valid_name(name):
            continue
        sp = _norm_speaker(name)
        counts[sp] = counts.get(sp, 0) + 1
    return frozenset(sp for sp, c in counts.items() if c >= 2)


def parse_labeled(lines: list[str], inline_names: frozenset = frozenset()) -> list[dict]:
    """ヘッダ行で話者ターンが切れている前提でセグメントに分ける。"""
    segments: list[dict] = []
    cur = None
    for line in lines:
        hit = _match_header(line, inline_names)
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
    # ヘッダ前の前文（話者 None のメタ情報）は speaker_count を汚さないよう除去
    return [s for s in segments if s.get("speaker")]


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


# timeline はセグメント全件ではなく粗い塊に集約する（長時間会議での JSON 膨張を防ぐ）
TIMELINE_BUCKET_SEC = 300   # 時刻ありは 5 分バケット
TIMELINE_CHUNK_SEGS = 10    # 時刻なしはセグメント 10 件ごとに 1 ブロック
TIMELINE_MAX_BLOCKS = 40    # 上限。超えたら隣接ブロックを均等に束ねる


def _time_to_sec(t: str | None):
    """"HH:MM:SS" / "MM:SS" を秒に変換する。変換できなければ None。"""
    if not t:
        return None
    parts = t.split(":")
    try:
        nums = [int(x) for x in parts]
    except ValueError:
        return None
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        # ASSUMPTION: 2 要素は「会議先頭からの MM:SS」とみなす（Plaud 等の経過時刻表記）
        return nums[0] * 60 + nums[1]
    return None


def _merge_blocks(blocks: list[dict], limit: int) -> list[dict]:
    """ブロック数が limit を超えたら、隣接ブロックを均等に束ねて上限内に収める。"""
    if len(blocks) <= limit:
        return blocks
    step = math.ceil(len(blocks) / limit)
    merged = []
    for i in range(0, len(blocks), step):
        chunk = blocks[i:i + step]
        speakers: list[str] = []
        for b in chunk:
            for sp in b["speakers"]:
                if sp not in speakers:
                    speakers.append(sp)
        preview = max((b["preview"] for b in chunk), key=len)
        merged.append({"time": chunk[0]["time"], "speakers": speakers, "preview": preview})
    return merged


def build_timeline(segments: list[dict]) -> list[dict]:
    """timeline ブロックを作る。

    - 時刻が取れる場合: 5 分バケットに集約し {"time": "00:05-", "speakers": [...],
      "preview": 代表発言 1 件（バケット内で最長の発言の抜粋）} を並べる。
    - 時刻が取れない場合: セグメント 10 件ごとに 1 ブロック（time は None）。
    - いずれも最大 40 ブロックに収める（超過分は隣接ブロックを束ねる）。
    """
    buckets: list[dict] = []
    if any(_time_to_sec(s.get("time")) is not None for s in segments):
        cur_key = None
        last_sec = 0
        for seg in segments:
            sec = _time_to_sec(seg.get("time"))
            if sec is None:
                sec = last_sec  # 時刻なしセグメントは直前の時刻に寄せる
            last_sec = sec
            key = sec // TIMELINE_BUCKET_SEC
            if not buckets or key != cur_key:
                start_min = key * TIMELINE_BUCKET_SEC // 60
                buckets.append({
                    "time": f"{start_min // 60:02d}:{start_min % 60:02d}-",
                    "speakers": [], "_texts": [],
                })
                cur_key = key
            b = buckets[-1]
            sp = seg.get("speaker")
            if sp and sp not in b["speakers"]:
                b["speakers"].append(sp)
            b["_texts"].append(seg.get("text", ""))
    else:
        for i in range(0, len(segments), TIMELINE_CHUNK_SEGS):
            group = segments[i:i + TIMELINE_CHUNK_SEGS]
            speakers: list[str] = []
            texts: list[str] = []
            for seg in group:
                sp = seg.get("speaker")
                if sp and sp not in speakers:
                    speakers.append(sp)
                texts.append(seg.get("text", ""))
            buckets.append({"time": None, "speakers": speakers, "_texts": texts})
    blocks = []
    for b in buckets:
        texts = b.pop("_texts")
        preview = excerpt(max(texts, key=len) if texts else "", 50)
        blocks.append({**b, "preview": preview})
    return _merge_blocks(blocks, TIMELINE_MAX_BLOCKS)


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

    # タイムブロック（5 分バケット or セグメント 10 件ごと、最大 40 ブロック）
    blocks = build_timeline(segments)

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
    inline_names = _collect_inline_names(lines)
    header_hits = sum(1 for ln in lines if _match_header(ln, inline_names))
    # ヘッダが本文行数に対して十分にある → 話者分離ありとみなす
    nonempty = sum(1 for ln in lines if ln.strip())
    labeled = header_hits >= 2 and (nonempty == 0 or header_hits / max(nonempty, 1) >= 0.1)
    if labeled:
        return parse_labeled(lines, inline_names), False
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
