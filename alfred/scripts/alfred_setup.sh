#!/bin/bash

# ========== Sets up environment for AI2THOR initialized with the Alfred datatse ===============

SOURCE_DIR=$(dirname -- ${BASH_SOURCE[0]})
ALFRED_DIR=$1
PREFIX=$2
PYTHON_ENV_NAME=$3
CUDA_VERSION=$4
PACKAGES=$5

echo "===================== ALFRED setup ====================="

# 1. Install CUDNN
bash $SOURCE_DIR/install_cudnn.sh $PREFIX $CUDA_VERSION $PACKAGES

# 2. Install alfred dependecies
echo "Installing alfred dependencies..."
bash $SOURCE_DIR/install_deps.sh

# 3. Install pyenv
echo "Installing pyenv..."
bash $SOURCE_DIR/install_pyenv.sh $PREFIX

# 4. Setup python environment for alfred
echo "Setting up python environment..."
VIRTUALENV=$PREFIX/$PYTHON_ENV_NAME
pyenv install -s 3.8 && pyenv global 3.8
pip install virtualenv
python -m virtualenv $VIRTUALENV
. $VIRTUALENV/bin/activate

# 5. Install python packages for alfred
echo "Installing python package dependencies for alfred..."
cd $ALFRED_DIR
pip install --upgrade pip
pip install -U setuptools
pip install -r requirements.txt

# 6. Install mesa utils
echo "Installing mesa utils..."
sudo apt-get install -y mesa-utils

deactivate

echo "===================== ALFRED setup finished ====================="