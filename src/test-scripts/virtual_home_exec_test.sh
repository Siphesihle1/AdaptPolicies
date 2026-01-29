#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"

# Starting the simulator
echo "--- Starting VirtualHome Simulator ---"
VIRTUALHOME_SIM_VERSION=$VIRTUALHOME_SIM_VERSION VIRTUALHOME_ROOT=$VIRTUALHOME_ROOT SIM_PORT=$SIM_PORT bash $PROJECT_ROOT/helper-scripts/run-sim.sh

# Wait for the simulator to be ready
echo "--- Waiting for VirtualHome Simulator to be ready... ---"
time curl --retry 360 --retry-connrefused --retry-delay 2 -sf http://127.0.0.1:$SIM_PORT

# Start ollama server
echo '--- Starting ollama server ---'
OLLAMA_HOST=$OLLAMA_HOST bash $PROJECT_ROOT/helper-scripts/start_ollama.sh
echo ""

PROGPROMPT_PREFIX=$PROJECT_ROOT/src/methods/progprompt

# Copy dataset to output directory
echo "--- Copying Progprompt dataset to output directory ---"

if [ ! -d "$DATASET_DIR/progprompt" ]; then
  mkdir $DATASET_DIR/progprompt
fi

cp -r $PROGPROMPT_PREFIX/data/ $DATASET_DIR/progprompt/

# Run test script
echo "--- Running VirtualHome Test Script ---"
python $PROGPROMPT_PREFIX/run_eval.py

# Kill the servers
echo "--- Stopping VirtualHome Simulator ---"
ps aux | grep -v "grep" | grep "Xvfb" | awk '{print $2}' | head -n 1 | xargs kill -9 > /dev/null 2>&1 || true

echo "--- Stopping Ollama Server ---"
ps aux | grep -v "grep" | grep "ollama" | awk '{print $2}' | xargs kill -9 > /dev/null 2>&1 || true

