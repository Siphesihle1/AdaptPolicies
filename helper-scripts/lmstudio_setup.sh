#!/usr/bin/env bash

# Install LM Studio's headless daemon (llmster) for the current Linux user.
# Usage: bash helper-scripts/lmstudio_setup.sh [--update] [--download-model]
# On a datasets transfer node or allocated Slurm node: use --download-only.
# The official installer fetches its current release. Existing installations
# are reused unless --update is supplied; the installer and log are retained.
# Model weights are pinned separately below. This script never stages weights
# to /scratch, starts a daemon, or loads a model: those belong in a Slurm job.
set -euo pipefail

update=0
download_model=0
download_only=0
while (( $# )); do
  case "$1" in
    --update) update=1 ;;
    --download-model) download_model=1 ;;
    --download-only) download_model=1; download_only=1 ;;
    -h|--help)
      cat <<'USAGE'
Usage: lmstudio_setup.sh [--update] [--download-model | --download-only]
  No flags          Install/reuse llmster and link ~/.local/bin/lms.
  --update          Update llmster using the current official installer.
  --download-model  Also download the pinned Qwen3.8-27B Q4_K_M model.
  --download-only   Download weights without installing or running LM Studio.

Run downloads on the datasets transfer node (cluster guide section 8.1):
  ssh <username>@10.100.14.250
  bash /path/to/helper-scripts/lmstudio_setup.sh --download-only
Or submit src/slurm-scripts/lmstudio_download.sh through Slurm.

Environment overrides:
  LMSTUDIO_MODELS_DIR      Master directory (default /datasets/<user>/lmstudio/models)
  LMSTUDIO_DOWNLOAD_HOST   Transfer-node IP (default 10.100.14.250)

Staging to /scratch and loading into RAM/VRAM belong in a separate Slurm job.
USAGE
      exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
if (( download_only && update )); then
  echo "--download-only cannot be combined with --update." >&2
  exit 2
fi

if [[ $(uname -s) != Linux ]]; then
  echo "This setup script targets Linux cluster accounts." >&2
  exit 1
fi

: "${HOME:?HOME must point to your cluster home directory}"
command_dir="$HOME/.local/bin"
lms_command="$command_dir/lms"
install_cache="${XDG_CACHE_HOME:-$HOME/.cache}/lmstudio-install"
install_script="$install_cache/install.sh"
install_log="$install_cache/install.log"
models_dir="${LMSTUDIO_MODELS_DIR:-/datasets/$(id -un)/lmstudio/models}"
download_host="${LMSTUDIO_DOWNLOAD_HOST:-10.100.14.250}"
# Hugging Face metadata pins both the exact artifact and its SHA-256/size.
# https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF
model_repo="ggml-org/Qwen3.8-27B-GGUF"
model_revision="8ccda149192dec5f41450a402e66889e5fd25a24"
model_filename="Qwen3.8-27B-Q4_K_M.gguf"
model_sha256="d15d4b6de55f662ac40e867702d31afe738d032fa06b829b2b1a21a49d4a48ee"
model_bytes=19403684480

download_master_model() (
  set -euo pipefail
  for dependency in curl sha256sum flock hostname stat df awk; do
    command -v "$dependency" >/dev/null 2>&1 || {
      echo "Required download command is missing: $dependency" >&2; exit 1;
    }
  done
  local allocated_node=0
  if [[ -n "${SLURM_JOB_ID:-}" && -n "${SLURM_JOB_NODELIST:-}" ]] && \
      command -v scontrol >/dev/null 2>&1; then
    if scontrol show hostnames "$SLURM_JOB_NODELIST" | grep -qxF "$(hostname -s)"; then
      allocated_node=1
    fi
  fi
  if [[ " $(hostname -I) " != *" $download_host "* ]] && (( ! allocated_node )); then
    echo "Run the download on transfer node $download_host or inside a Slurm allocation." >&2
    echo "Do not download model weights on the shared login node." >&2
    exit 1
  fi
  if [[ "$models_dir" != /* ]]; then
    echo "LMSTUDIO_MODELS_DIR must be an absolute path." >&2
    exit 1
  fi
  local target_dir="$models_dir/$model_repo"
  mkdir -p "$target_dir"
  # Serialize downloads of this artifact; never treat a partial file as ready.
  exec 9>"$target_dir/.$model_filename.lock"
  flock 9
  local target="$target_dir/$model_filename"
  local partial="$target.part"
  if [[ -f "$target" ]]; then
    printf '%s  %s\n' "$model_sha256" "$target" | sha256sum --check -
    echo "Master model already verified: $target"
    exit 0
  fi
  local partial_bytes=0 available_bytes required_bytes
  if [[ -f "$partial" ]]; then partial_bytes=$(stat -c %s "$partial"); fi
  if (( partial_bytes > model_bytes )); then
    echo "Partial file is larger than the pinned model; inspect $partial" >&2
    exit 1
  fi
  available_bytes=$(df -PB1 "$target_dir" | awk 'NR==2 {print $4}')
  required_bytes=$(( model_bytes - partial_bytes + 1073741824 ))
  if (( available_bytes < required_bytes )); then
    echo "Insufficient free space for the model and a 1 GiB reserve." >&2
    exit 1
  fi
  echo "Downloading $model_repo at revision $model_revision"
  echo "Destination: $target ($model_bytes bytes); partial downloads resume."
  if (( partial_bytes < model_bytes )); then
    curl --fail --location --silent --show-error --retry 3 \
      --connect-timeout 15 --speed-time 120 --speed-limit 1024 \
      --continue-at - --output "$partial" \
      "https://huggingface.co/$model_repo/resolve/$model_revision/$model_filename"
  fi
  [[ $(stat -c %s "$partial") == "$model_bytes" ]] || {
    echo "Downloaded size does not match the pinned model." >&2; exit 1;
  }
  printf '%s  %s\n' "$model_sha256" "$partial" | sha256sum --check -
  mv -- "$partial" "$target"
  printf '%s  %s\n' "$model_sha256" "$model_filename" > "$target.sha256"
  printf 'repository=%s\nrevision=%s\nbytes=%s\n' \
    "$model_repo" "$model_revision" "$model_bytes" > "$target.source"
  echo "Master model verified: $target"
)

if (( download_only )); then
  download_master_model
  exit 0
fi

resolve_install_root() {
  lmstudio_root="$HOME/.lmstudio"
  if [[ -f "$HOME/.lmstudio-home-pointer" ]]; then
    lmstudio_root=$(cat "$HOME/.lmstudio-home-pointer")
  fi
  if [[ -z "$lmstudio_root" || "$lmstudio_root" != /* ]]; then
    echo "LM Studio's home directory must be an absolute path." >&2
    exit 1
  fi
}

resolve_install_root
if [[ -e "$lms_command" || -L "$lms_command" ]]; then
  if [[ ! -L "$lms_command" || $(readlink "$lms_command") != "$lmstudio_root/bin/lms" ]]; then
    echo "Refusing to overwrite an unrelated command: $lms_command" >&2
    exit 1
  fi
fi

if [[ ! -x "$lmstudio_root/bin/lms" ]] || (( update )); then
  for dependency in curl bash tar awk ldconfig; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
      echo "Required command is missing: $dependency" >&2
      exit 1
    fi
  done
  mkdir -p "$install_cache"
  echo "Installing headless LM Studio for $(uname -sm)."
  echo "Installer log: $install_log"
  curl --fail --silent --show-error --location --retry 3 \
    --connect-timeout 15 --max-time 120 \
    https://lmstudio.ai/install.sh -o "$install_script.part"
  mv -- "$install_script.part" "$install_script"
  if ! bash "$install_script" --no-modify-path >"$install_log" 2>&1; then
    tail -n 30 "$install_log" >&2
    echo "LM Studio installation failed; see $install_log" >&2
    exit 1
  fi
  resolve_install_root
fi

if [[ ! -x "$lmstudio_root/bin/lms" ]]; then
  echo "LM Studio's lms executable was not installed at $lmstudio_root/bin/lms" >&2
  exit 1
fi
mkdir -p "$command_dir"
if [[ ! -e "$lms_command" && ! -L "$lms_command" ]]; then
  ln -s "$lmstudio_root/bin/lms" "$lms_command"
fi
"$lms_command" --version
printf 'LM Studio is ready: %s\n' "$lms_command"
case ":$PATH:" in
  *":$command_dir:"*) ;;
  *) echo 'To use lms by name: export PATH="$HOME/.local/bin:$PATH"' ;;
esac
echo "Start the daemon and API server inside your allocated cluster job."
echo "Master model directory: $models_dir"
if (( download_model )); then
  download_master_model
fi
