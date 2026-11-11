#!/usr/bin/env bash
set -euo pipefail
# This Python runs only the operator controller. Gateway and Hermes CLI calls
# use stock PM's native .hermes/bin/hermes entry point, never this dev venv.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/../stock-hermes/.venv/bin/python" "$ROOT/scripts/demo_fixture.py" down "$@"
