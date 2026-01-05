#!/bin/bash

export PROJECT_ROOT=~/AdaptPolicies
export PATH=$CONDA_PREFIX/bin:$PATH
export ALFRED_ROOT=$PROJECT_ROOT/alfred
export PYTHONPATH=$PROJECT_ROOT/src:$ALFRED_ROOT:${ALFRED_ROOT}/gen:${ALFRED_ROOT}/models
export ALFRED_DATA=$PROJECT_ROOT/alfred/data
export LIBGL_ALWAYS_INDIRECT=0
export AI2THOR_PREFIX=/tmp
export OLLAMA_HOST=http://localhost:11434
