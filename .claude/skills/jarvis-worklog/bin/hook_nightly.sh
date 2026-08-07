#!/usr/bin/env bash
# Claude Code の SessionStart hook から worklog nightly を起動するラッパー（launchd 代替）。
#
# なぜ hook か: launchd の無人実行は TCC が ~/Documents を読ませず、回避には
# フルディスクアクセス付与が要る。hook はユーザーが既に Documents アクセスを
# 許可した端末/Claude Code の文脈で動くため、追加権限ゼロで済む。
#
# 動作:
#   - スロットル: 前回起動から WORKLOG_HOOK_MIN_INTERVAL_SEC（既定 3600 秒）未満なら何もしない
#   - 多重起動防止: PID ロック（前回の nightly が生きていれば何もしない）
#   - nightly.sh --skip-today を nohup でデタッチ起動し、即座に return する
#     （SessionStart をブロックしない。進行中の当日は対象外 = 完了した日だけ digest 化）
#   - stdout には何も出さない（SessionStart hook の stdout はモデルの文脈に注入されるため）
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="${WORKLOG_NIGHTLY_LOG:-/tmp/worklog-nightly.log}"
THROTTLE="${WORKLOG_HOOK_MIN_INTERVAL_SEC:-3600}"

PY="$(command -v python3 || true)"
[ -z "$PY" ] && exit 0

DATA="$(SD="$SCRIPT_DIR" "$PY" -c 'import os, sys; sys.path.insert(0, os.environ["SD"]); import worklog_lib; print(worklog_lib.worklog_home())' 2>/dev/null || true)"
[ -z "$DATA" ] || [ ! -d "$DATA" ] && exit 0

STATE_DIR="$DATA/logs/nightly"
mkdir -p "$STATE_DIR"
LAST="$STATE_DIR/.hook-last-spawn"
LOCK="$STATE_DIR/.hook-pid"

# スロットル: 直近の起動から間隔が空いていなければ何もしない
now="$(date +%s)"
if [ -f "$LAST" ]; then
  last="$(cat "$LAST" 2>/dev/null || echo 0)"
  if [ $((now - last)) -lt "$THROTTLE" ]; then
    exit 0
  fi
fi

# 多重起動防止: 前回 spawn した nightly がまだ生きていれば何もしない
if [ -f "$LOCK" ]; then
  pid="$(cat "$LOCK" 2>/dev/null || echo)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    exit 0
  fi
fi

echo "$now" > "$LAST"
nohup bash "$SCRIPT_DIR/nightly.sh" --skip-today >> "$LOG" 2>&1 &
echo $! > "$LOCK"
exit 0
