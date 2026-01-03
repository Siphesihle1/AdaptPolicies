#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"

# start tmux session
tmux new -s startx 

Xvfb :1 \
  -screen 0 1920x1080x24 \
  -listen tcp \
  +extension GLX \
  +render \
  -ac

# detach from tmux shell
tmux detach

# check THOR
python $SCRIPT_DIR/ai2thor_test.py

# kill tmux session
tmux kill-session -t startx
