#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${ZHANGGUI_HERMES_RUNTIME_DIR:-$HOME/.local/share/zhanggui-agent/hermes-runtime}"
LOG_DIR="$ROOT_DIR/output/runtime"
PID_FILE="$RUNTIME_DIR/gateway.pid"

mkdir -p "$LOG_DIR" "$RUNTIME_DIR"

if [[ -s "$PID_FILE" ]] && kill -0 "$(<"$PID_FILE")" 2>/dev/null; then
  echo "Hermes runtime is already running (PID $(<"$PID_FILE"))."
  exit 0
fi

nohup "$ROOT_DIR/scripts/run_hermes_runtime.sh" >>"$LOG_DIR/hermes.log" 2>&1 &
pid=$!
printf '%s\n' "$pid" > "$PID_FILE"

for _ in {1..30}; do
  if kill -0 "$pid" 2>/dev/null && curl -fsS "http://127.0.0.1:${HERMES_API_PORT:-8652}/health" >/dev/null 2>&1; then
    echo "Hermes runtime is ready (PID $pid)."
    exit 0
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "Hermes runtime exited during startup. See $LOG_DIR/hermes.log" >&2
    exit 1
  fi
  sleep 1
done

echo "Hermes runtime did not become healthy in 30 seconds." >&2
exit 1
