#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/web"
FRONTEND_URL="http://127.0.0.1:3005/overview"
BACKEND_PORT=8000
FRONTEND_PORT=3005
HERMES_PORT=8652
PI_PORT=8653
HERMES_RUNTIME_DIR="${ZHANGGUI_HERMES_RUNTIME_DIR:-$HOME/.local/share/zhanggui-agent/hermes-runtime}"

backend_pid=""
frontend_pid=""
hermes_pid=""
pi_pid=""

NODE_BIN="${NODE_BIN:-}"
CODEX_NODE="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
if [[ -z "$NODE_BIN" && -x "$CODEX_NODE" ]]; then NODE_BIN="$CODEX_NODE"; fi
if [[ -z "$NODE_BIN" ]]; then NODE_BIN="$(command -v node || true)"; fi
if [[ -n "$NODE_BIN" ]]; then export PATH="$(dirname "$NODE_BIN"):$PATH"; fi

PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "缺少项目 Python 环境：$PYTHON_BIN"
  echo "请先在项目目录创建 .venv 并安装 requirements.txt。"
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  echo "掌柜Agent 需要 Python 3.10 或更高版本。"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  for node_bin in /opt/homebrew/bin /usr/local/bin; do
    if [[ -x "$node_bin/npm" ]]; then
      export PATH="$node_bin:$PATH"
      break
    fi
  done
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "找不到 npm。请先安装 Node.js 22，并确保 npm 在 PATH 中。"
  exit 1
fi

is_listening() {
  local port="$1"
  lsof -iTCP:"$port" -sTCP:LISTEN -n -P >/dev/null 2>&1
}

is_http_ready() {
  local url="$1"
  curl --silent --fail --max-time 2 "$url" >/dev/null 2>&1
}

is_backend_ready() {
  is_http_ready "http://127.0.0.1:${BACKEND_PORT}/health" \
    && is_http_ready "http://127.0.0.1:${BACKEND_PORT}/api/projects/xinyu-hengtai-dakou/finance/overview?start=2026-07-01&end=2026-07-01"
}

is_backend_using_selected_runtime() {
  local selected="hermes"
  if [[ -f "$ROOT_DIR/runtimes/pi/enabled" ]]; then selected="pi"; fi
  curl --silent --fail --max-time 2 "http://127.0.0.1:${BACKEND_PORT}/api/agent/runtime" \
    | grep -q "\"selected\":\"${selected}\""
}

clear_stale_listener() {
  local port="$1"
  local service_name="$2"
  if is_listening "$port"; then
    echo "$service_name 占用了 $port 但没有响应，正在关闭假活进程..."
    lsof -tiTCP:"$port" -sTCP:LISTEN | xargs kill >/dev/null 2>&1 || true
    sleep 1
  fi
}

cleanup() {
  echo ""
  echo "正在关闭掌柜Agent..."
  if [[ -n "$frontend_pid" ]]; then kill "$frontend_pid" >/dev/null 2>&1 || true; fi
  if [[ -n "$backend_pid" ]]; then kill "$backend_pid" >/dev/null 2>&1 || true; fi
  if [[ -n "$hermes_pid" ]]; then kill "$hermes_pid" >/dev/null 2>&1 || true; fi
  if [[ -n "$pi_pid" ]]; then kill "$pi_pid" >/dev/null 2>&1 || true; fi
}

trap cleanup EXIT INT TERM

echo "掌柜Agent 本地启动器"
echo "项目目录: $ROOT_DIR"
echo ""

if [[ -f "$ROOT_DIR/runtimes/pi/enabled" ]]; then
  if is_http_ready "http://127.0.0.1:${PI_PORT}/health"; then
    echo "Pi Agent Core 已在 $PI_PORT 端口运行，直接复用。"
  else
    echo "启动 Pi Agent Core..."
    PI_AGENT_PORT="$PI_PORT" "$ROOT_DIR/scripts/run_pi_runtime.sh" &
    pi_pid="$!"
    for _ in {1..40}; do
      is_http_ready "http://127.0.0.1:${PI_PORT}/health" && break
      kill -0 "$pi_pid" >/dev/null 2>&1 || break
      sleep 0.5
    done
  fi
elif [[ -f "$HERMES_RUNTIME_DIR/enabled" ]]; then
  if is_http_ready "http://127.0.0.1:${HERMES_PORT}/health"; then
    echo "Hermes 店铺运行时已在 $HERMES_PORT 端口运行，直接复用。"
  else
    echo "启动 Hermes 店铺运行时..."
    HERMES_API_PORT="$HERMES_PORT" "$ROOT_DIR/scripts/run_hermes_runtime.sh" &
    hermes_pid="$!"
    for _ in {1..40}; do
      is_http_ready "http://127.0.0.1:${HERMES_PORT}/health" && break
      kill -0 "$hermes_pid" >/dev/null 2>&1 || break
      sleep 0.5
    done
  fi
fi

# A running backend cannot change its injected reasoning runtime in place.
# Restart only this product's listener so the backend and sidecar agree.
if { [[ -f "$ROOT_DIR/runtimes/pi/enabled" ]] || [[ -f "$HERMES_RUNTIME_DIR/enabled" ]]; } \
  && is_backend_ready && ! is_backend_using_selected_runtime; then
  echo "同步后端 Agent 运行时..."
  lsof -tiTCP:"$BACKEND_PORT" -sTCP:LISTEN | xargs kill >/dev/null 2>&1 || true
  sleep 1
fi

if is_listening "$BACKEND_PORT" && ! is_backend_ready; then
  clear_stale_listener "$BACKEND_PORT" "后端服务"
fi
if is_backend_ready; then
  echo "后端服务已在 $BACKEND_PORT 端口运行，直接复用。"
else
  echo "启动数据/API服务..."
  "$ROOT_DIR/scripts/run_backend_service.sh" &
  backend_pid="$!"
fi

if is_listening "$FRONTEND_PORT" && ! is_http_ready "http://127.0.0.1:${FRONTEND_PORT}/overview"; then
  clear_stale_listener "$FRONTEND_PORT" "网页服务"
fi
if is_http_ready "http://127.0.0.1:${FRONTEND_PORT}/overview"; then
  echo "网页服务已在 $FRONTEND_PORT 端口运行，直接复用。"
else
  echo "启动网页界面..."
  if [[ -z "$NODE_BIN" || ! -x "$NODE_BIN" ]]; then
    echo "找不到可用的 Node.js，无法启动网页界面。" >&2
    exit 1
  fi
  (
    cd "$WEB_DIR"
    "$NODE_BIN" "$WEB_DIR/node_modules/next/dist/bin/next" dev \
      -H 127.0.0.1 -p "$FRONTEND_PORT"
  ) &
  frontend_pid="$!"
fi

echo ""
echo "等待服务就绪..."
for _ in {1..60}; do
  if is_backend_ready \
    && is_http_ready "http://127.0.0.1:${FRONTEND_PORT}/overview"; then
    break
  fi
  sleep 0.5
done

echo ""
echo "已启动。浏览器会打开：$FRONTEND_URL"
echo "使用时只看浏览器里的 AI掌柜 页面。"
echo "不用时回到这个窗口按 Control+C，或直接关闭这个终端窗口。"
echo ""

open "$FRONTEND_URL" >/dev/null 2>&1 || true

while true; do
  sleep 3600
done
