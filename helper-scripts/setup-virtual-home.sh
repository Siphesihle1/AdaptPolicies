#!/bin/bash

shopt -s nullglob

# echo "--- Installing the virtualhome package ---"

# cd $VIRTUALHOME_DIR

# Install dependencies
# pip install -e .

# Install the simulator
echo "--- Detected the $OSTYPE operating system ---"
if [[ "$OSTYPE" == "linux-gnu" ]]; then
    SIM_NAME="linux_exec"
    SUFFIX="x86_64"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    SIM_NAME="macos_exec"
    SUFFIX="app"
elif [[ "$OSTYPE" == "windows" ]]; then
    SIM_NAME="windows_exec"
    SUFFIX="exe"
else
    echo "OS not recognized"
fi

echo "--- Downloading ---"
SIM_VERSION_NUMBER=${VIRTUALHOME_SIM_VERSION##*/}

if [ ! -f ~/Downloads/${SIM_NAME}.${SIM_VERSION_NUMBER}.zip ]; then
    echo "--- Simulator not found in Downloads, downloading... ---"
    wget http://virtual-home.org/release/simulator/${VIRTUALHOME_SIM_VERSION}/${SIM_NAME}.zip -O ~/Downloads/${SIM_NAME}.${SIM_VERSION_NUMBER}.zip
else
    echo "--- Simulator found in Downloads, skipping download ---"
fi

echo "--- Unzipping simulator ---"
SIM_EXE_PATTERN="${VIRTUALHOME_ROOT}/simulation/${SIM_NAME}.*${SIM_VERSION_NUMBER##v}*.${SUFFIX}"
SIM_EXE=($SIM_EXE_PATTERN)

if (( "${#SIM_EXE[@]}" > 0 )); then
  echo "--- Simulation folder already exists, skipping creation ---"
else
  unzip -o ~/Downloads/${SIM_NAME}.${SIM_VERSION_NUMBER}.zip -d ${VIRTUALHOME_ROOT}/simulation
  echo "--- Executable moved to simulation folder ---"
fi
