#!/usr/bin/env bash
#SBATCH --partition=bigbatch
#SBATCH --job-name=lmstudio_download
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=04:00:00
#SBATCH --output=/home-mscluster/%u/slurm-logs/lmstudio_download/%j.out
#SBATCH --error=/home-mscluster/%u/slurm-logs/lmstudio_download/%j.err

set -euo pipefail

# Log directories must exist before sbatch; the GitHub workflow creates them.
# Manual submission: mkdir -p "$HOME/slurm-logs/lmstudio_download"
: "${SLURM_JOB_ID:?Submit this script with sbatch}"
: "${SLURM_JOB_NODELIST:?Missing Slurm node allocation}"

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/AdaptPolicies}"
export LMSTUDIO_MODELS_DIR="${LMSTUDIO_MODELS_DIR:-/datasets/$(id -un)/lmstudio/models}"

echo "Job ID: $SLURM_JOB_ID"
echo "Allocated nodes: $SLURM_JOB_NODELIST"
echo "Running on: $(hostname)"
echo "Master models directory: $LMSTUDIO_MODELS_DIR"

cd "$PROJECT_ROOT"

# Fail early if compute nodes cannot reach Hugging Face.
curl --fail --silent --show-error --location \
  --connect-timeout 15 --max-time 60 \
  https://huggingface.co/ -o /dev/null

# Download the pinned Qwen3.8-27B Q4_K_M GGUF, resume partial transfers,
# and verify its size and SHA-256 before publishing the completed file.
bash helper-scripts/lmstudio_setup.sh --download-only

echo "Model download completed and verified."
