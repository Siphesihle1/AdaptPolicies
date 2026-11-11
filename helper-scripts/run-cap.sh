#!/usr/bin/env bash
# Invoke through run_with_sim_and_ollama.sh for owned simulator startup/cleanup.
set -euo pipefail
python -m methods.cap.run_eval "$@"
