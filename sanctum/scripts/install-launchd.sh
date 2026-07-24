#!/bin/bash
# Sanctum を launchd に登録してログイン時に自動起動させる（macOS 用）。
# 使い方:
#   ./scripts/install-launchd.sh            # release ビルド + 登録 + 起動（既定ポート 14141）
#   PORT=8888 ./scripts/install-launchd.sh  # ポートを変えて登録
#   ./scripts/install-launchd.sh uninstall  # 解除
set -euo pipefail

SANCTUM_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VAULT_DIR="$(cd "$SANCTUM_DIR/.." && pwd)"
LABEL="com.onclimb.sanctum"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PORT="${PORT:-14141}"
LOG="$HOME/Library/Logs/sanctum.log"

if [[ "${1:-}" == "uninstall" ]]; then
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "解除しました: $PLIST"
    exit 0
fi

echo "release ビルド中…"
(cd "$SANCTUM_DIR" && cargo build --release)

# ~/Documents 配下のバイナリを launchd から直接起動すると macOS の
# 保護フォルダ（TCC）に阻まれて dyld がハングするため、外にコピーして使う。
BIN="$HOME/.local/bin/sanctum"
mkdir -p "$HOME/.local/bin"
cp "$SANCTUM_DIR/target/release/sanctum" "$BIN"

mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__BIN__|$BIN|g" \
    -e "s|__VAULT__|$VAULT_DIR|g" \
    -e "s|__PORT__|$PORT|g" \
    -e "s|__LOG__|$LOG|g" \
    "$SANCTUM_DIR/launchd/$LABEL.plist.template" > "$PLIST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "登録しました: $PLIST"
echo "URL: http://127.0.0.1:$PORT/  (ログ: $LOG)"
echo "解除するには: ./scripts/install-launchd.sh uninstall"
