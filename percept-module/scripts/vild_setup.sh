#!/bin/bash

PACKAGES=$1

# === Setup for t ViLD (Visual and Language Knowledge Distillation) ===

# 1. Download tensorflow wheel file
if [ ! -e "$PACKAGES/tensorflow-1.15.2-cp37-cp37m-linux_x86_64.whl" ]; then
  wget "https://nextjournal.com/data/QmYfqhzSkpXskK4kNwYTRtQcsrDw1LiUV4XiFavj8nNRCh?content-type=application%2Fzip&filename=tensorflow-1.15.2-cp37-cp37m-linux_x86_64.whl" -O "$PACKAGES/tensorflow-1.15.2-cp37-cp37m-linux_x86_64.whl"
fi


# 2. Install system dependencies
sudo apt-get -y install libhdf5-serial-dev hdf5-tools libhdf5-dev zlib1g-dev zip libjpeg8-dev