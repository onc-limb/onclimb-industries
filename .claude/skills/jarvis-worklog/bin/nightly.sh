#!/usr/bin/env bash
# 夜間の先回り実行: collect → (raw が更新された日だけ) classify → summarize。
# 毎晩これを回しておくと、日中の「まとめて」は suggest_projects の確認と
# ToDo 突き合わせだけになり、ほぼ即答になる。
#
# 使い方:
#   bin/nightly.sh                       # launchd(deploy/com.user.worklog.nightly.plist) / cron から毎晩 1 回
#   WORKLOG_DATA=/path bin/nightly.sh    # データ置き場を上書きしたい場合
#
# 仕組み:
#   - 処理済み管理は logs/nightly/<日付>.stamp。raw/<日付>.jsonl が stamp より新しい日だけ処理する。
#   - classify と summarize が両方成功した日だけ stamp を更新する。失敗した日は翌晩に再試行される
#     （summarize は差分スキップを持つため、再試行時に成功済み digest を作り直すことはない）。
#   - claude CLI が無い環境では classify は決定論+キーワードに fallback し、summarize は
#     プロンプト保存のみで失敗(exit 1)になる → stamp は更新されず、次回また対象になる。
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "[nightly] python3 が見つかりません" >&2
  exit 1
fi

# データ置き場（WORKLOG_DATA → 無ければ git リポジトリ直下の worklog-data/）は
# worklog_lib.worklog_home() が正本なので、そこから取得する。
DATA="$(SD="$SCRIPT_DIR" "$PY" -c 'import os, sys; sys.path.insert(0, os.environ["SD"]); import worklog_lib; print(worklog_lib.worklog_home())')"
if [ -z "$DATA" ] || [ ! -d "$DATA" ]; then
  echo "[nightly] データ置き場を解決できません: $DATA" >&2
  exit 1
fi

echo "[nightly] $(date '+%F %T') 開始 (data=$DATA)"
bash "$SCRIPT_DIR/collect.sh"

STAMP_DIR="$DATA/logs/nightly"
mkdir -p "$STAMP_DIR"

status=0
for raw in "$DATA"/raw/*.jsonl; do
  [ -e "$raw" ] || continue
  d="$(basename "$raw" .jsonl)"
  case "$d" in
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
    *) continue ;;   # undated.jsonl 等の日付でないファイルはスキップ
  esac
  stamp="$STAMP_DIR/$d.stamp"
  if [ -e "$stamp" ] && [ ! "$raw" -nt "$stamp" ]; then
    continue   # 前回処理以降 raw に追加が無い日
  fi
  echo "[nightly] $d を処理 (classify → summarize)"
  if "$PY" "$SCRIPT_DIR/classify.py" "$d" && "$PY" "$SCRIPT_DIR/summarize.py" "$d"; then
    touch "$stamp"
  else
    echo "[nightly] $d の処理に失敗（翌晩に再試行）" >&2
    status=1
  fi
done

echo "[nightly] $(date '+%F %T') 終了 (status=$status)"
exit $status
