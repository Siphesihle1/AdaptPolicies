#!/bin/bash

SOURCE_DIR=$(dirname -- ${BASH_SOURCE[0]})
PREFIX=$1
CUDA_VERSION=$2

echo "Running samples..."

if [[ -d "$PREFIX/cuda-samples" ]]; then
  rm -rf $PREFIX/cuda-samples
fi

git clone https://github.com/NVIDIA/cuda-samples.git $PREFIX/cuda-samples
cd $PREFIX/cuda-samples
git checkout tags/v$CUDA_VERSION -b working_dir

if [[ "$CUDA_VERSION" == "13.0" || "$CUDA_VERSION" == "11.8" ]]; then
  cd ./Samples/1_Utilities/deviceQuery
  make -j1
elif [ "$CUDA_VERSION" == "10.2" ]; then
  cd ./Samples/deviceQuery
  make
fi

./deviceQuery > "deviceQuery.txt"
bash $SOURCE_DIR/validate_gpu.sh "deviceQuery.txt"
rm -rf deviceQuery.txt

cd $PREFIX && rm -rf cuda-samples
