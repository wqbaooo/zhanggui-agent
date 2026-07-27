#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/runtimes/pi"
NODE_BIN="${NODE_BIN:-}"

CODEX_NODE="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
if [[ -z "$NODE_BIN" && -x "$CODEX_NODE" ]]; then
  NODE_BIN="$CODEX_NODE"
fi
if [[ -z "$NODE_BIN" && -x "/Applications/ChatGPT.app/Contents/Resources/cua_node/bin/node" ]]; then
  NODE_BIN="/Applications/ChatGPT.app/Contents/Resources/cua_node/bin/node"
fi
if [[ -z "$NODE_BIN" ]]; then
  NODE_BIN="$(command -v node || true)"
fi
if [[ -z "$NODE_BIN" || ! -x "$NODE_BIN" ]]; then
  echo "Pi Agent runtime requires Node.js." >&2
  exit 1
fi
if [[ ! -d "$RUNTIME_DIR/node_modules/@earendil-works/pi-agent-core" ]]; then
  echo "Pi Agent runtime is not installed. Run npm install in runtimes/pi first." >&2
  exit 1
fi

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi

export PI_AGENT_PORT="${PI_AGENT_PORT:-8653}"
export ZHANGGUI_API_BASE="${ZHANGGUI_API_BASE:-http://127.0.0.1:8000}"
export ZHANGGUI_PROJECT_ID="${ZHANGGUI_PROJECT_ID:-xinyu-hengtai-dakou}"

cd "$RUNTIME_DIR"
exec "$NODE_BIN" server.mjs
