#!/bin/bash

# Installs cuda-tookit version 13.0 on wsl2
# https://developer.nvidia.com/cuda-downloads?target_os=Linux&target_arch=x86_64&Distribution=WSL-Ubuntu&target_version=2.0&target_type=deb_local
# https://docs.nvidia.com/cuda/wsl-user-guide/index.html#getting-started-with-cuda-on-wsl-2

PREFIX=$1
CUDA_VERSION=$2

if [ "$CUDA_VERSION" = "13.0" ]; then
  wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-wsl-ubuntu.pin -P $PREFIX
  sudo mv $PREFIX/cuda-wsl-ubuntu.pin /etc/apt/preferences.d/cuda-repository-pin-600
  wget https://developer.download.nvidia.com/compute/cuda/13.0.1/local_installers/cuda-repo-wsl-ubuntu-13-0-local_13.0.1-1_amd64.deb -P $PREFIX
  sudo dpkg -i $PREFIX/cuda-repo-wsl-ubuntu-13-0-local_13.0.1-1_amd64.deb
  sudo cp /var/cuda-repo-wsl-ubuntu-13-0-local/cuda-*-keyring.gpg /usr/share/keyrings/
  sudo apt-get update
  sudo apt-get -y install cuda-toolkit-13-0
  sudo apt-mark hold cuda-toolkit-13-0
elif [ "$CUDA_VERSION" = "10.2" ]; then
  wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64/cuda-ubuntu1804.pin -P $PREFIX
  sudo mv $PREFIX/cuda-ubuntu1804.pin /etc/apt/preferences.d/cuda-repository-pin-600
  
  if [ ! -e "$PREFIX/cuda-repo-ubuntu1804-10-2-local-10.2.89-440.33.01_1.0-1_amd64.deb" ]; then
    wget https://developer.download.nvidia.com/compute/cuda/10.2/Prod/local_installers/cuda-repo-ubuntu1804-10-2-local-10.2.89-440.33.01_1.0-1_amd64.deb -P $PREFIX
  fi

  sudo dpkg -i $PREFIX/cuda-repo-ubuntu1804-10-2-local-10.2.89-440.33.01_1.0-1_amd64.deb
  sudo apt-key add /var/cuda-repo-10-2-local-10.2.89-440.33.01/7fa2af80.pub
  sudo apt-get update
  sudo apt-get -y install cuda-toolkit-10-2
  sudo apt-mark hold cuda-toolkit-10-2
elif [ "$CUDA_VERSION" = "11.6" ]; then
  wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-ubuntu2004.pin -P $PREFIX
  sudo mv $PREFIX/cuda-ubuntu2004.pin /etc/apt/preferences.d/cuda-repository-pin-600
  
  if [ ! -e "$PREFIX/cuda-repo-ubuntu2004-11-6-local_11.6.0-510.39.01-1_amd64.deb" ]; then
    wget https://developer.download.nvidia.com/compute/cuda/11.6.0/local_installers/cuda-repo-ubuntu2004-11-6-local_11.6.0-510.39.01-1_amd64.deb -P $PREFIX
  fi

  sudo dpkg -i $PREFIX/cuda-repo-ubuntu2004-11-6-local_11.6.0-510.39.01-1_amd64.deb
  sudo apt-key add /var/cuda-repo-ubuntu2004-11-6-local/7fa2af80.pub
  sudo apt-get update
  sudo apt-get -y install cuda-toolkit-11-6
  sudo apt-mark hold cuda-toolkit-11-6
elif [ "$CUDA_VERSION" = "11.7" ]; then
  wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin -P $PREFIX
  sudo mv $PREFIX/cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600
  
  if [ ! -e "$PREFIX/cuda-repo-ubuntu2204-11-7-local_11.7.0-515.43.04-1_amd64.deb" ]; then
    wget https://developer.download.nvidia.com/compute/cuda/11.7.0/local_installers/cuda-repo-ubuntu2204-11-7-local_11.7.0-515.43.04-1_amd64.deb -P $PREFIX
  fi
  
  sudo dpkg -i $PREFIX/cuda-repo-ubuntu2204-11-7-local_11.7.0-515.43.04-1_amd64.deb
  sudo cp /var/cuda-repo-ubuntu2204-11-7-local/cuda-*-keyring.gpg /usr/share/keyrings/
  sudo apt-get update
  sudo apt-get -y install cuda-toolkit-11-7
fi