#!/usr/bin/env bash
#SBATCH --partition=bigbatch
#SBATCH --account=general
#SBATCH --job-name=lmstudio_test
#SBATCH --time=02:00:00
#SBATCH --signal=B:TERM@90
#SBATCH --output=/home-mscluster/%u/slurm-logs/lmstudio_test/%j.out
#SBATCH --error=/home-mscluster/%u/slurm-logs/lmstudio_test/%j.err

# No CPU, memory, GPU, node-count, or exclusive-allocation directives.
# Before submission: mkdir -p "$HOME/slurm-logs/lmstudio_test"
# sbatch src/slurm-scripts/lmstudio_test.sh [/absolute/path/to/model.gguf]
set -euo pipefail
: "${SLURM_JOB_ID:?Submit this script using sbatch}"

finish() {
  local exit_status=$?
  trap - EXIT TERM INT
  set +e
  if declare -F stop_lmstudio_model >/dev/null; then
    stop_lmstudio_model || { (( exit_status != 0 )) || exit_status=1; }
  fi
  local result=FAILED tags=warning
  if (( exit_status == 0 )); then result=COMPLETED; tags=white_check_mark; fi
  echo "LM Studio test $result (exit $exit_status)."
  curl --fail --silent --show-error --retry 2 --retry-delay 2 \
    --connect-timeout 5 --max-time 15 \
    --header "Title: Slurm LM Studio test $result" --header "Tags: $tags" \
    --data-binary "Job $SLURM_JOB_ID (lmstudio_test): $result. Exit code: $exit_status." \
    "${NTFY_SERVER:-https://ntfy.sh}/${NTFY_TOPIC:-research-project-slurm-job-alerts}" \
    >/dev/null || echo 'Warning: ntfy delivery failed.' >&2
  exit "$exit_status"
}
trap finish EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/AdaptPolicies}"
MODEL_PATH="${1:-/datasets/$(id -un)/lmstudio/models/ggml-org/Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf}"
RESULTS_DIR="$HOME/outputs/lmstudio_test/$SLURM_JOB_ID"
mkdir -p "$RESULTS_DIR"
cd "$PROJECT_ROOT"
echo "Job $SLURM_JOB_ID on $(hostname); partition $SLURM_JOB_PARTITION; account $SLURM_JOB_ACCOUNT"
echo "Persistent results: $RESULTS_DIR"

# Source rather than execute so the endpoint, model ID, lock, and cleanup hook
# remain available to this job after the helper returns.
source helper-scripts/load_lmstudio_model.sh "$MODEL_PATH"
"$LMSTUDIO_LMS_BIN" ps --json > "$RESULTS_DIR/loaded-models.json"
python3 - "$LMSTUDIO_MODEL_ID" "$RESULTS_DIR/request.json" <<'PY'
import json, sys
request = {
    "model": sys.argv[1],
    "messages": [{"role": "user", "content": "What is 2 + 2? Reply briefly. /no_think"}],
    "temperature": 0,
    "max_tokens": 512,
    "stream": False,
}
with open(sys.argv[2], "w") as f:
    json.dump(request, f)
PY
curl --fail --silent --show-error --noproxy '*' --connect-timeout 10 --max-time 1800 \
  --header 'Content-Type: application/json' --data-binary "@$RESULTS_DIR/request.json" \
  "$LMSTUDIO_BASE_URL/chat/completions" --output "$RESULTS_DIR/response.json"
python3 - "$RESULTS_DIR/response.json" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    response = json.load(f)
if response.get("error"):
    raise SystemExit(f"Model API error: {response['error']}")
choices = response.get("choices", [])
text = choices[0].get("message", {}).get("content") if choices else None
if not isinstance(text, str) or not text.strip():
    raise SystemExit("Test failed: the API returned no generated answer. See response.json.")
print("Model response:")
print(text)
print("PASS: the loaded model generated a non-empty answer through the API.")
PY
