#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STOCK_ROOT="${STOCK_ROOT:-$(dirname "$ROOT")/stock-hermes}"
ENV_ROOT="${ENV_ROOT:-$(dirname "$ROOT")/env}"
mkdir -p "$ENV_ROOT"
RUN_ROOT="$(mktemp -d "$ENV_ROOT/test.XXXXXX")"
export HOME="$RUN_ROOT/home"
export HERMES_HOME="$RUN_ROOT/hermes"
export HERMES_RUNTIME_DIR="$ENV_ROOT/runtime"
export TMPDIR="$RUN_ROOT/tmp"
export PYTHONPATH="$STOCK_ROOT"
export PYTHONDONTWRITEBYTECODE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
mkdir -p "$HOME" "$HERMES_HOME" "$TMPDIR"
unset HERMES_PROFILE HERMES_CONFIG_PATH HERMES_BUNDLED_PLUGINS
cd "$ROOT"
exec "$STOCK_ROOT/.venv/bin/python" -m pytest tests -o addopts= -q -p no:cacheprovider "$@"
