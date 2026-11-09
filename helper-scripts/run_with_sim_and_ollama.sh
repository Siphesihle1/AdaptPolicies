#!/bin/bash

set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") /path/to/script.sh [args...]" >&2
}

if [ $# -lt 1 ]; then
  usage
  exit 1
fi

TARGET_SCRIPT="$1"
shift

if [ ! -f "$TARGET_SCRIPT" ]; then
  echo "Script not found: $TARGET_SCRIPT" >&2
  exit 1
fi

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
export ADAPT_CONFIG=${ADAPT_CONFIG:-dev}
LLM_PROVIDER=$(python -m methods.config) || exit 1

SIM_GROUP=''
cleanup() {
  result=$?
  trap - EXIT INT TERM
  if [ -n "$SIM_GROUP" ]; then
    echo "--- Stopping owned VirtualHome simulator/Xvfb group $SIM_GROUP ---"
    kill -TERM -- "-$SIM_GROUP" 2>/dev/null || true
    for attempt in $(seq 1 10); do
      if ! kill -0 -- "-$SIM_GROUP" 2>/dev/null; then break; fi
      sleep 0.2
    done
    if kill -0 -- "-$SIM_GROUP" 2>/dev/null; then
      kill -KILL -- "-$SIM_GROUP" 2>/dev/null || true
    fi
  fi
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

python - <<'PY'
import os
import socket

with socket.socket() as probe:
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    probe.bind(("127.0.0.1", int(os.environ["SIM_PORT"])))
PY

# Starting the simulator
echo "--- Starting VirtualHome Simulator ---"
mkdir -p "$JOB_OUTPUT_DIR"
SIM_FOREGROUND=1 setsid bash "$SCRIPT_DIR/run-sim.sh" \
  > "$JOB_OUTPUT_DIR/simulator-stdout.log" 2>&1 &
SIM_GROUP=$!
printf '%s\n' "$SIM_GROUP" > "$JOB_OUTPUT_DIR/simulator-process-group.txt"

# Wait for the simulator to be ready
echo "--- Waiting for VirtualHome Simulator to be ready... ---"
SIM_READY=false
for attempt in $(seq 1 90); do
  if curl --max-time 2 -sf -H 'Content-Type: application/json' \
    -d '{"id":"readiness","action":"idle"}' \
    "http://127.0.0.1:$SIM_PORT" | grep -Eq '"success"[[:space:]]*:[[:space:]]*true'; then
    SIM_READY=true
    break
  fi
  if ! kill -0 -- "-$SIM_GROUP" 2>/dev/null; then
    echo "Simulator exited before becoming ready; see $JOB_OUTPUT_DIR/Player.log" >&2
    exit 1
  fi
  sleep 1
done
if [ "$SIM_READY" != true ]; then
  echo "Simulator did not become ready on port $SIM_PORT" >&2
  exit 1
fi

# Other providers are managed externally. Only start a configured local Ollama.
if [ "$LLM_PROVIDER" = ollama ]; then
  bash "$SCRIPT_DIR/start_ollama.sh" || exit 1
fi

echo "--- Running main script: $TARGET_SCRIPT ---"
bash "$TARGET_SCRIPT" "$@"
