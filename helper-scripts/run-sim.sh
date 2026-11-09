#!/bin/bash

set -euo pipefail

SIM_VERSION_NUMBER=${VIRTUALHOME_SIM_VERSION:?Set VIRTUALHOME_SIM_VERSION}
SIM_VERSION_NUMBER=${SIM_VERSION_NUMBER##*/v}
SIM_ROOT=${VIRTUALHOME_SIM_ROOT:-${VIRTUALHOME_ROOT:?Set VIRTUALHOME_SIM_ROOT}/simulation}
SIM_EXECUTABLES=("$SIM_ROOT"/linux_exec.*"$SIM_VERSION_NUMBER".x86_64)
if [ "${#SIM_EXECUTABLES[@]}" -ne 1 ] || [ ! -x "${SIM_EXECUTABLES[0]}" ]; then
  echo "Expected one executable simulator in $SIM_ROOT" >&2
  exit 1
fi
SIM_LOG_DIR=${JOB_OUTPUT_DIR:-$PWD}
mkdir -p "$SIM_LOG_DIR"
SIM_COMMAND=(xvfb-run -a --server-args="-screen 0 640x480x24"
  "${SIM_EXECUTABLES[0]}" -force-glcore "$@" -batchmode
  "-http-port=${SIM_PORT:?Set SIM_PORT}" -logFile "$SIM_LOG_DIR/Player.log")
if [ "${SIM_FOREGROUND:-0}" = 1 ]; then
  exec "${SIM_COMMAND[@]}"
fi
nohup "${SIM_COMMAND[@]}" > "$SIM_LOG_DIR/simulator-stdout.log" 2>&1 &

