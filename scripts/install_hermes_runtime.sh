#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${ZHANGGUI_HERMES_RUNTIME_DIR:-$HOME/.local/share/zhanggui-agent/hermes-runtime}"
HERMES_HOME_DIR="$RUNTIME_DIR/home"
VENV_DIR="$RUNTIME_DIR/venv"
SOURCE_DIR="$RUNTIME_DIR/source"
HERMES_COMMIT="339d968689a3b91c5f537d7198ff28abde32ab3b7d482"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

mkdir -p "$RUNTIME_DIR" "$HERMES_HOME_DIR"
chmod 700 "$RUNTIME_DIR" "$HERMES_HOME_DIR"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip

# Hermes intentionally rejects wheel/sdist builds. Its supported development
# path is an editable source install, kept here in the isolated sidecar runtime.
if [[ ! -d "$SOURCE_DIR/.git" ]]; then
  git clone --filter=blob:none https://github.com/NousResearch/hermes-agent.git "$SOURCE_DIR"
fi
if ! git -C "$SOURCE_DIR" cat-file -e "$HERMES_COMMIT^{commit}" 2>/dev/null; then
  git -C "$SOURCE_DIR" fetch --quiet origin main
fi
git -C "$SOURCE_DIR" checkout --quiet --detach "$HERMES_COMMIT"
"$VENV_DIR/bin/python" -m pip install --editable "$SOURCE_DIR"
# The OpenAI-compatible gateway adapter is in Hermes' optional messaging
# surface; install only its audited HTTP runtime instead of every chat SDK.
"$VENV_DIR/bin/python" -m pip install "aiohttp==3.14.1"

cp "$ROOT_DIR/.hermes/config.yaml" "$HERMES_HOME_DIR/config.yaml"
chmod 600 "$HERMES_HOME_DIR/config.yaml"

if [[ ! -s "$RUNTIME_DIR/api-server.key" ]]; then
  "$VENV_DIR/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))' > "$RUNTIME_DIR/api-server.key"
  chmod 600 "$RUNTIME_DIR/api-server.key"
fi

printf '%s\n' "$HERMES_COMMIT" > "$RUNTIME_DIR/version"
printf 'Hermes runtime installed at %s\n' "$RUNTIME_DIR"
