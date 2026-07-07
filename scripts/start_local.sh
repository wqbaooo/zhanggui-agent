#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/web"
FRONTEND_URL="http://127.0.0.1:3005/overview"
BACKEND_PORT=8000
FRONTEND_PORT=3005

backend_pid=""
frontend_pid=""

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
}

trap cleanup EXIT INT TERM

echo "掌柜Agent 本地启动器"
echo "项目目录: $ROOT_DIR"
echo ""

if is_listening "$BACKEND_PORT" && ! is_http_ready "http://127.0.0.1:${BACKEND_PORT}/health"; then
  clear_stale_listener "$BACKEND_PORT" "后端服务"
fi
if is_http_ready "http://127.0.0.1:${BACKEND_PORT}/health"; then
  echo "后端服务已在 $BACKEND_PORT 端口运行，直接复用。"
else
  echo "启动数据/API服务..."
  cd "$ROOT_DIR"
  "$PYTHON_BIN" -m uvicorn server.main:app --port "$BACKEND_PORT" &
  backend_pid="$!"
fi

if is_listening "$FRONTEND_PORT" && ! is_http_ready "http://127.0.0.1:${FRONTEND_PORT}/overview"; then
  clear_stale_listener "$FRONTEND_PORT" "网页服务"
fi
if is_http_ready "http://127.0.0.1:${FRONTEND_PORT}/overview"; then
  echo "网页服务已在 $FRONTEND_PORT 端口运行，直接复用。"
else
  echo "启动网页界面..."
  cd "$WEB_DIR"
  npm run dev &
  frontend_pid="$!"
fi

echo ""
echo "等待服务就绪..."
for _ in {1..60}; do
  if is_http_ready "http://127.0.0.1:${BACKEND_PORT}/health" \
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
