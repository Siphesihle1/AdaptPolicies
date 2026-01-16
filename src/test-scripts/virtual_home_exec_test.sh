#!/bin/bash

# run the simulator

echo "--- Starting VirtualHome Simulator ---"

SIM_PID=$(VIRTUALHOME_SIM_VERSION=$VIRTUALHOME_SIM_VERSION VIRTUALHOME_ROOT=$VIRTUALHOME_ROOT SIM_PORT=$SIM_PORT bash $PROJECT_ROOT/helper-scripts/run-sim.sh)
SCRIPT_DIR="$(dirname "$(realpath "$0")")"

echo  "--- VirtualHome Simulator PID: $SIM_PID ---"

# Block using the ready endpoint
echo "--- Waiting for VirtualHome Simulator to be ready... ---"
time curl --retry 60 --retry-connrefused -sf http://127.0.0.1:$SIM_PORT

# Run test script
echo "--- Running VirtualHome Test Script ---"
python $PROJECT_ROOT/src/methods/progprompt/run_eval.py

# Kill the simulator
echo "--- Stopping VirtualHome Simulator (PID: $SIM_PID) ---"
kill -9 $SIM_PID

