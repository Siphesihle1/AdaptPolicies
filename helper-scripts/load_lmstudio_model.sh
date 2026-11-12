#!/usr/bin/env bash
# Source inside a Slurm job so the caller retains the endpoint and cleanup hook:
#   source helper-scripts/load_lmstudio_model.sh /datasets/<user>/models/model.gguf
#   # Use $LMSTUDIO_BASE_URL and $LMSTUDIO_MODEL_ID, then:
#   stop_lmstudio_model
# The caller must call stop_lmstudio_model from its EXIT trap (including errors).
# Single-file GGUF models only. The persistent source is never moved or changed.
# Jobs on different nodes share the installed binaries, but keep daemon state in
# their own node-local /var/tmp job directory. One instance per user per node.
# Optional settings: LMSTUDIO_PORT (1234), LMSTUDIO_MODEL_ID, LMSTUDIO_RUNTIME
# (default llama.cpp:cuda on NVIDIA nodes, else llama.cpp; or a pinned runtime
# query such as llama.cpp:cuda@2.73.0), LMSTUDIO_LOAD_TIMEOUT (3600 seconds),
# LMSTUDIO_CONTEXT_LENGTH (unset: LM Studio's default context length).

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  echo 'Source this helper inside a Slurm job; see the usage comments.' >&2
  exit 2
fi

stop_lmstudio_model() {
  # Only stop a daemon started by this invocation, never another user's service.
  local status=0
  if [[ ${LMSTUDIO_DAEMON_OWNED:-0} == 1 ]]; then
    if timeout 60 "$LMSTUDIO_LMS_BIN" daemon down; then
      LMSTUDIO_DAEMON_OWNED=0
    else
      echo 'Failed to stop the LM Studio daemon.' >&2
      status=1
    fi
  fi
  # Delete this job's node-local model copy and daemon state once nothing uses them.
  if [[ ${LMSTUDIO_DAEMON_OWNED:-0} == 0 && -n ${LMSTUDIO_JOB_DIR:-} ]]; then
    rm -rf -- "$LMSTUDIO_JOB_DIR" || status=1
    unset LMSTUDIO_JOB_DIR
  fi
  if [[ -n ${LMSTUDIO_LOCK_FD:-} ]]; then
    flock -u "$LMSTUDIO_LOCK_FD" || status=1
    exec {LMSTUDIO_LOCK_FD}>&-
    unset LMSTUDIO_LOCK_FD
  fi
  return "$status"
}

load_lmstudio_model() {
  if (( $# != 1 )); then
    echo 'Usage: source load_lmstudio_model.sh /absolute/path/to/model.gguf' >&2
    return 2
  fi
  local dependency
  for dependency in scontrol hostname realpath cp sha256sum stat df awk flock curl python3 timeout; do
    command -v "$dependency" >/dev/null || { echo "Missing command: $dependency" >&2; return 1; }
  done
  if [[ -z ${SLURM_JOB_ID:-} || -z ${SLURM_JOB_NODELIST:-} ]] ||
      ! scontrol show hostnames "$SLURM_JOB_NODELIST" | grep -qxF "$(hostname -s)"; then
    echo 'Run this helper on a compute node allocated by Slurm, not the login node.' >&2
    return 1
  fi
  if [[ -n ${LMSTUDIO_LOCK_FD:-} ]]; then
    echo 'Stop the model from the previous helper invocation first.' >&2
    return 1
  fi
  local source_model filename scratch_root scratch_dir available required expected actual namespace
  source_model=$(realpath -e -- "$1") || return
  [[ -f $source_model && $source_model == *.gguf ]] || {
    echo 'The model must be an existing single GGUF file.' >&2; return 1;
  }
  filename=$(basename -- "$source_model")
  if [[ $filename =~ -[0-9]{5}-of-[0-9]{5}\.gguf$ ]]; then
    echo 'Split GGUF models are not supported by this helper.' >&2
    return 1
  fi
  # Current cluster nodes have no /scratch; /tmp is RAM-backed. /var/tmp is
  # writable node-local disk. Use a private numeric-UID directory, including
  # an ownership check before using an existing directory in this shared area.
  scratch_root="/var/tmp/lmstudio-$(id -u)"
  if [[ ! -e $scratch_root && ! -L $scratch_root ]]; then
    mkdir -m 700 -- "$scratch_root" || return
  fi
  if [[ -L $scratch_root || ! -d $scratch_root || ! -O $scratch_root ]]; then
    echo "Refusing staging directory that is a symlink or not owned by this user: $scratch_root" >&2
    return 1
  fi
  chmod 700 "$scratch_root" || return
  scratch_dir="$scratch_root/job-$SLURM_JOB_ID"
  export LMSTUDIO_JOB_DIR="$scratch_dir"   # removed by stop_lmstudio_model
  echo "Node-local staging directory: $scratch_dir"
  mkdir -p "$scratch_dir/models" || {
    echo "Cannot create model staging directory: $scratch_dir/models" >&2; return 1;
  }
  chmod 700 "$scratch_dir" || return
  required=$(( $(stat -c %s "$source_model") + 1073741824 ))
  available=$(df -PB1 "$scratch_dir" | awk 'NR==2 {print $4}') || return
  (( available >= required )) || { echo 'Insufficient node-local space for the model plus 1 GiB.' >&2; return 1; }
  export LMSTUDIO_STAGED_MODEL="$scratch_dir/models/$filename"
  echo "Staging model on $(hostname -s): $LMSTUDIO_STAGED_MODEL"
  # Prefer the download script's verified checksum sidecar; hash the source if absent.
  if [[ -f $source_model.sha256 ]]; then
    expected=$(awk 'NR==1 {print $1}' "$source_model.sha256") || return
  else
    expected=$(sha256sum "$source_model" | awk '{print $1}') || return
  fi
  [[ $expected =~ ^[a-fA-F0-9]{64}$ ]] || { echo 'Invalid SHA-256 checksum.' >&2; return 1; }
  cp --reflink=auto -- "$source_model" "$LMSTUDIO_STAGED_MODEL.part" || return
  actual=$(sha256sum "$LMSTUDIO_STAGED_MODEL.part" | awk '{print $1}') || return
  [[ ${actual,,} == ${expected,,} ]] || { echo 'Staged model checksum mismatch.' >&2; return 1; }
  mv -- "$LMSTUDIO_STAGED_MODEL.part" "$LMSTUDIO_STAGED_MODEL" || return

  local studio_root="$HOME/.lmstudio"
  if [[ -f $HOME/.lmstudio-home-pointer ]]; then
    studio_root=$(cat "$HOME/.lmstudio-home-pointer") || return
  fi
  [[ $studio_root == /* ]] || { echo 'LM Studio home must be absolute.' >&2; return 1; }
  export LMSTUDIO_SHARED_LMS_BIN="$studio_root/bin/lms"
  [[ -x $LMSTUDIO_SHARED_LMS_BIN ]] || { echo 'Run lmstudio_setup.sh to install LM Studio first.' >&2; return 1; }
  # The staging root is node-local: this lock prevents instances on THIS node
  # without blocking jobs on other nodes. Keep the fixed localhost port simple.
  exec {LMSTUDIO_LOCK_FD}>"$scratch_root/node.lock" || return
  flock -n "$LMSTUDIO_LOCK_FD" || {
    echo 'Another helper-managed LM Studio job is already running on this node.' >&2; return 1;
  }
  LMSTUDIO_DAEMON_OWNED=0
  export LMSTUDIO_PROCESS_HOME="$scratch_dir/home"
  mkdir -p "$LMSTUDIO_PROCESS_HOME/.lmstudio/.internal" || return
  # Reuse only the installation descriptor (binary path/cwd), never shared daemon
  # discovery files, credentials, model registrations, or runtime configuration.
  cp -- "$studio_root/.internal/llmster-install-location.json" \
    "$LMSTUDIO_PROCESS_HOME/.lmstudio/.internal/llmster-install-location.json" || return
  export LMSTUDIO_LMS_BIN="$scratch_dir/lms"
  # HOME is scoped to the child process; the calling job retains its real $HOME
  # for repository paths, outputs and logs. The daemon inherits this private home.
  cat > "$LMSTUDIO_LMS_BIN" <<'SH' || return
#!/usr/bin/env bash
exec env -u LMS_API_SERVER_INFO_PATH -u LMSTUDIO_HOME -u LMS_LMSTUDIO_HOME \
  HOME="$LMSTUDIO_PROCESS_HOME" XDG_CACHE_HOME="$LMSTUDIO_PROCESS_HOME/.cache" \
  "$LMSTUDIO_SHARED_LMS_BIN" "$@"
SH
  chmod 700 "$LMSTUDIO_LMS_BIN" || return
  echo "Private LM Studio state: $LMSTUDIO_PROCESS_HOME/.lmstudio"
  timeout 60 "$LMSTUDIO_LMS_BIN" daemon status --json > "$scratch_dir/daemon-before.json" || return
  python3 - "$scratch_dir/daemon-before.json" <<'PY' || return
import json, sys
with open(sys.argv[1]) as f:
    state = json.load(f)
if state.get("status") != "not-running":
    raise SystemExit("An existing LM Studio service was detected; refusing to reuse or stop it.")
PY
  export LMSTUDIO_PORT="${LMSTUDIO_PORT:-1234}"
  [[ $LMSTUDIO_PORT =~ ^[0-9]{1,5}$ ]] && (( 10#$LMSTUDIO_PORT >= 1 && 10#$LMSTUDIO_PORT <= 65535 )) || {
    echo 'LMSTUDIO_PORT must be between 1 and 65535.' >&2; return 1;
  }
  # A busy API port should fail before a daemon is launched.
  python3 - "$LMSTUDIO_PORT" <<'PY' || return
import socket, sys
with socket.socket() as sock:
    sock.bind(("127.0.0.1", int(sys.argv[1])))
PY
  export LMSTUDIO_BASE_URL="http://127.0.0.1:$LMSTUDIO_PORT/v1"
  export LMSTUDIO_MODEL_ID="${LMSTUDIO_MODEL_ID:-slurm-$SLURM_JOB_ID}"
  namespace="slurm-$SLURM_JOB_ID/staged"
  # Set ownership before startup so an interrupted startup is also cleaned up.
  LMSTUDIO_DAEMON_OWNED=1
  # The daemon binary lives on shared home storage. When many jobs start together,
  # each also copying a model, that storage slows enough for "daemon up" to report
  # "no valid installation" (2026-11-12, 7 of 15 jobs). Retry before giving up.
  local daemon_attempt
  for daemon_attempt in 1 2 3; do
    timeout 120 "$LMSTUDIO_LMS_BIN" daemon up && break
    (( daemon_attempt < 3 )) || return 1
    echo "LM Studio daemon did not start (attempt $daemon_attempt of 3); retrying in 30 s." >&2
    timeout 60 "$LMSTUDIO_LMS_BIN" daemon down > /dev/null 2>&1 || true
    sleep 30
  done
  # A bare "llama.cpp" query resolves to the CPU (avx2) engine first, which ran a
  # 9B model at ~5 tok/s instead of ~53 tok/s on an RTX 3060. Request the CUDA
  # engine on GPU nodes. The fresh private home has no other engine installed, so
  # the downloaded one is the engine used; record it for provenance.
  local runtime_query="${LMSTUDIO_RUNTIME:-}"
  if [[ -z $runtime_query ]]; then
    runtime_query='llama.cpp'
    if nvidia-smi -L >/dev/null 2>&1; then runtime_query='llama.cpp:cuda'; fi
  fi
  timeout 600 "$LMSTUDIO_LMS_BIN" runtime get "$runtime_query" --yes || return
  # The daemon indexes a new engine shortly after installation ("No runtimes
  # found" until then). Wait for it, then make sure it is the selected engine.
  local engine_attempt installed=""
  export LMSTUDIO_ENGINE=""
  for (( engine_attempt=0; engine_attempt<30; engine_attempt++ )); do
    timeout 60 "$LMSTUDIO_LMS_BIN" runtime ls > "$scratch_dir/runtimes.txt" 2>&1 || return
    installed=$(awk '$1 ~ /^llama\.cpp-/ {print $1; exit}' "$scratch_dir/runtimes.txt")
    [[ -n $installed ]] && break
    sleep 2
  done
  [[ -n $installed ]] || { echo 'The installed engine was not indexed; see runtimes.txt.' >&2; return 1; }
  LMSTUDIO_ENGINE=$(awk '$2 == "✓" {print $1}' "$scratch_dir/runtimes.txt")
  if [[ $LMSTUDIO_ENGINE != "$installed" ]]; then
    timeout 60 "$LMSTUDIO_LMS_BIN" runtime select "$installed" || return
    timeout 60 "$LMSTUDIO_LMS_BIN" runtime ls > "$scratch_dir/runtimes.txt" 2>&1 || return
    LMSTUDIO_ENGINE=$(awk '$2 == "✓" {print $1}' "$scratch_dir/runtimes.txt")
  fi
  echo "LM Studio engine: ${LMSTUDIO_ENGINE:-unknown}"
  if [[ $runtime_query == *:cuda && $LMSTUDIO_ENGINE != *cuda* ]]; then
    echo 'A CUDA engine was requested but is not the selected engine; see runtimes.txt.' >&2
    return 1
  fi
  timeout 120 "$LMSTUDIO_LMS_BIN" import "$LMSTUDIO_STAGED_MODEL" \
    --symbolic-link --user-repo "$namespace" --yes || return
  # The CLI loads indexed model keys, which are not necessarily filesystem paths.
  # This private LM Studio home contains only the single LLM imported above.
  # Allow the daemon's model index a short time to notice the new import.
  local index_attempt model_key=""
  for (( index_attempt=0; index_attempt<15; index_attempt++ )); do
    timeout 30 "$LMSTUDIO_LMS_BIN" ls --llm --json > "$scratch_dir/disk-models.json" || return
    model_key=$(python3 - "$scratch_dir/disk-models.json" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    models = json.load(f)
if not isinstance(models, list):
    raise SystemExit("Unexpected model index format; see disk-models.json.")
if len(models) > 1:
    raise SystemExit("Expected exactly one LLM in the private model index; refusing to choose another model.")
if models:
    key = models[0].get("modelKey")
    if not isinstance(key, str) or not key.strip():
        raise SystemExit("Model index entry has no usable modelKey.")
    print(key)
PY
    ) || return
    [[ -n $model_key ]] && break
    sleep 2
  done
  [[ -n $model_key ]] || {
    echo "Imported model did not appear in the model index; see $scratch_dir/disk-models.json" >&2
    return 1
  }
  export LMSTUDIO_MODEL_KEY="$model_key"
  echo "Discovered model key: $LMSTUDIO_MODEL_KEY"
  # Omit --gpu and resource flags: use LM Studio defaults. Context length is the
  # only override, so experiments can match the context of a reference campaign.
  local load_args=("$LMSTUDIO_MODEL_KEY" --identifier "$LMSTUDIO_MODEL_ID" --yes)
  if [[ -n ${LMSTUDIO_CONTEXT_LENGTH:-} ]]; then
    [[ $LMSTUDIO_CONTEXT_LENGTH =~ ^[1-9][0-9]*$ ]] || {
      echo 'LMSTUDIO_CONTEXT_LENGTH must be a positive integer.' >&2; return 1;
    }
    load_args+=(--context-length "$LMSTUDIO_CONTEXT_LENGTH")
  fi
  timeout "${LMSTUDIO_LOAD_TIMEOUT:-3600}" "$LMSTUDIO_LMS_BIN" load "${load_args[@]}" || return
  timeout 120 "$LMSTUDIO_LMS_BIN" server start --bind 127.0.0.1 --port "$LMSTUDIO_PORT" || return
  local attempt ready=0
  for (( attempt=0; attempt<60; attempt++ )); do
    if curl --fail --silent --show-error --noproxy '*' --connect-timeout 2 --max-time 5 \
        "$LMSTUDIO_BASE_URL/models" > "$scratch_dir/models.json" 2>/dev/null; then
      if python3 - "$scratch_dir/models.json" "$LMSTUDIO_MODEL_ID" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    models = json.load(f).get("data", [])
sys.exit(0 if any(m.get("id") == sys.argv[2] for m in models) else 1)
PY
      then ready=1; break; fi
    fi
    sleep 2
  done
  (( ready )) || { echo 'The model API did not become ready.' >&2; return 1; }
  echo "Model loaded: $LMSTUDIO_MODEL_ID; API: $LMSTUDIO_BASE_URL"
}

if load_lmstudio_model "$@"; then
  return 0
else
  _lmstudio_load_status=$?
  stop_lmstudio_model || true
  return "$_lmstudio_load_status"
fi
