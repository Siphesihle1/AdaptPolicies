#!/bin/bash

PREFIX=$1
CUDA_VERSION=$2

echo "Verifying installation..."
LIBCUDNN_SAMPLES_PACKAGE=''
LIBCUDNN_VERSION_SUFFIX=''

# --- Verify ---
if [ "$CUDA_VERSION" = "13.0" ]; then
  LIBCUDNN_SAMPLES_PACKAGE=libcudnn9-samples
  LIBCUDNN_VERSION_SUFFIX=v9
  sudo apt-get install -y $LIBCUDNN_SAMPLES_PACKAGE
elif [ "$CUDA_VERSION" = "10.2" ]; then
  LIBCUDNN_SAMPLES_PACKAGE=libcudnn7-doc
  LIBCUDNN_VERSION_SUFFIX=v7
elif [ "$CUDA_VERSION" = "11.8" ]; then
  LIBCUDNN_SAMPLES_PACKAGE=libcudnn8-samples
  LIBCUDNN_VERSION_SUFFIX=v8
  sudo apt-get install -y $LIBCUDNN_SAMPLES_PACKAGE
fi

cp -r /usr/src/cudnn_samples_$LIBCUDNN_VERSION_SUFFIX $PREFIX
cd $PREFIX/cudnn_samples_$LIBCUDNN_VERSION_SUFFIX/mnistCUDNN
make clean && make
./mnistCUDNN
rm -rf $PREFIX/cudnn_samples_$LIBCUDNN_VERSION_SUFFIX
sudo apt-get remove -y $LIBCUDNN_SAMPLES_PACKAGE