#!/usr/bin/env bash
#SBATCH --account=general
#SBATCH --job-name=cap_qwen35_9b
#SBATCH --partition=batch
#SBATCH --time=24:00:00
#SBATCH --signal=B:TERM@300
#SBATCH --output=/home-mscluster/%u/slurm-logs/cap_qwen35_9b/%j.out
#SBATCH --error=/home-mscluster/%u/slurm-logs/cap_qwen35_9b/%j.err
# adaptpolicies: self-submit
#
# Code as Policies temperature x reasoning sweep for Qwen3.5-9B Q4_K_M, with the
# same model, conditions, datasets, examples (3 random, seed 42) and token
# budgets as the ProgPrompt sweep: 8192 tokens per request with a 600 s request
# timeout and a 1200 s task deadline; 16384 / 1200 s / 2400 s for ambiguous goals.
# Submit from the login node with bash (not sbatch); this checks node availability
# and submits one job per dataset (all five by default):
#   bash src/slurm-scripts/cap_qwen35_9b.sh [DATASET ...]
# Inside each job, helper-scripts/sweep.sh does the work.
# Worst case per job (every task hits its deadline) is about 20 h, inside batch's
# 1-day limit. A resubmission runs only the conditions that did not finish.
# Results: ~/outputs/experiments/$SWEEP_CAMPAIGN/<dataset>/<run>.
set -euo pipefail
export SWEEP_METHOD=cap
export SWEEP_MODEL_TAG=qwen35-9b
export SWEEP_MODEL_ID=qwen/qwen3.5-9b
export SWEEP_PLAN_TOKENS=8192   # config/cap-<tag>-<temp>-m8192-<reasoning>.yaml
export SWEEP_PLAN_TOKENS_BY_DATASET="test_unseen_ambiguous_goals=16384"
export SWEEP_GGUF="/datasets/$(id -un)/lmstudio/models/lmstudio-community/Qwen3.5-9B-GGUF/Qwen3.5-9B-Q4_K_M.gguf"
export SWEEP_CAMPAIGN="${SWEEP_CAMPAIGN:-cluster_cap_qwen35_9b_001}"
export SWEEP_PARTITIONS="batch bigbatch"
export SWEEP_TIME=24:00:00
# Known-faulty nodes, skipped at submission. mscluster76: GPU not found by
# nvidia-smi (2026-11-11), so LM Studio fell back to the CPU. mscluster68: same
# fault, caught by the GPU check (2026-11-12).
export SWEEP_EXCLUDE_NODES=mscluster68,mscluster76
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/AdaptPolicies}"

if [[ -z ${SLURM_JOB_ID:-} ]]; then
  exec bash "$PROJECT_ROOT/helper-scripts/submit_sweep.sh" "$(realpath -- "$0")" "$@"
fi
exec bash "$PROJECT_ROOT/helper-scripts/sweep.sh" "$@"
