#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/web"
FRONTEND_URL="http://localhost:3005/overview"
BACKEND_PORT=8000
FRONTEND_PORT=3005

backend_pid=""
frontend_pid=""

is_listening() {
  local port="$1"
  lsof -iTCP:"$port" -sTCP:LISTEN -n -P >/dev/null 2>&1
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

if is_listening "$BACKEND_PORT"; then
  echo "后端服务已在 $BACKEND_PORT 端口运行，直接复用。"
else
  echo "启动数据/API服务..."
  cd "$ROOT_DIR"
  python3 -m uvicorn server.main:app --port "$BACKEND_PORT" &
  backend_pid="$!"
fi

if is_listening "$FRONTEND_PORT"; then
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
  if is_listening "$BACKEND_PORT" && is_listening "$FRONTEND_PORT"; then
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
