#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"

# check THOR
xvfb-run --server-args="-screen 0 1920x1080x24" python $SCRIPT_DIR/ai2thor_test.py

