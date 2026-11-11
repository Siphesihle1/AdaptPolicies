#!/usr/bin/env bash
#SBATCH --account=general
#SBATCH --job-name=progprompt_qwen38_27b
#SBATCH --partition=bigbatch
#SBATCH --time=2-00:00:00
#SBATCH --signal=B:TERM@300
#SBATCH --output=/home-mscluster/%u/slurm-logs/progprompt_qwen38_27b/%j.out
#SBATCH --error=/home-mscluster/%u/slurm-logs/progprompt_qwen38_27b/%j.err
# adaptpolicies: self-submit
#
# ProgPrompt temperature x reasoning sweep for Qwen3.8-27B Q4_K_M with the same
# six conditions, datasets and settings (8192 plan tokens, 600 s timeout) as the
# Qwen3.5-9B sweep.
# Submit from the login node with bash (not sbatch); this checks node availability
# and submits one job per dataset (all five by default):
#   bash src/slurm-scripts/progprompt_qwen38_27b.sh [DATASET ...]
# Inside each job, helper-scripts/progprompt_sweep.sh does the work.
# bigbatch only: the 19.4 GB model needs the 24 GB RTX 3090. A batch node's 12 GB
# RTX 3060 would push most layers onto 6 CPU cores, making generation far slower
# than the 600 s request timeout allows and confounding the comparison.
# Results: ~/outputs/experiments/$SWEEP_CAMPAIGN/<dataset>/<run>.
set -euo pipefail
export SWEEP_MODEL_TAG=qwen38-27b
export SWEEP_MODEL_ID=qwen/qwen3.8-27b
export SWEEP_PLAN_TOKENS=8192   # config/dev-<tag>-<temp>-m8192-<reasoning>.yaml
# Open-ended goals get a larger budget (configs set a 1200 s timeout for m16384).
export SWEEP_PLAN_TOKENS_BY_DATASET="test_unseen_ambiguous_goals=16384"
export SWEEP_GGUF="/datasets/$(id -un)/lmstudio/models/ggml-org/Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf"
export SWEEP_CAMPAIGN="${SWEEP_CAMPAIGN:-cluster_qwen38_27b_002}"
export SWEEP_PARTITIONS="bigbatch"
export SWEEP_TIME=2-00:00:00
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/AdaptPolicies}"

if [[ -z ${SLURM_JOB_ID:-} ]]; then
  exec bash "$PROJECT_ROOT/helper-scripts/submit_progprompt_sweep.sh" "$(realpath -- "$0")" "$@"
fi
exec bash "$PROJECT_ROOT/helper-scripts/progprompt_sweep.sh" "$@"
