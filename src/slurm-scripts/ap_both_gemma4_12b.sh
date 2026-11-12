#!/usr/bin/env bash
#SBATCH --account=general
#SBATCH --job-name=ap_both_gemma4_12b
#SBATCH --partition=bigbatch
#SBATCH --time=2-00:00:00
#SBATCH --signal=B:TERM@300
#SBATCH --output=/home-mscluster/%u/slurm-logs/ap_both_gemma4_12b/%j.out
#SBATCH --error=/home-mscluster/%u/slurm-logs/ap_both_gemma4_12b/%j.err
# adaptpolicies: self-submit
#
# Adaptive Policies sweep for Gemma 4 12B Q4_K_M (main condition: model-written checkpoints and checkpoints on failed actions).
# Same conditions as the CaP sweep: temperature 0/0.6/1.0 x reasoning off/on, the five
# test sets, 3 random examples (seed 42; AP versions of the same training tasks) and
# 8192 tokens per request with a 600 s request timeout (16384 / 1200 s for ambiguous
# goals). AP allows 64 model requests per task (CaP 32) and a 1.5x task deadline for
# recovery generation: 1800 s (3600 s for ambiguous goals).
# Configs: config/ap-both-<tag>-<temp>-m<tokens>-<reasoning>.yaml.
# Submit from the login node with bash (not sbatch); this checks node availability
# and submits one job per dataset (all five by default):
#   bash src/slurm-scripts/ap_both_gemma4_12b.sh [DATASET ...]
# Inside each job, helper-scripts/sweep.sh does the work.
# Worst case per job (every task hits its deadline) is about 30 h, beyond batch's
# 1-day limit; such a job is cut off and its resubmission runs only the conditions
# that did not finish. Typical runs take far less than the deadline.
# Results: ~/outputs/experiments/$SWEEP_CAMPAIGN/<dataset>/<run>.
set -euo pipefail
export SWEEP_METHOD=adaptive
export SWEEP_PLACEMENT=both
export SWEEP_MODEL_TAG=gemma4-12b
export SWEEP_MODEL_ID=google/gemma-4-12b
export SWEEP_PLAN_TOKENS=8192   # config/ap-both-<tag>-<temp>-m8192-<reasoning>.yaml
export SWEEP_PLAN_TOKENS_BY_DATASET="test_unseen_ambiguous_goals=16384"
export SWEEP_GGUF="/datasets/$(id -un)/lmstudio/models/lmstudio-community/gemma-4-12B-it-GGUF/gemma-4-12B-it-Q4_K_M.gguf"
export SWEEP_CAMPAIGN="${SWEEP_CAMPAIGN:-cluster_ap_both_gemma4_12b_001}"
export SWEEP_PARTITIONS="bigbatch"
export SWEEP_TIME=2-00:00:00
# Known-faulty nodes, skipped at submission. mscluster76: GPU not found by
# nvidia-smi (2026-11-11), so LM Studio fell back to the CPU. mscluster68: same
# fault, caught by the GPU check (2026-11-12).
export SWEEP_EXCLUDE_NODES=mscluster68,mscluster76
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/AdaptPolicies}"

if [[ -z ${SLURM_JOB_ID:-} ]]; then
  exec bash "$PROJECT_ROOT/helper-scripts/submit_sweep.sh" "$(realpath -- "$0")" "$@"
fi
exec bash "$PROJECT_ROOT/helper-scripts/sweep.sh" "$@"
