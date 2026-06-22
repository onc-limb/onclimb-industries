#!/usr/bin/env bash
# 生 JSONL を raw/ へ収集・構造抽出・マスキングする収集スクリプト。
# SessionEnd Hook / PreCompact Hook / 毎日 cron(launchd) / 手動 のいずれからでも安全に動く。
# 実体の重い処理は collect_impl.py（堅牢な JSON パースのため Python）に委譲する。
#
# 使い方:
#   bin/collect.sh                  # 通常実行（前回カーソル以降を収集）
#   WORKLOG_DATA=/path bin/collect.sh   # データ置き場を上書きしたい場合
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# データの置き場所は collect_impl.py(worklog_lib.data_home) が決める:
#   WORKLOG_DATA 環境変数 → 無ければ git リポジトリ直下の worklog-data/。
# ここではあえて WORKLOG_HOME を強制しない（コードとデータを分離するため）。

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "[collect] python3 が見つかりません" >&2
  exit 1
fi

exec "$PY" "$SCRIPT_DIR/collect_impl.py" "$@"
