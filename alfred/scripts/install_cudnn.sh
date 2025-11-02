#!/bin/bash

# ======= Installs cudnn ==========
# Instructions: https://docs.nvidia.com/deeplearning/cudnn/installation/latest/linux.html#ubuntu-and-debian-network-installation
# Support matrix: https://docs.nvidia.com/deeplearning/cudnn/backend/v9.13.0/reference/support-matrix.html

SOURCE_DIR=$(dirname -- ${BASH_SOURCE[0]})
PREFIX=$1
CUDA_VERSION=$2
PACKAGES=$3

echo "===================== CUDNN Setup ========================"

# 1. Install cuda
bash $SOURCE_DIR/install_cuda.sh $PREFIX $CUDA_VERSION

# 2. Install cudnn
echo "Installing CUDNN..."

sudo apt-mark unhold cudnn9-cuda-13 libcudnn7

if [ "$CUDA_VERSION" = "13.0" ]; then
  wget https://developer.download.nvidia.com/compute/cudnn/9.13.0/local_installers/cudnn-local-repo-ubuntu2404-9.13.0_1.0-1_amd64.deb -P $PREFIX
  sudo dpkg -i $PREFIX/cudnn-local-repo-ubuntu2404-9.13.0_1.0-1_amd64.deb
  sudo cp /var/cudnn-local-repo-ubuntu2404-9.13.0/cudnn-*-keyring.gpg /usr/share/keyrings/
  sudo apt-get update
  sudo apt-get -y install zlib1g cudnn9-cuda-13
  sudo apt-mark hold cudnn9-cuda-13

  # Add symbolic link
  ln -s /usr/lib/x86_64-linux-gnu/libcudnn.so.9 /usr/lib/cuda-$CUDA_VERSION/lib64/libcudnn.so.9
elif [ "$CUDA_VERSION" = "10.2" ]; then
  # NVARCH=x86_64
  # curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/${NVARCH}/3bf863cc.pub | sudo apt-key add -
  # echo "deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/${NVARCH} /" | sudo tee /etc/apt/sources.list.d/cuda10.2.list > /dev/null
  # sudo apt-get update
  # sudo apt-get install -y libcudnn8=$CUDNN8_VERSION libcudnn8-dev=$CUDNN8_VERSION
  CUDNN7_VERSION=7.6.5.32-1+cuda10.2

  # https://gist.github.com/tzvsi/222b3b22a847004a729744f89fe31255
  sudo dpkg -i $PACKAGES/libcudnn7_${CUDNN7_VERSION}_amd64.deb
  sudo dpkg -i $PACKAGES/libcudnn7-dev_${CUDNN7_VERSION}_amd64.deb
  sudo dpkg -i $PACKAGES/libcudnn7-doc_${CUDNN7_VERSION}_amd64.deb

  sudo apt-mark hold libcudnn7

  # Add symbolic link
  sudo ln -s /usr/lib/x86_64-linux-gnu/libcudnn.so.7 /usr/local/cuda-$CUDA_VERSION/lib64/libcudnn.so.7
fi

# 3. Install nccl and cublas
echo "Installing NCCL and CUBLAS..."
bash $SOURCE_DIR/install_nccl_cublas.sh $PREFIX $CUDA_VERSION

echo "Verifying installation..."
LIBCUDNN_SAMPLES_PACKAGE=''
LIBCUDNN_VERSION_SUFFIX=''

# --- Verify ---
if [ "$CUDA_VERSION" = "13.0" ]; then
  LIBCUDNN_SAMPLES_PACKAGE=libcudnn9-samples
  LIBCUDNN_VERSION_SUFFIX=v9
  sudo apt-get install -y $LIBCUDNN_SAMPLES_PACKAGE libfreeimage3 libfreeimage-dev
elif [ "$CUDA_VERSION" = "10.2" ]; then
  LIBCUDNN_SAMPLES_PACKAGE=libcudnn7-doc
  LIBCUDNN_VERSION_SUFFIX=v7
fi

cp -r /usr/src/cudnn_samples_$LIBCUDNN_VERSION_SUFFIX $HOME
cd $HOME/cudnn_samples_$LIBCUDNN_VERSION_SUFFIX/mnistCUDNN
make clean && make
LD_LIBRARY_PATH=/usr/local/cuda-$CUDA_VERSION/lib64:$LD_LIBRARY_PATH PATH=/usr/local/cuda-$CUDA_VERSION/bin:$PATH ./mnistCUDNN
rm -rf $HOME/cudnn_samples_$LIBCUDNN_VERSION_SUFFIX
sudo apt-get remove -y $LIBCUDNN_SAMPLES_PACKAGE

echo "===================== CUDNN Setup Finished ====================="
