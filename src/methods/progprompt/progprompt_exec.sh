#!/bin/bash

set -euo pipefail

python -c 'from methods.progprompt.run_eval import parse_args; parse_args()' "$@"
for argument in "$@"; do
  if [ "$argument" = --help ] || [ "$argument" = -h ]; then exit 0; fi
done

export PROGPROMPT_DATASET_DIR
export PROGPROMPT_PREFIX
export JOB_OUTPUT_DIR

bash "$PROJECT_ROOT/helper-scripts/run_with_sim_and_ollama.sh" \
  "$PROGPROMPT_PREFIX/progprompt_run.sh" "$@"

if [ -n "${SLURM_JOB_ID:-}" ]; then
  curl --fail --show-error \
    -d "Slurm job $SLURM_JOB_NAME with id $SLURM_JOB_ID running on $SLURM_JOB_NODELIST finished" \
    -H "Title: Slurm Job Alert: $SLURM_JOB_NAME" \
    ntfy.sh/research-project-slurm-job-alerts
fi
