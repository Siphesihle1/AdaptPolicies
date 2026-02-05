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

cleanup() {
  echo "--- Stopping VirtualHome Simulator ---"
  ps aux | grep -v "grep" | grep "Xvfb" | awk '{print $2}' | head -n 1 | xargs \
    kill -9 > /dev/null 2>&1 || true

  echo "--- Stopping Ollama Server ---"
  ps aux | grep -v "grep" | grep "ollama" | awk '{print $2}' | xargs \
    kill -9 > /dev/null 2>&1 || true
}

trap cleanup EXIT

# Starting the simulator
echo "--- Starting VirtualHome Simulator ---"
bash "$SCRIPT_DIR/run-sim.sh"

# Wait for the simulator to be ready
echo "--- Waiting for VirtualHome Simulator to be ready... ---"
time curl --retry 360 --retry-connrefused --retry-delay 2 -sf "http://127.0.0.1:$SIM_PORT"

# Start ollama server
echo "--- Starting ollama server ---"
bash "$SCRIPT_DIR/start_ollama.sh"
echo ""

echo "--- Running main script: $TARGET_SCRIPT ---"
bash "$TARGET_SCRIPT" "$@"
