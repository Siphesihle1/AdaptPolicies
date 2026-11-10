#!/bin/bash -l
#SBATCH --partition=batch
#SBATCH --account=general
#SBATCH --job-name=conda_setup
#SBATCH --time=02:00:00
#SBATCH --signal=B:TERM@90
#SBATCH --output=/home-mscluster/%u/slurm-logs/conda_setup/%j.out
#SBATCH --error=/home-mscluster/%u/slurm-logs/conda_setup/%j.err

# Before submitting: mkdir -p "$HOME/slurm-logs/conda_setup"
set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch}"
finish() {
  local status=$?
  trap - EXIT TERM INT
  local result=FAILED tags=warning
  if (( status == 0 )); then result=COMPLETED; tags=white_check_mark; fi
  echo "Conda setup $result (exit $status)."
  curl --fail --silent --show-error --retry 2 --retry-delay 2 \
    --connect-timeout 5 --max-time 15 \
    --header "Title: Slurm Conda setup $result" --header "Tags: $tags" \
    --data-binary "Job $SLURM_JOB_ID (conda_setup): $result. Exit code: $status." \
    "${NTFY_SERVER:-https://ntfy.sh}/${NTFY_TOPIC:-research-project-slurm-job-alerts}" \
    >/dev/null || echo 'Warning: ntfy delivery failed.' >&2
  exit "$status"
}
trap finish EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
export PROJECT_ROOT="${PROJECT_ROOT:-$HOME/AdaptPolicies}"
export RESULTS_DIR="$HOME/outputs/conda_setup/$SLURM_JOB_ID"
# Source so the exported Lmod shell function is available to the helper.
source "$PROJECT_ROOT/helper-scripts/conda_setup.sh"
