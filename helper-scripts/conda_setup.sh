#!/usr/bin/env bash
# Run via src/slurm-scripts/conda_setup.sh (a login shell initializes Lmod).
# Conda is supplied by the cluster's Apptainer-backed Anaconda module.
set -euo pipefail
: "${SLURM_JOB_ID:?Run environment installation inside a Slurm allocation}"
if ! scontrol show hostnames "$SLURM_JOB_NODELIST" | grep -qxF "$(hostname -s)"; then
  echo 'Environment installation must run on an allocated compute node.' >&2
  exit 1
fi
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/AdaptPolicies}"
ENV_PREFIX="$HOME/.conda/envs/research_proj"
RESULTS_DIR="${RESULTS_DIR:-$HOME/outputs/conda_setup/$SLURM_JOB_ID}"
export CONDA_ENVS_PATH="$HOME/.conda/envs"
export CONDA_PKGS_DIRS="$HOME/.conda/pkgs"
export CONDA_CACHEDIR="$HOME/.conda/cache"
export PIP_CACHE_DIR="$HOME/.cache/pip"
export PYTHONNOUSERSITE=1
mkdir -p "$CONDA_ENVS_PATH" "$CONDA_PKGS_DIRS" "$CONDA_CACHEDIR" "$PIP_CACHE_DIR" "$RESULTS_DIR"
exec 9>"$HOME/.conda/research_proj-setup.lock"
flock -n 9 || { echo 'Another research_proj setup is already running.' >&2; exit 1; }
type module >/dev/null || { echo 'Run the setup job with its login-shell shebang to initialize modules.' >&2; exit 1; }
module load anaconda/anaconda-2025-12-2
cd "$PROJECT_ROOT"
echo "Installing research_proj at $ENV_PREFIX on $(hostname -s)"
conda --version
# Use the repository specification directly, including its declared channels,
# constraints and pip requirements. Repository ToS acceptance is a separate,
# explicitly authorized account operation, never automated by this script.
if [[ -f $ENV_PREFIX/conda-meta/history ]]; then
  conda env update --prefix "$ENV_PREFIX" --file environment.yml
else
  conda env create --prefix "$ENV_PREFIX" --file environment.yml --yes
fi
conda run --no-capture-output --prefix "$ENV_PREFIX" python -m pip check
conda run --no-capture-output --prefix "$ENV_PREFIX" python - "$ENV_PREFIX" "$RESULTS_DIR" <<'PY'
import importlib, importlib.metadata, json, pathlib, subprocess, sys
assert sys.version_info[:2] == (3, 10), sys.version
assert pathlib.Path(sys.prefix).resolve() == pathlib.Path(sys.argv[1]).resolve(), sys.prefix
modules = ["matplotlib", "openai", "ollama", "weave", "wandb", "uuid_utils", "PIL", "yaml"]
for name in modules:
    importlib.import_module(name)
for command in (["ffmpeg", "-version"], ["rustc", "--version"]):
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    print(result.stdout.splitlines()[0])
versions = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions() if d.metadata["Name"]}
(pathlib.Path(sys.argv[2]) / "dependency-versions.json").write_text(json.dumps(versions, indent=2, sort_keys=True))
print(f"PASS: Python {sys.version.split()[0]}, declared dependency imports, ffmpeg and Rust.")
print(f"Environment: {sys.prefix}")
PY
conda list --prefix "$ENV_PREFIX" --explicit > "$RESULTS_DIR/conda-explicit.txt"
conda run --no-capture-output --prefix "$ENV_PREFIX" python -m pip freeze > "$RESULTS_DIR/pip-freeze.txt"
echo "Environment setup and verification completed. Details: $RESULTS_DIR"
