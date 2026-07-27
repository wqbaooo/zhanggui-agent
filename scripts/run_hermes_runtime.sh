#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${ZHANGGUI_HERMES_RUNTIME_DIR:-$HOME/.local/share/zhanggui-agent/hermes-runtime}"
HERMES_HOME_DIR="$RUNTIME_DIR/home"
HERMES_BIN="$RUNTIME_DIR/venv/bin/hermes"

if [[ ! -x "$HERMES_BIN" || ! -s "$RUNTIME_DIR/api-server.key" ]]; then
  echo "Hermes runtime is not installed. Run scripts/install_hermes_runtime.sh first." >&2
  exit 1
fi

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi

: "${DEEPSEEK_API_KEY:?DEEPSEEK_API_KEY is required for the isolated Hermes runtime}"

export HERMES_HOME="$HERMES_HOME_DIR"
export HERMES_ENABLE_PROJECT_PLUGINS=true
export HERMES_PLUGINS_DEBUG="${HERMES_PLUGINS_DEBUG:-0}"
export API_SERVER_ENABLED=true
export API_SERVER_PORT="${HERMES_API_PORT:-8652}"
export API_SERVER_KEY="$(<"$RUNTIME_DIR/api-server.key")"
export ZHANGGUI_API_BASE="${ZHANGGUI_API_BASE:-http://127.0.0.1:8000}"
export ZHANGGUI_PROJECT_ID="${ZHANGGUI_PROJECT_ID:-xinyu-hengtai-dakou}"

cd "$ROOT_DIR"
# A separate user-level Hermes may already be supervised by launchd. --force
# is safe here because this sidecar has its own HERMES_HOME, API port and key.
exec "$HERMES_BIN" gateway run --force
