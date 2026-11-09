#!/bin/bash

set -euo pipefail

# Copy dataset to output directory
echo "--- Copying Progprompt dataset to output directory ---"
cp -r "$PROGPROMPT_PREFIX"/data/* "$PROGPROMPT_DATASET_DIR"/

# Run progprompt script
echo "--- Running Progprompt Script ---"
python -m methods.progprompt.run_eval "$@"
