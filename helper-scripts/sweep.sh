#!/usr/bin/env bash
# Run a ProgPrompt or Code as Policies (CaP) sweep for ONE dataset inside a
# Slurm job: temperatures 0, 0.6, 1.0 x reasoning off/on, one attempt per task.
#
# Started by src/slurm-scripts/<method>_<model>.sh, which sets:
#   SWEEP_METHOD       progprompt (default) or cap
#   SWEEP_MODEL_TAG    e.g. qwen35-9b
#   SWEEP_MODEL_ID     LM Studio model name used in the configs, e.g. qwen/qwen3.5-9b
#   SWEEP_PLAN_TOKENS  plan max_tokens in the config names, e.g. 8192
#   SWEEP_PLAN_TOKENS_BY_DATASET  optional overrides, e.g. "test_unseen_ambiguous_goals=16384"
#   SWEEP_GGUF         model file on /datasets
#   SWEEP_CAMPAIGN     results folder under ~/outputs/experiments
# Optional for quick tests: SWEEP_NUM_TASKS (default all).
#
# Each condition uses config/dev-<tag>-<temp>-m<tokens>-<reasoning>.yaml (ProgPrompt)
# or config/cap-<tag>-<temp>-m<tokens>-<reasoning>.yaml (CaP) and writes
# ~/outputs/experiments/<campaign>/<dataset>/<run id>/. A run with exit-code.txt = 0
# is complete and is never rerun, so resubmitting a dataset only runs what is
# missing. Older failed or interrupted attempts are kept with a suffix.
set -euo pipefail

dataset=${1:?Usage: sweep.sh DATASET}
method=${SWEEP_METHOD:-progprompt}
case $method in
  progprompt) label=ProgPrompt run_prefix="" ;;
  cap) label=CaP run_prefix="cap-" ;;
  *) echo "Unknown SWEEP_METHOD: $method" >&2; exit 2 ;;
esac
case $dataset in
  test_seen|test_unseen|test_unseen_ambiguous_goals) env_id=0 ;;
  env1) env_id=1 ;;
  env2) env_id=2 ;;
  *) echo "Unknown dataset: $dataset" >&2; exit 2 ;;
esac
plan_tokens=$SWEEP_PLAN_TOKENS
for pair in ${SWEEP_PLAN_TOKENS_BY_DATASET:-}; do
  if [[ ${pair%%=*} == "$dataset" ]]; then plan_tokens=${pair#*=}; fi
done

REPO="${PROJECT_ROOT:-$HOME/AdaptPolicies}"
ENV_PREFIX="$HOME/.conda/envs/research_proj"
RESULTS="$HOME/outputs/experiments/$SWEEP_CAMPAIGN/$dataset"
RECORD="$RESULTS/jobs/$SLURM_JOB_ID"   # provenance for this job
WORK=""                                # node-local work folder, set after staging
current_run=""
child=""
completed=0 skipped=0 failed=0

notify() {  # notify TITLE MESSAGE
  curl --fail --silent --show-error --retry 2 --max-time 15 \
    --header "Title: $1" --data-binary "$2" \
    "${NTFY_SERVER:-https://ntfy.sh}/${NTFY_TOPIC:-research-project-slurm-job-alerts}" \
    >/dev/null || echo 'Warning: ntfy delivery failed.' >&2
}

cleanup() {
  local status=$?
  trap - EXIT TERM INT
  set +e
  # Keep a run that was interrupted (e.g. by the time limit), never as a result.
  if [[ -n $current_run ]]; then
    copy_home "$WORK/runs/$current_run" "$RESULTS/$current_run.incomplete-$SLURM_JOB_ID"
  fi
  declare -F stop_lmstudio_model >/dev/null && stop_lmstudio_model
  declare -F remove_staged_simulator >/dev/null && remove_staged_simulator
  [[ -n $WORK ]] && rm -rf -- "$WORK"

  local result=COMPLETED
  (( status == 0 )) || result=FAILED
  local summary="$completed completed, $skipped already done, $failed failed"
  echo "$label $SWEEP_MODEL_TAG $dataset: $result ($summary), exit $status"
  echo "$result: $summary, exit $status" > "$RECORD/finished.txt"
  notify "Slurm $label $SWEEP_MODEL_TAG $dataset $result" \
    "Job $SLURM_JOB_ID on $(hostname -s): $summary. Exit code: $status."
  exit "$status"
}

stop_child() {  # Slurm signals only this shell; stop the running evaluation too.
  [[ -n $child ]] && kill -TERM -- "-$child" 2>/dev/null
  wait "$child" 2>/dev/null
  exit 143
}

setup_environment() {
  # The env's activation hook holds the API keys and VIRTUALHOME_SIM_ROOT
  # (written by the deploy workflow); otherwise use the repository defaults.
  export CONDA_PREFIX="$ENV_PREFIX" PROJECT_ROOT="$REPO"
  local hook="$ENV_PREFIX/etc/conda/activate.d/env_vars.sh"
  [[ -f $hook ]] || hook="$REPO/env_vars/activate_env_vars.sh"
  source "$hook"
  export PATH="$ENV_PREFIX/bin:$PATH"
  export PYTHONHASHSEED=42 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LIBGL_ALWAYS_SOFTWARE=1
  export VIRTUALHOME_DISPLAY_PREFIX="${VIRTUALHOME_DISPLAY_PREFIX:-$HOME/.conda/envs/vh_display}"
  : "${WANDB_API_KEY:?missing; Weave is enabled in the configs}"
  : "${PROJECT_NAME:?missing; Weave needs a project name}"
}

snapshot_code() {
  # Run from a node-local copy so a later deploy cannot change code mid-job.
  mkdir -p "$WORK/repo" "$WORK/runs"
  git -C "$REPO" rev-parse HEAD > "$RECORD/git-commit.txt"
  git -C "$REPO" status --porcelain > "$RECORD/git-status.txt"
  tar -C "$REPO" --exclude=./.git --exclude=./outputs -cf - . | tar -C "$WORK/repo" -xf -

  export PROJECT_ROOT="$WORK/repo"
  local vh="$PROJECT_ROOT/src/virtual_home"
  export PYTHONPATH="$PROJECT_ROOT/src:$vh:$vh/virtualhome/src:$vh/virtualhome/src/virtualhome:$vh/virtualhome/src/virtualhome/simulation"
  export PROGPROMPT_PREFIX="$PROJECT_ROOT/src/methods/progprompt"
}

load_model() {
  # Without a working GPU the loader falls back to the CPU engine (the 27B ran at
  # ~0.6 tok/s on mscluster76), and every run would time out. Stop instead.
  nvidia-smi -L > /dev/null 2>&1 || { echo "No working GPU on $(hostname -s)." >&2; exit 1; }
  export LMSTUDIO_MODEL_ID="$SWEEP_MODEL_ID" LMSTUDIO_CONTEXT_LENGTH=64000 LMSTUDIO_PORT=1234
  source "$REPO/helper-scripts/load_lmstudio_model.sh" "$SWEEP_GGUF"
  [[ $LMSTUDIO_ENGINE == *cuda* ]] || { echo "Not a CUDA engine: $LMSTUDIO_ENGINE" >&2; exit 1; }
}

record_provenance() {
  {
    echo "job=$SLURM_JOB_ID node=$(hostname -s) partition=$SLURM_JOB_PARTITION"
    echo "method=$method dataset=$dataset env_id=$env_id model=$SWEEP_MODEL_ID gguf=$SWEEP_GGUF"
    echo "plan_tokens=$plan_tokens context=$LMSTUDIO_CONTEXT_LENGTH engine=$LMSTUDIO_ENGINE"
    echo "started=$(date -u +%FT%TZ)"
  } > "$RECORD/job.txt"
  "$LMSTUDIO_LMS_BIN" ps --json > "$RECORD/model-load.json"
  # Memory used after loading shows whether the whole model is on the GPU.
  nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv \
    > "$RECORD/gpu.csv" || true
  python -m pip freeze > "$RECORD/pip-freeze.txt"
}

run_condition() {  # run_condition TEMP REASONING, e.g. t06 ron
  local experiment="$run_prefix$SWEEP_MODEL_TAG-$1-m$plan_tokens-$2"
  local run_id="$experiment-$dataset-r1"
  local final="$RESULTS/$run_id"
  local run_dir="$WORK/runs/$run_id"

  if [[ $(cat "$final/exit-code.txt" 2>/dev/null) == 0 ]]; then
    echo "Already completed: $run_id"
    skipped=$(( skipped + 1 ))
    return
  fi
  [[ -e $final ]] && mv "$final" "$final.previous-$(date +%Y%m%d%H%M%S)"

  mkdir -p "$run_dir/dataset"
  local config="$PROJECT_ROOT/config/dev-$experiment.yaml"
  [[ $method == cap ]] && config="$PROJECT_ROOT/config/$experiment.yaml"
  cp "$config" "$run_dir/config.yaml"
  export ADAPT_CONFIG="$run_dir/config.yaml" EXPERIMENT_REPEAT=1 EXPERIMENT_RUN_ID="$run_id"
  export JOB_OUTPUT_DIR="$run_dir" PROGPROMPT_DATASET_DIR="$run_dir/dataset"
  export LLM_METRICS_FILE="$run_dir/llm_calls.jsonl"
  # ProgPrompt copies the dataset into the run folder itself; CaP reads it from
  # there too, so both record the exact data each run used.
  local runner=("$PROGPROMPT_PREFIX/progprompt_exec.sh")
  if [[ $method == cap ]]; then
    cp -r "$PROGPROMPT_PREFIX"/data/. "$run_dir/dataset/"
    runner=("$PROJECT_ROOT/helper-scripts/run_with_sim_and_ollama.sh" "$PROJECT_ROOT/helper-scripts/run-cap.sh")
  fi

  echo "$(date +%T) Starting $run_id"
  current_run=$run_id
  # Own process group so a time-limit signal reaches the whole evaluation.
  # Without SLURM_JOB_ID, progprompt_exec.sh sends no per-run notification.
  setsid env -u SLURM_JOB_ID bash "${runner[@]}" \
    --expt-name "$experiment" --env-id "$env_id" --test-set "$dataset" \
    --examples-type random --examples-num 3 --num-tasks "${SWEEP_NUM_TASKS:-all}" \
    < /dev/null > "$run_dir/experiment.log" 2>&1 &
  child=$!
  local status=0
  wait "$child" || status=$?
  child=""

  # Copy results home; exit-code.txt is written last and marks the run complete.
  copy_home "$run_dir" "$final"
  echo "$status" > "$final/exit-code.txt"
  rm -rf -- "$run_dir"
  current_run=""
  echo "$(date +%T) Finished $run_id (exit $status)"

  if (( status == 0 )); then
    completed=$(( completed + 1 ))
  else
    failed=$(( failed + 1 ))
    # If the model server died, the remaining runs would fail the same way.
    curl --fail --silent --max-time 10 "$LMSTUDIO_BASE_URL/models" > /dev/null || exit 1
  fi
}

make_home_dir() {  # make_home_dir DIR (inside $HOME)
  # Home is NFS: a node can cache a stale "does not exist" for a folder that a
  # job on another node created, and mkdir then fails with "Already exists".
  # Listing each parent on the way down refreshes those cached entries.
  local path=$HOME part IFS=/
  for part in ${1#"$HOME"/}; do
    ls "$path" > /dev/null
    path+="/$part"
    [[ -d $path ]] || mkdir "$path" 2>/dev/null || { ls "${path%/*}" > /dev/null; [[ -d $path ]]; }
  done
}

copy_home() {  # copy_home SRC DEST: copy a node-local folder into home storage
  # tar instead of cp -r: the nodes' cp (uutils) failed with "File exists" on a
  # destination folder it had just created on NFS.
  make_home_dir "$2"
  tar -C "$1" -cf - . | tar -C "$2" -xf -
}

# ---- main ----
make_home_dir "$RECORD"
trap cleanup EXIT
trap stop_child TERM INT
echo "Job $SLURM_JOB_ID on $(hostname -s): $label $SWEEP_MODEL_TAG, $dataset"

setup_environment
source "$REPO/helper-scripts/stage_simulator.sh"   # simulator -> /var/tmp
WORK="$ADAPT_NODE_TMP/$method-job-$SLURM_JOB_ID"
snapshot_code
load_model                                          # model -> /var/tmp, served on :1234
record_provenance

for temp in t0 t06 t10; do
  for reasoning in roff ron; do
    run_condition "$temp" "$reasoning"
  done
done
(( failed == 0 ))
