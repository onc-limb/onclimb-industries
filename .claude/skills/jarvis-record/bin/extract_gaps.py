#!/usr/bin/env python3
"""jarvis-record 用: digest の欠損箇所と時間帯(band)構成の機械抽出.

worklog digest から「記録なし / 未確認 / 確認できない」等のログ欠損表現を
行単位で拾い、確認サイクルの質問候補リストの原料を JSON で返す。
判定はパターンマッチのみで、正誤・重要度の判断はしない。
band 間の矛盾検知は意味の突き合わせが必要なため、ここでは band 構成と
digest 冒頭の「重複・矛盾」セクションの有無を返すに留める(突き合わせ自体は
エージェントが行う)。

使い方:
    python3 extract_gaps.py <digest.md>

出力(JSON):
    bands:  [{"index": 1, "total": 5, "span": "09:00–11:30", "line": 3}, ...]
    reconciliation: {"present": true, "line": 5}   # digest 側で検知済みリストの有無
    gaps:   [{"line": 42, "band": 2, "section": "作業内容（進捗ステータス付き）",
              "type": "セッション中断" | null, "text": "..."}]
    count:  欠損箇所の総数
"""
import json
import re
import sys

BAND_RE = re.compile(r"^##\s*【時間帯\s*(\d+)\s*/\s*(\d+)\s*:?\s*(.*?)】")
RECON_RE = re.compile(r"^##\s*【時間帯間の重複・矛盾")
HEADING_RE = re.compile(r"^(#{2,4})\s+(.*)")
# 欠損を示す表現(digest の書き癖に合わせて育てる)
GAP_RE = re.compile(
    r"記録なし|記録に残っていない|ログに残っていない|未確認|"
    r"確認できない|確認できていない|ログの範囲内では|ログからは読み取れ"
)
# 「記録なし（セッション中断）」のような型付き欠損の型を拾う
TYPED_RE = re.compile(r"記録なし\s*[（(]([^）)]+)[）)]")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: extract_gaps.py <digest.md>")
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError as e:
        sys.exit("error: {}".format(e))

    bands = []
    recon = {"present": False, "line": None}
    gaps = []
    cur_band = None
    cur_section = None

    for i, line in enumerate(lines, start=1):
        m = BAND_RE.match(line)
        if m:
            cur_band = int(m.group(1))
            bands.append({
                "index": cur_band,
                "total": int(m.group(2)),
                "span": m.group(3).strip() or None,
                "line": i,
            })
            cur_section = None
            continue
        if RECON_RE.match(line):
            recon = {"present": True, "line": i}
            cur_section = "時間帯間の重複・矛盾"
            continue
        hm = HEADING_RE.match(line)
        if hm:
            cur_section = hm.group(2).strip()
            continue
        if GAP_RE.search(line):
            tm = TYPED_RE.search(line)
            gaps.append({
                "line": i,
                "band": cur_band,
                "section": cur_section,
                "type": tm.group(1).strip() if tm else None,
                "text": line.strip().lstrip("-* ").strip(),
            })

    print(json.dumps({
        "bands": bands,
        "reconciliation": recon,
        "gaps": gaps,
        "count": len(gaps),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
