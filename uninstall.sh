#!/usr/bin/env bash
set -euo pipefail

AGY_APP_DIR="${ANTIGRAVITY_APP_DATA_DIR:-$HOME/.gemini/antigravity-cli}"
GEMINI_CFG_DIR="$HOME/.gemini/config"

echo "==> Removing AGY Plus plugins & CLI symlink (preserving your saved memories & checkpoints)..."
rm -rf "$GEMINI_CFG_DIR/plugins/agy-core-plus" "$GEMINI_CFG_DIR/plugins/agy-engineering-fleet"
rm -f "$HOME/.local/bin/agy-plus"

AGY_BIN="$(command -v agy || echo "$HOME/.local/bin/agy")"
if [ -x "$AGY_BIN" ]; then
  "$AGY_BIN" mcp remove agy-plus >/dev/null 2>&1 || true
fi

if [ -f "$AGY_APP_DIR/settings.json.agy-plus.bak" ]; then
  cp -f "$AGY_APP_DIR/settings.json.agy-plus.bak" "$AGY_APP_DIR/settings.json"
fi

echo "✓ Uninstalled AGY Plus plugins. (Your data in $AGY_APP_DIR/memories and $AGY_APP_DIR/agy_plus was kept safe.)"
