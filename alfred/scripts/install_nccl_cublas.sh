#!/bin.bash

PREFIX=$1
CUDA_VERSION=$2

# === Installs libnccl and libcublas ===
sudo apt-mark unhold libnccl2 libnccl-dev libcublas-dev libcublas13-0 libcublas10

sudo apt-get install -y build-essential dkms

if [ "$CUDA_VERSION" = "13.0" ]; then
  wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-keyring_1.0-1_all.deb -O $PREFIX/cuda-keyring_1.0-1_all.deb
  sudo dpkg -i $PREFIX/cuda-keyring_1.0-1_all.deb
  sudo apt-get update
  sudo apt-get install -y libnccl2 libnccl-dev libcublas13-0
  sudo apt-mark hold libcublas13-0
elif [ "$CUDA_VERSION" = "10.2" ]; then
  LIBNCCL_VERSION=2.15.5-1
  LIBCUBLAS_VERSION=10.2.2.89-1
  sudo apt-get install -y --allow-downgrades \
    libnccl-dev=$LIBNCCL_VERSION+cuda$CUDA_VERSION \
    libcublas-dev=$LIBCUBLAS_VERSION \
    libnccl2=$LIBNCCL_VERSION+cuda$CUDA_VERSION \
    libcublas10=$LIBCUBLAS_VERSION
  sudo apt-mark hold libcublas10
fi

sudo ldconfig -p | grep libnccl

# Keep apt from auto upgrading the cublas and nccl packages. See https://gitlab.com/nvidia/container-images/cuda/-/issues/88
sudo apt-mark hold libnccl2 libnccl-dev libcublas-dev
