#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""取得済み指標から健全性コア条件を決定論的に判定する。

数値の捏造を構造的に防ぐため、合否はこのスクリプトだけが決める。
LLM は各社のデータ（利回り/配当性向/配当推移/営業利益推移）をサイトから取得して
下記 JSON に整形する役割に専念し、判定そのものはここに委ねる。

入力 JSON（1 社 or 複数社の配列。配当/営業利益は古い→新しいの時系列）:
  {
    "ticker": "1234", "name": "...",
    "yield": 4.3, "payout_ratio": 38.0,
    "dividend_history": [40, 42, 45, 48],
    "op_profit_history": [120, 130, 150, 160],
    "sources": ["https://...","https://..."]
  }

使い方:
  echo '<json>' | python3 judge.py --stdin
  python3 judge.py --file companies.json
  python3 judge.py --file c.json --yield-min 4.0 --payout-max 50 --min-periods 3
出力: 判定結果 JSON（passed / checks / reasons / insufficient）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hdss_lib as L  # noqa: E402


def main(argv):
    file_path = None
    use_stdin = False
    overrides = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--file":
            i += 1
            file_path = argv[i] if i < len(argv) else None
        elif a == "--stdin":
            use_stdin = True
        elif a == "--yield-min":
            i += 1
            overrides["yield_min"] = float(argv[i])
        elif a == "--payout-max":
            i += 1
            overrides["payout_max"] = float(argv[i])
        elif a == "--min-periods":
            i += 1
            overrides["min_periods"] = int(argv[i])
        elif a == "--allow-cuts":
            i += 1
            overrides["allow_dividend_cuts"] = int(argv[i])
        i += 1

    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()
    elif use_stdin:
        raw = sys.stdin.read()
    else:
        sys.stderr.write("使い方: judge.py (--file <json> | --stdin) [--yield-min N] [--payout-max N] [--min-periods N]\n")
        return 2

    try:
        data = json.loads(raw)
    except Exception as e:
        print(json.dumps({"error": "JSON 解析失敗: %s" % e}, ensure_ascii=False))
        return 1

    cfg = L.load_config()
    cfg.update(overrides)

    companies = data if isinstance(data, list) else [data]
    results = [L.judge_company(c, cfg) for c in companies]

    passed = [r for r in results if r["passed"]]
    summary = {
        "thresholds": {
            "yield_min": L.config_value(cfg, "yield_min", 4.0),
            "payout_max": L.config_value(cfg, "payout_max", 50.0),
            "min_periods": L.config_value(cfg, "min_periods", 3),
            "allow_dividend_cuts": L.config_value(cfg, "allow_dividend_cuts", 0),
        },
        "judged": len(results),
        "passed": len(passed),
        "failed": len(results) - len(passed),
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
