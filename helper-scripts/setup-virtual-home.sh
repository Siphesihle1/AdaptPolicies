#!/bin/bash

set -e
shopt -s nullglob
SIM_ROOT=${VIRTUALHOME_SIM_ROOT:-${VIRTUALHOME_ROOT}/simulation}

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
    exit 1
fi

echo "--- Downloading ---"
SIM_VERSION_NUMBER=${VIRTUALHOME_SIM_VERSION##*/}
SIM_ARCHIVE="$HOME/Downloads/${SIM_NAME}.${SIM_VERSION_NUMBER}.zip"
mkdir -p "$HOME/Downloads" "$SIM_ROOT"

if [ ! -f "$SIM_ARCHIVE" ]; then
    : "${VIRTUALHOME_SIM_URL:?Set VIRTUALHOME_SIM_URL to the simulator archive URL}"
    echo "--- Simulator not found in Downloads, downloading... ---"
    wget "$VIRTUALHOME_SIM_URL" -O "$SIM_ARCHIVE.part"
    mv -- "$SIM_ARCHIVE.part" "$SIM_ARCHIVE"
else
    echo "--- Simulator found in Downloads, skipping download ---"
fi

echo "--- Unzipping simulator ---"
SIM_EXE_PATTERN="${SIM_ROOT}/${SIM_NAME}.*${SIM_VERSION_NUMBER##v}*.${SUFFIX}"
SIM_EXE=($SIM_EXE_PATTERN)

if (( "${#SIM_EXE[@]}" > 0 )); then
  echo "--- Simulation folder already exists, skipping creation ---"
else
  unzip -q -o "$SIM_ARCHIVE" -d "$SIM_ROOT"
  # Some distributions include an enclosing executable/ directory.
  if [ -d "$SIM_ROOT/executable" ]; then
    for entry in "$SIM_ROOT/executable"/*; do
      mv -- "$entry" "$SIM_ROOT/"
    done
    rmdir "$SIM_ROOT/executable"
  fi
  SIM_EXE=($SIM_EXE_PATTERN)
  if (( ${#SIM_EXE[@]} == 0 )); then
    echo "Simulator executable not found in $SIM_ROOT" >&2
    exit 1
  fi
  chmod +x "${SIM_EXE[@]}"
  echo "--- Executable moved to simulation folder ---"
fi
