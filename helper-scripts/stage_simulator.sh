#!/usr/bin/env bash
# Source inside a Slurm job to run the VirtualHome player from node-local disk:
#   source helper-scripts/stage_simulator.sh
#   # helper-scripts/run-sim.sh now uses the staged $VIRTUALHOME_SIM_ROOT, then:
#   remove_staged_simulator
# The caller must call remove_staged_simulator from its EXIT trap (including errors).
#
# The persistent build stays in home storage (VIRTUALHOME_SIM_SOURCE, default
# ~/virtualhome/adaptpolicies-simulator-v2) next to its checksum manifest
# (<build>.sha256, one "sha256  <build>/<file>" line per file). Each job copies it
# to node-local /var/tmp, verifies every file, and deletes the copy on exit.
# VIRTUALHOME_SIM_ROOT selects the staged location; it must lie inside this user's
# private /var/tmp/<user> directory (default /var/tmp/<user>/virtualhome/<build>).
# Nodes are allocated whole (select/linear), and a per-node lock additionally
# stops two of this user's jobs from staging into the same directory.

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  echo 'Source this helper inside a Slurm job; see the usage comments.' >&2
  exit 2
fi

remove_staged_simulator() {
  # Only remove a copy staged by this invocation, and only inside the private root.
  local status=0
  if [[ ${VIRTUALHOME_SIM_STAGED:-0} == 1 ]]; then
    if [[ $VIRTUALHOME_SIM_ROOT == "$ADAPT_NODE_TMP"/* ]]; then
      rm -rf -- "$VIRTUALHOME_SIM_ROOT" || status=1
    fi
    VIRTUALHOME_SIM_STAGED=0
  fi
  if [[ -n ${VIRTUALHOME_SIM_LOCK_FD:-} ]]; then
    flock -u "$VIRTUALHOME_SIM_LOCK_FD" || status=1
    exec {VIRTUALHOME_SIM_LOCK_FD}>&-
    unset VIRTUALHOME_SIM_LOCK_FD
  fi
  return "$status"
}

ensure_private_node_tmp() {
  # Shared /var/tmp: create or accept only a non-symlink directory owned by this user.
  export ADAPT_NODE_TMP="/var/tmp/$(id -un)"
  if [[ ! -e $ADAPT_NODE_TMP && ! -L $ADAPT_NODE_TMP ]]; then
    mkdir -m 700 -- "$ADAPT_NODE_TMP" || return
  fi
  if [[ -L $ADAPT_NODE_TMP || ! -d $ADAPT_NODE_TMP || ! -O $ADAPT_NODE_TMP ]]; then
    echo "Refusing node-local directory that is a symlink or not owned by this user: $ADAPT_NODE_TMP" >&2
    return 1
  fi
  chmod 700 "$ADAPT_NODE_TMP"
}

stage_simulator() {
  local dependency
  for dependency in scontrol hostname realpath tar sha256sum sed flock df du awk; do
    command -v "$dependency" >/dev/null || { echo "Missing command: $dependency" >&2; return 1; }
  done
  if [[ -z ${SLURM_JOB_ID:-} || -z ${SLURM_JOB_NODELIST:-} ]] ||
      ! scontrol show hostnames "$SLURM_JOB_NODELIST" | grep -qxF "$(hostname -s)"; then
    echo 'Stage the simulator on a compute node allocated by Slurm, not the login node.' >&2
    return 1
  fi
  if [[ -n ${VIRTUALHOME_SIM_LOCK_FD:-} ]]; then
    echo 'Remove the previously staged simulator first.' >&2
    return 1
  fi
  local source_dir build manifest target required available
  source_dir=$(realpath -e -- "${VIRTUALHOME_SIM_SOURCE:-$HOME/virtualhome/adaptpolicies-simulator-v2}") || return
  build=$(basename -- "$source_dir")
  manifest="$source_dir.sha256"
  [[ -d $source_dir && -f $manifest ]] || {
    echo "Expected the simulator build and its manifest: $source_dir, $manifest" >&2; return 1;
  }
  ensure_private_node_tmp || return
  target="${VIRTUALHOME_SIM_ROOT:-$ADAPT_NODE_TMP/virtualhome/$build}"
  # Lexical checks: the cleanup deletes this path, so keep it strictly inside the root.
  if [[ $target != "$ADAPT_NODE_TMP"/* || /$target/ == */../* || /$target/ == */./* ]]; then
    echo "VIRTUALHOME_SIM_ROOT must be a normalized path inside $ADAPT_NODE_TMP: $target" >&2
    return 1
  fi
  exec {VIRTUALHOME_SIM_LOCK_FD}>"$ADAPT_NODE_TMP/virtualhome.lock" || return
  flock -n "$VIRTUALHOME_SIM_LOCK_FD" || {
    echo 'Another job of this user is staging or running a simulator on this node.' >&2; return 1;
  }
  export VIRTUALHOME_SIM_ROOT="$target"
  # A copy left by a killed job (e.g. SIGKILL at the time limit) is stale: replace it.
  VIRTUALHOME_SIM_STAGED=1
  rm -rf -- "$VIRTUALHOME_SIM_ROOT" || return
  mkdir -p -- "$VIRTUALHOME_SIM_ROOT" || return
  required=$(( $(du -sB1 -- "$source_dir" | awk '{print $1}') + 1073741824 ))
  available=$(df -PB1 -- "$VIRTUALHOME_SIM_ROOT" | awk 'NR==2 {print $4}') || return
  (( available >= required )) || { echo 'Insufficient node-local space for the simulator plus 1 GiB.' >&2; return 1; }
  echo "Staging simulator on $(hostname -s): $VIRTUALHOME_SIM_ROOT"
  # tar keeps file modes (executables) without copying home-directory NFS ACLs.
  tar -C "$source_dir" -cf - . | tar -C "$VIRTUALHOME_SIM_ROOT" -xf - || return
  # Manifest paths are "<build>/<file>"; check every file relative to the copy.
  sed "s#  $build/#  #" "$manifest" | (cd "$VIRTUALHOME_SIM_ROOT" && sha256sum --quiet --check -) || {
    echo 'Staged simulator checksum mismatch.' >&2; return 1;
  }
  echo "Simulator staged and verified ($(wc -l < "$manifest") files)."
}

if stage_simulator; then
  return 0
else
  _stage_simulator_status=$?
  remove_staged_simulator || true
  return "$_stage_simulator_status"
fi
