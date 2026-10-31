#!/bin/bash

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

cleanup() {
  echo "--- Stopping VirtualHome Simulator ---"
  ps aux | grep -v "grep" | grep "Xvfb" | awk '{print $2}' | head -n 1 | xargs \
    kill -9 >/dev/null 2>&1 || true
}

trap cleanup EXIT

# Starting the simulator
echo "--- Starting VirtualHome Simulator ---"
bash "$SCRIPT_DIR/run-sim.sh"

# Wait for the simulator to be ready
echo "--- Waiting for VirtualHome Simulator to be ready... ---"
time curl --retry 360 --retry-connrefused --retry-delay 2 -sf \
  -H 'Content-Type: application/json' \
  -d '{"id":"readiness","action":"idle"}' \
  "http://127.0.0.1:$SIM_PORT"

# Other providers are managed externally. Only start a configured local Ollama.
if [ "$LLM_PROVIDER" = ollama ]; then
  bash "$SCRIPT_DIR/start_ollama.sh" || exit 1
fi

echo "--- Running main script: $TARGET_SCRIPT ---"
bash "$TARGET_SCRIPT" "$@"
