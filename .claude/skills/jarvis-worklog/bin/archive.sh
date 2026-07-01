#!/usr/bin/env bash
# 要約済みの raw/ classified/ を月単位で zip 退避する。
# 圧縮後に元ファイルを削除するが、zip 内には必ず残る（完全消失しない）。
# 実体は archive_impl.py に委譲。破壊的操作のため SKILL からは確認後に呼ぶこと。
#
# 使い方:
#   bin/archive.sh                 # 当月より前の全月
#   bin/archive.sh 2026-05         # 指定月
#   bin/archive.sh 2026-05 --force # 未要約でも強制
#   bin/archive.sh --check 2026-05 # チェックのみ（退避しない）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# データ置き場は archive_impl.py(worklog_lib.data_home) が決める。WORKLOG_DATA で上書き可。

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "[archive] python3 が見つかりません" >&2
  exit 1
fi

exec "$PY" "$SCRIPT_DIR/archive_impl.py" "$@"
