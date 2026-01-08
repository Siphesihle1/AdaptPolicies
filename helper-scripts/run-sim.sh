#!/bin/bash

SIM_VERSION_NUMBER=${VIRTUALHOME_SIM_VERSION##*/v}

nohup xvfb-run -a \
  --server-args="-screen 0 640x480x24" \
  ${VIRTUALHOME_ROOT}/simulation/linux_exec.*${SIM_VERSION_NUMBER}.x86_64 \
  -batchmode -http-port=$SIM_PORT -logFile Player.log > $HOME/vh_sim.log 2>&1 &

PID=$!

echo $PID

