#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/output/runtime"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
HERMES_RUNTIME_DIR="${ZHANGGUI_HERMES_RUNTIME_DIR:-$HOME/.local/share/zhanggui-agent/hermes-runtime}"

mkdir -p "$LOG_DIR"
cd "$ROOT_DIR"

# Pi is the preferred embedded runtime once its audited project-local marker
# and dependencies are present. It owns orchestration only; store writes remain
# behind the FastAPI permission and confirmation contracts.
if [[ -f "$ROOT_DIR/runtimes/pi/enabled" && -d "$ROOT_DIR/runtimes/pi/node_modules/@earendil-works/pi-agent-core" ]]; then
  export AGENT_RUNTIME=pi
  export PI_AGENT_API_BASE="http://127.0.0.1:${PI_AGENT_PORT:-8653}"
elif [[ -f "$HERMES_RUNTIME_DIR/enabled" && -s "$HERMES_RUNTIME_DIR/api-server.key" ]]; then
  export AGENT_RUNTIME=hermes
  export HERMES_API_BASE="http://127.0.0.1:${HERMES_API_PORT:-8652}"
  export HERMES_API_KEY_FILE="$HERMES_RUNTIME_DIR/api-server.key"
fi

exec "$PYTHON_BIN" -m uvicorn server.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level info \
  >>"$LOG_DIR/backend.log" 2>&1
