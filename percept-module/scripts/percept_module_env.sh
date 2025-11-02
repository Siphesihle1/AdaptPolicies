#!/bin/bash

ALFRED_DIR=$(pwd)/../alfred
PREFIX=$(pwd)/../build
PYTHON_ENV_NAME=alfred_env

export ALFRED_ROOT=$ALFRED_DIR
export ALFRED_DATA=$ALFRED_ROOT/data
export MODEL_DIR=$(pwd)/model_dir
export DISPLAY=:0

# for wsl
export LIBGL_ALWAYS_INDIRECT=0

. $PREFIX/$PYTHON_ENV_NAME/bin/activate