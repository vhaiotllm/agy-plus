#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGY_APP_DIR="${ANTIGRAVITY_APP_DATA_DIR:-$HOME/.gemini/antigravity-cli}"
GEMINI_CFG_DIR="$HOME/.gemini/config"
LOCAL_BIN="$HOME/.local/bin"

echo "==> Installing AGY Plus (Claude Code + OpenAI Codex Supercharged Edition)..."

mkdir -p "$AGY_APP_DIR/agy_plus" "$GEMINI_CFG_DIR/plugins" "$GEMINI_CFG_DIR/skills" "$LOCAL_BIN"

# 1. Install AGY Plus runtime & statusline
cp -f "$REPO_DIR/runtime/agy_plus/"*.py "$AGY_APP_DIR/agy_plus/"
if [ ! -f "$AGY_APP_DIR/agy_plus/projects.json" ]; then
  cp -f "$REPO_DIR/runtime/agy_plus/projects.example.json" "$AGY_APP_DIR/agy_plus/projects.json"
fi
chmod +x "$AGY_APP_DIR/agy_plus/"*.py

cp -f "$REPO_DIR/statusline/statusline.py" "$AGY_APP_DIR/statusline.py"
cp -f "$REPO_DIR/statusline/statusline.sh" "$AGY_APP_DIR/statusline.sh"
chmod +x "$AGY_APP_DIR/statusline.py" "$AGY_APP_DIR/statusline.sh"

ln -sf "$AGY_APP_DIR/agy_plus/cli.py" "$LOCAL_BIN/agy-plus"

# 2. Install validated plugins
rm -rf "$GEMINI_CFG_DIR/plugins/agy-core-plus" "$GEMINI_CFG_DIR/plugins/agy-engineering-fleet"
cp -a "$REPO_DIR/plugins/agy-core-plus" "$GEMINI_CFG_DIR/plugins/"
cp -a "$REPO_DIR/plugins/agy-engineering-fleet" "$GEMINI_CFG_DIR/plugins/"

# 3. Install curated skills (non-destructive merge)
cp -a "$REPO_DIR/skills/." "$GEMINI_CFG_DIR/skills/"
if [ ! -f "$GEMINI_CFG_DIR/skills.json" ]; then
  cp -f "$REPO_DIR/config/skills.json" "$GEMINI_CFG_DIR/skills.json"
fi
if [ ! -f "$GEMINI_CFG_DIR/AGENTS.md" ]; then
  cp -f "$REPO_DIR/config/AGENTS.md" "$GEMINI_CFG_DIR/AGENTS.md"
  cp -f "$REPO_DIR/config/GEMINI.md" "$GEMINI_CFG_DIR/GEMINI.md"
fi

# 4. Configure statusLine in settings.json safely
python3 - "$AGY_APP_DIR/settings.json" "$AGY_APP_DIR/statusline.sh" <<'PY'
import json, os, shutil, sys
settings_path, status_sh = sys.argv[1], sys.argv[2]
data = {}
if os.path.isfile(settings_path):
    shutil.copy2(settings_path, settings_path + ".agy-plus.bak")
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
data.setdefault("mode", "accept-edits")
data["statusLine"] = {
    "type": "",
    "command": status_sh,
    "enabled": True,
    "stack_with_default": True,
}
os.makedirs(os.path.dirname(settings_path), exist_ok=True)
with open(settings_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
PY

# 5. Register MCP servers (agy-plus + context7)
AGY_BIN="$(command -v agy || echo "$LOCAL_BIN/agy")"
if [ -x "$AGY_BIN" ]; then
  "$AGY_BIN" mcp add agy-plus "$(command -v python3)" "$AGY_APP_DIR/agy_plus/mcp_server.py" >/dev/null 2>&1 || true
  "$AGY_BIN" mcp add context7 https://mcp.context7.com/mcp >/dev/null 2>&1 || true
else
  python3 - "$GEMINI_CFG_DIR/mcp_config.json" "$AGY_APP_DIR/agy_plus/mcp_server.py" <<'PY'
import json, os, shutil, sys
mcp_path, server_py = sys.argv[1], sys.argv[2]
cfg = {"mcpServers": {}}
if os.path.isfile(mcp_path) and os.path.getsize(mcp_path) > 0:
    try:
        cfg = json.load(open(mcp_path, "r", encoding="utf-8"))
    except Exception:
        pass
cfg.setdefault("mcpServers", {})
cfg["mcpServers"]["agy-plus"] = {"command": shutil.which("python3") or "python3", "args": [server_py]}
cfg["mcpServers"]["context7"] = {"url": "https://mcp.context7.com/mcp"}
with open(mcp_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)
PY
fi

# 6. Install shell wrapper into ~/.bashrc or ~/.zshrc
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
  [ -f "$rc" ] || continue
  if ! grep -q "AGY-PLUS WRAPPER START" "$rc" && ! grep -q "AGY-PLUS (CLAUDE + CODEX PARITY) START" "$rc"; then
    cat >> "$rc" <<'SH'

# AGY-PLUS WRAPPER START
export PATH="$HOME/.local/bin:$PATH"
export AGY_CLI_MODEL_API_MAX_RETRIES=5
agy() {
    local real_agy="${AGY_REAL_BIN:-$HOME/.local/bin/agy}"
    [ -x "$real_agy" ] || real_agy="$(command -v agy)"
    case "${1:-}" in
        nonstop|memory|undo|goals|ralph|sessions|stats|report|review|exec|doctor)
            "$HOME/.local/bin/agy-plus" "$@"
            ;;
        plugin|plugins|mcp|models|agent|agents|remote-control|update|changelog|help|install)
            "$real_agy" "$@"
            ;;
        *)
            "$real_agy" --dangerously-skip-permissions "$@"
            ;;
    esac
}
# AGY-PLUS WRAPPER END
SH
  fi
done

echo "==> Running AGY Plus Doctor..."
"$LOCAL_BIN/agy-plus" doctor || true
echo ""
echo "✓ AGY Plus installed! Run: source ~/.bashrc && agy doctor"
