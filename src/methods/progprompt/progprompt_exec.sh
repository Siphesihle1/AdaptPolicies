#!/bin/bash

export PROGPROMPT_DATASET_DIR
export PROGPROMPT_PREFIX
export JOB_OUTPUT_DIR

bash "$PROJECT_ROOT/helper-scripts/run_with_sim_and_ollama.sh" \
  "$PROGPROMPT_PREFIX/progprompt_run.sh"
