#!/bin/bash

# ========== Sets up environment for the percept module ==========

ALFRED_DIR=$1
PERCEPT_MODULE_DIR=$2
PREFIX=$3
PYTHON_ENV_NAME=$4
CUDA_VERSION=$5
PACKAGES=$6

echo "===================== Percept module setup ====================="

# 1. Setup alfred
bash $ALFRED_DIR/scripts/alfred_setup.sh $ALFRED_DIR $PREFIX $PYTHON_ENV_NAME $CUDA_VERSION $PACKAGES

cd $PERCEPT_MODULE_DIR

# 2. Setup ViLD (https://github.com/tensorflow/tpu/tree/master/models/official/detection/projects/vild)
echo "Setting up ViLD"
bash scripts/vild_setup.sh $PREFIX

# 3. Install python dependencies
echo "Installing python dependencies"
. $PREFIX/$PYTHON_ENV_NAME/bin/activate
pip install -r requirements.txt

# 4. Test tensorflow GPU integration (https://www.tensorflow.org/install/pip)
echo "Testing if tensorflow can detect the GPU/s..."
python -c "from tensorflow._api.v1.config import experimental; print(experimental.list_physical_devices('GPU'))"

# xhost +local:$(whoami)

# https://unix.stackexchange.com/questions/478742/error-when-trying-to-use-xorg-only-console-users-are-allowed-to-run-the-x-serve
# sudo sed -i 's/allowed_users=.*/allowed_users=anybody' /etc/X11/Xwrapper.config

# python startx.py 0

# deactivate

echo "===================== Percept module setup finished ====================="