#!/bin/bash

# ======== Installs cuda =========

## Info on driver
# https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/index.html
# https://docs.nvidia.com/cuda/cuda-installation-guide-linux/#meta-packages

SOURCE_DIR=$(dirname -- ${BASH_SOURCE[0]})
PREFIX=$1
CUDA_VERSION=$2

echo "===================== CUDA setup ========================"

# ==== 1. cuda toolkit ====
echo "Installing cuda toolkit..."
bash $SOURCE_DIR/install_cuda_toolkit.sh $PREFIX $CUDA_VERSION

# ==== 2. OpenGL ====
# https://gist.github.com/Mluckydwyer/8df7782b1a6a040e5d01305222149f3c
# sudo apt-get install -y mesa-utils libglu1-mesa-dev freeglut3-dev mesa-common-dev
# if ! env | grep -q '^LIBGL_ALWAYS_INDIRECT=0'; then
# echo "export LIBGL_ALWAYS_INDIRECT=0" >> ${HOME}/.profile
# fi

# Environent setup
echo "Setting environment variables..."
grep -q "export PATH=.*/usr/local/cuda-$CUDA_VERSION/bin.*" ${HOME}/.profile
if [ $? -ne 0 ]; then
  echo "export PATH=/usr/local/cuda-$CUDA_VERSION/bin:\$PATH" >> ${HOME}/.profile
fi

LD_LIBRARY_PATH_LOCAL=''

if env | grep -q '^LD_LIBRARY_PATH='; then
  LD_LIBRARY_PATH_LOCAL="/usr/local/cuda-$CUDA_VERSION/lib64:\$LD_LIBRARY_PATH"
else
  LD_LIBRARY_PATH_LOCAL="/usr/local/cuda-$CUDA_VERSION/lib64"
fi

# For wsl
grep -q "export LD_LIBRARY_PATH=.*/usr/lib/wsl/lib.*" ${HOME}/.profile
if [ $? -ne 0 ]; then
  echo -e "export LD_LIBRARY_PATH=$LD_LIBRARY_PATH_LOCAL:/usr/lib/wsl/lib" >> ${HOME}/.profile
fi

# Create symbolic link to nvcc installed
# if [[ -d "/usr/local/cuda" || -L "/usr/local/cuda" ]]; then
#   sudo rm -rf /usr/local/cuda
# fi

if [ ! -e "/usr/local/cuda/bin/nvcc" ]; then
  sudo ln -s /usr/local/cuda-$CUDA_VERSION/bin/nvcc /usr/local/cuda/bin/nvcc
fi

. ${HOME}/.profile

# --- Sanity check ---
# sudo apt install cmake

# Have to use gcc 8 to compile this
# https://askubuntu.com/questions/1419593/how-to-resolve-the-error-package-gcc-8-has-no-installation-candidate-im-t
echo "Running samples..."

if [[ -d "$PREFIX/cuda-samples" ]]; then
  rm -rf $PREFIX/cuda-samples
fi

git clone https://github.com/NVIDIA/cuda-samples.git $PREFIX/cuda-samples
cd $PREFIX/cuda-samples
git checkout tags/v$CUDA_VERSION -b working_dir

if [ "$CUDA_VERSION" == "13.0" ]; then
  mkdir build && cd build
  $HOME/.local/cmake/bin/cmake ..
  make -j1
  cd ./Samples/1_Utilities/deviceQuery
elif [ "$CUDA_VERSION" == "10.2" ]; then
  cd ./Samples/deviceQuery
  make
fi

./deviceQuery > "deviceQuery.txt"
bash $SOURCE_DIR/validate_gpu.sh "deviceQuery.txt"
rm -rf deviceQuery.txt

cd $PREFIX && rm -rf cuda-samples
# cd ..
# python run_tests.py --output ./test --dir ./build/Samples --config test_args.json


echo "===================== CUDA Setup Finished ====================="
