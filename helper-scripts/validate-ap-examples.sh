#!/usr/bin/env bash
# Validate the Adaptive Policies few-shot examples in the simulator (V2-V5).
# No model is contacted: a deterministic generator returns the example code.
#
# Usage (repository root, inside the project's Python environment):
#   VIRTUALHOME_SIM_ROOT=/path/to/player bash helper-scripts/validate-ap-examples.sh \
#     OUTPUT_DIR [validate_examples options, e.g. --policies explicit --scenarios R1]
# The simulator is started and stopped by run_with_sim_and_ollama.sh. Results are
# printed and written to OUTPUT_DIR/validation-report.json.
set -euo pipefail
output=${1:?Usage: validate-ap-examples.sh OUTPUT_DIR [options]}
shift
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export PROJECT_ROOT=$REPO
source "$REPO/env_vars/activate_env_vars.sh"
export ADAPT_CONFIG=${ADAPT_CONFIG:-$REPO/config/adaptive.yml}
export PROGPROMPT_DATASET_DIR=${PROGPROMPT_DATASET_DIR:-$REPO/src/methods/progprompt/data}
export LIBGL_ALWAYS_SOFTWARE=${LIBGL_ALWAYS_SOFTWARE:-1}
export PYTHONHASHSEED=42 PYTHONUNBUFFERED=1
mkdir -p "$output"
export JOB_OUTPUT_DIR=$(realpath "$output")
export GIT_COMMIT=$(git -C "$REPO" rev-parse HEAD 2>/dev/null || true)
runner=$(mktemp)
trap 'rm -f "$runner"' EXIT
printf '#!/usr/bin/env bash\nset -euo pipefail\npython -m methods.adaptive.validate_examples --output "$JOB_OUTPUT_DIR" "$@"\n' > "$runner"
bash "$REPO/helper-scripts/run_with_sim_and_ollama.sh" "$runner" "$@"
