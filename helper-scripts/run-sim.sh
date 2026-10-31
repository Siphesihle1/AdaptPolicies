#!/bin/bash

SIM_VERSION_NUMBER=${VIRTUALHOME_SIM_VERSION##*/v}
SIM_ROOT=${VIRTUALHOME_SIM_ROOT:-${VIRTUALHOME_ROOT}/simulation}

nohup xvfb-run -a \
  --server-args="-screen 0 640x480x24" \
  "$SIM_ROOT"/linux_exec.*${SIM_VERSION_NUMBER}.x86_64 \
  -force-glcore "$@" -batchmode -http-port=$SIM_PORT -logFile Player.log > $HOME/vh_sim.log 2>&1 &

