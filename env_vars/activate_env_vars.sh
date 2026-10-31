#!/bin/bash

if [ -z "${PROJECT_ROOT:-}" ]; then
  # Resolve a local checkout; copied cluster activation hooks retain the old default.
  _adapt_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
  if [ -d "$_adapt_root/src/methods" ]; then
    PROJECT_ROOT=$_adapt_root
  else
    PROJECT_ROOT=$HOME/AdaptPolicies
  fi
  unset _adapt_root
fi
export PROJECT_ROOT
export PATH=$CONDA_PREFIX/bin:$PATH
export VIRTUALHOME_PREFIX=$PROJECT_ROOT/src/virtual_home
export VIRTUALHOME_DIR=$VIRTUALHOME_PREFIX/virtualhome
export VIRTUALHOME_ROOT=$VIRTUALHOME_DIR/src/virtualhome
export PYTHONPATH=${PROJECT_ROOT}/src:${VIRTUALHOME_PREFIX}:${VIRTUALHOME_DIR}/src:${VIRTUALHOME_ROOT}:${VIRTUALHOME_ROOT}/simulation
export LIBGL_ALWAYS_INDIRECT=0
export OLLAMA_HOST=http://localhost:11430
export VIRTUALHOME_SIM_VERSION=v2.0/v2.3.0
export VIRTUALHOME_SIM_URL='https://web.archive.org/web/20241229111508id_/http://virtual-home.org//release/simulator/v2.0/v2.3.0/linux_exec.zip'
export SIM_PORT=8082
