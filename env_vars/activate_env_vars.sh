#!/bin/bash

export PROJECT_ROOT=~/AdaptPolicies
export PATH=$CONDA_PREFIX/bin:$PATH
export ALFRED_ROOT=$PROJECT_ROOT/alfred
export VIRTUALHOME_DIR=$PROJECT_ROOT/src/virtual_home/virtualhome
export VIRTUALHOME_ROOT=$VIRTUALHOME_DIR/src/virtualhome
export PYTHONPATH=${PROJECT_ROOT}/src:${ALFRED_ROOT}:${ALFRED_ROOT}/gen:${ALFRED_ROOT}/models:${VIRTUALHOME_ROOT}:${VIRTUALHOME_ROOT}/simulation
export ALFRED_DATA=$PROJECT_ROOT/alfred/data
export LIBGL_ALWAYS_INDIRECT=0
export AI2THOR_PREFIX=/tmp
export OLLAMA_HOST=http://localhost:11434
export VIRTUALHOME_SIM_VERSION=v2.0/v2.3.0
export SIM_PORT=8082
