#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""調査済み台帳(screened.jsonl)の操作。一意キーは法人番号(13桁)。証券コードでも名寄せ。

サブコマンド:
  status                         台帳の累計件数・合格数・最終調査日を表示
  filter <ticker...> | --stdin   候補から「未調査」だけを抜き出す（重複調査の防止）
  add  --file <json> | --stdin   1 件を追記（合否に関わらず記録。重複は追記しない）

filter 出力例:
  {"new": ["7203","8058"], "known": ["9433"], "total_in_registry": 12}
add は標準入力/ファイルから 1 社分の JSON を受け取り {"added": true/false, ...} を返す。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hdss_lib as L  # noqa: E402


def cmd_status():
    records = L.read_registry()
    passed = sum(1 for r in records if r.get("passed"))
    failed = len(records) - passed
    last = max((r.get("screened_at") or "" for r in records), default="")
    out = {
        "registry_path": L.registry_path(),
        "total": len(records),
        "passed": passed,
        "failed": failed,
        "last_screened_at": last or None,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_filter(args, use_stdin):
    tickers = list(args)
    if use_stdin:
        tickers += [ln.strip() for ln in sys.stdin.read().splitlines() if ln.strip()]
    if not tickers:
        sys.stderr.write("使い方: registry.py filter [--stdin] <証券コード...>\n")
        return 2
    records = L.read_registry()
    _, known_tickers = L.registry_keys(records)
    new, known = [], []
    seen = set()
    for t in tickers:
        norm = L.normalize_ticker(t)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        (known if norm in known_tickers else new).append(norm)
    print(json.dumps({
        "new": new,
        "known": known,
        "total_in_registry": len(records),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_add(file_path, use_stdin):
    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()
    elif use_stdin:
        raw = sys.stdin.read()
    else:
        sys.stderr.write("使い方: registry.py add (--file <json> | --stdin)\n")
        return 2
    try:
        rec = json.loads(raw)
    except Exception as e:
        print(json.dumps({"added": False, "error": "JSON 解析失敗: %s" % e}, ensure_ascii=False))
        return 1
    if isinstance(rec, list):
        # 複数件まとめ追記
        results = []
        for r in rec:
            results.append({"ticker": r.get("ticker"), "added": _add_one(r)})
        print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
        return 0
    added = _add_one(rec)
    print(json.dumps({
        "added": added,
        "ticker": rec.get("ticker"),
        "corp_number": rec.get("corp_number"),
        "note": None if added else "既に台帳に存在（重複追記なし）",
    }, ensure_ascii=False, indent=2))
    return 0


def _add_one(rec):
    rec.setdefault("screened_at", L.today_jst())
    if not rec.get("corp_number"):
        sys.stderr.write("[registry] 警告: corp_number 未設定。ticker=%s（重複排除は証券コードで実施）\n"
                         % rec.get("ticker"))
    return L.append_registry(rec)


def main(argv):
    if not argv:
        sys.stderr.write("サブコマンド: status | filter | add\n")
        return 2
    cmd, rest = argv[0], argv[1:]
    use_stdin = "--stdin" in rest
    rest = [a for a in rest if a != "--stdin"]
    if cmd == "status":
        return cmd_status()
    if cmd == "filter":
        return cmd_filter(rest, use_stdin)
    if cmd == "add":
        file_path = None
        if "--file" in rest:
            i = rest.index("--file")
            file_path = rest[i + 1] if i + 1 < len(rest) else None
        return cmd_add(file_path, use_stdin)
    sys.stderr.write("不明なサブコマンド: %s\n" % cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
