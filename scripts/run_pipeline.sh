#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/runtime.env}"
PYTHON_BIN="${PYTHON_BIN:-python}"
LIMIT="${LIMIT:-0}"
START_ROW="${START_ROW:-0}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy configs/runtime.env.example to runtime.env first." >&2
  exit 2
fi

"$PYTHON_BIN" -m toolmed_agent.pipeline \
  --root-dir "$ROOT_DIR" \
  --env-file "$ENV_FILE" \
  --limit "$LIMIT" \
  --start-row "$START_ROW"
