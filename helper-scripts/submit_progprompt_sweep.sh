#!/usr/bin/env bash
# Submit one Slurm job per dataset for a ProgPrompt sweep job script, placing
# jobs by current node availability. Runs on the login node (sbatch/squeue/sinfo
# only); the deploy workflow calls it through the job script:
#   bash src/slurm-scripts/progprompt_<model>.sh [DATASET ...]
# Expects SWEEP_CAMPAIGN, SWEEP_MODEL_TAG, SWEEP_PARTITIONS (preference order,
# space-separated) and SWEEP_TIME from the job script. Datasets default to all five.
#
# Placement: each dataset takes an idle node in the first preferred partition that
# still has one. With no idle node left, the job is queued on all allowed partitions
# together and starts on whichever frees up first. A dataset already queued or
# running for this script, or with all six runs completed, is not resubmitted.
# SWEEP_DRY_RUN=1 prints the placement and sbatch commands without submitting.
set -euo pipefail
(( $# >= 1 )) || { echo "Usage: $(basename "$0") JOB_SCRIPT [DATASET ...]" >&2; exit 2; }
: "${SWEEP_CAMPAIGN:?}" "${SWEEP_MODEL_TAG:?}" "${SWEEP_PLAN_TOKENS:?}" "${SWEEP_PARTITIONS:?}" "${SWEEP_TIME:?}"
if [[ -n ${SLURM_JOB_ID:-} ]]; then
  echo 'Submit from the login node, not from inside a Slurm job.' >&2
  exit 1
fi
job_script=$(realpath -e -- "$1")
shift
all_datasets=(test_seen test_unseen test_unseen_ambiguous_goals env1 env2)
datasets=("$@")
(( ${#datasets[@]} )) || datasets=("${all_datasets[@]}")
for dataset in "${datasets[@]}"; do
  [[ " ${all_datasets[*]} " == *" $dataset "* ]] || { echo "Unknown dataset: $dataset" >&2; exit 2; }
done
read -r -a partitions <<< "$SWEEP_PARTITIONS"
base=$(basename -- "$job_script" .sh)
mkdir -p "$HOME/slurm-logs/$base"

declare -A idle
echo "Node availability at $(date '+%F %T'):"
printf '  %-10s %5s %5s\n' partition idle total
for partition in "${partitions[@]}"; do
  idle[$partition]=$(sinfo -h -p "$partition" -t idle -o '%D' | awk '{n += $1} END {print n + 0}')
  total=$(sinfo -h -p "$partition" -o '%D' | awk '{n += $1} END {print n + 0}')
  printf '  %-10s %5s %5s\n' "$partition" "${idle[$partition]}" "$total"
done

submitted=0
for dataset in "${datasets[@]}"; do
  name="${base}_${dataset}"
  existing=$(squeue -h -u "$(id -un)" -n "$name" -o '%i %T' | head -n 1)
  if [[ -n $existing ]]; then
    echo "$dataset: already in the queue (job $existing); not resubmitted."
    continue
  fi
  # Count only runs at this dataset's current plan budget (run names contain m<tokens>).
  plan_tokens=$SWEEP_PLAN_TOKENS
  for pair in ${SWEEP_PLAN_TOKENS_BY_DATASET:-}; do
    if [[ ${pair%%=*} == "$dataset" ]]; then plan_tokens=${pair#*=}; fi
  done
  done_runs=0
  for code in "$HOME/outputs/experiments/$SWEEP_CAMPAIGN/$dataset/$SWEEP_MODEL_TAG"-*-m"$plan_tokens"-*-"$dataset"-r1/exit-code.txt; do
    [[ -f $code && $(<"$code") == 0 ]] && done_runs=$(( done_runs + 1 ))
  done
  if (( done_runs >= 6 )); then
    echo "$dataset: all six runs already completed; not resubmitted."
    continue
  fi
  target=""
  for partition in "${partitions[@]}"; do
    if (( idle[$partition] > 0 )); then
      target=$partition
      idle[$partition]=$(( idle[$partition] - 1 ))
      break
    fi
  done
  placement="idle node"
  if [[ -z $target ]]; then
    target=$(IFS=,; echo "${partitions[*]}")
    placement="queued; first free node"
  fi
  submit=(sbatch --parsable --partition="$target" --time="$SWEEP_TIME" --job-name="$name")
  # Nodes with known hardware faults (SWEEP_EXCLUDE_NODES, comma-separated).
  [[ -n ${SWEEP_EXCLUDE_NODES:-} ]] && submit+=(--exclude="$SWEEP_EXCLUDE_NODES")
  submit+=("$job_script" "$dataset")
  if [[ ${SWEEP_DRY_RUN:-0} == 1 ]]; then
    echo "$dataset: would run on $target ($placement): ${submit[*]}"
    continue
  fi
  job_id=$("${submit[@]}")
  echo "$dataset: job $job_id on $target ($placement)."
  submitted=$(( submitted + 1 ))
done
echo "Submitted $submitted job(s) for $base."
