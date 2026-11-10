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
SIM_PLAYER=("${SIM_EXECUTABLES[0]}" -force-glcore "$@" -batchmode
  "-http-port=${SIM_PORT:?Set SIM_PORT}" -logFile "$SIM_LOG_DIR/Player.log")

# Cluster nodes have no xvfb-run. VIRTUALHOME_DISPLAY_PREFIX names a conda prefix
# built from environment-display.yml (Xvfb plus Mesa DRI drivers for its GLX).
# Unset (e.g. local machines): the system xvfb-run path below is unchanged.
if [ -n "${VIRTUALHOME_DISPLAY_PREFIX:-}" ]; then
  if [ "${SIM_FOREGROUND:-0}" != 1 ]; then
    SIM_FOREGROUND=1 nohup bash "$0" "$@" > "$SIM_LOG_DIR/simulator-stdout.log" 2>&1 &
    exit 0
  fi
  XVFB="$VIRTUALHOME_DISPLAY_PREFIX/bin/Xvfb"
  if [ ! -x "$XVFB" ] || [ ! -d "$VIRTUALHOME_DISPLAY_PREFIX/lib/dri" ]; then
    echo "Expected Xvfb and Mesa DRI drivers in $VIRTUALHOME_DISPLAY_PREFIX" >&2
    exit 1
  fi
  DISPLAY_FILE="$SIM_LOG_DIR/xvfb-display.txt"
  : > "$DISPLAY_FILE"
  # -displayfd: Xvfb picks a free display and writes its number once it is ready.
  LIBGL_DRIVERS_PATH="$VIRTUALHOME_DISPLAY_PREFIX/lib/dri" "$XVFB" -displayfd 9 \
    -screen 0 640x480x24 -nolisten tcp +extension GLX \
    9>"$DISPLAY_FILE" > "$SIM_LOG_DIR/Xvfb.log" 2>&1 &
  XVFB_PID=$!
  trap 'kill "$XVFB_PID" 2>/dev/null || true' EXIT
  for attempt in $(seq 1 150); do
    if [ -s "$DISPLAY_FILE" ]; then break; fi
    if ! kill -0 "$XVFB_PID" 2>/dev/null; then
      echo "Xvfb exited before reporting a display; see $SIM_LOG_DIR/Xvfb.log" >&2
      exit 1
    fi
    sleep 0.2
  done
  if [ ! -s "$DISPLAY_FILE" ]; then
    echo "Xvfb did not report a display; see $SIM_LOG_DIR/Xvfb.log" >&2
    exit 1
  fi
  # Unity renders with the node's system Mesa (llvmpipe, OpenGL 4.5 core) via
  # glvnd's mesa vendor, never the NVIDIA GLX vendor, which has no X server here.
  DISPLAY=":$(tr -d '[:space:]' < "$DISPLAY_FILE")" __GLX_VENDOR_LIBRARY_NAME=mesa \
    "${SIM_PLAYER[@]}"
  exit $?
fi

SIM_COMMAND=(xvfb-run -a --server-args="-screen 0 640x480x24" "${SIM_PLAYER[@]}")
if [ "${SIM_FOREGROUND:-0}" = 1 ]; then
  exec "${SIM_COMMAND[@]}"
fi
nohup "${SIM_COMMAND[@]}" > "$SIM_LOG_DIR/simulator-stdout.log" 2>&1 &

