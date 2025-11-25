#!/bin/bash

# start tmux session
tmux new -s startx 

conda activate research_proj
# start X server on DISPLAY 0
# single X server should be sufficient for multiple instances of THOR
python startx.py 0  # if this throws errors e.g "(EE) Server terminated with error (1)" or "(EE) already running ..." try a display > 0

# detach from tmux shell
# Ctrl+b then d
tmux detach

# set DISPLAY variable to match X server
conda activate research_proj

# check THOR
cd $ALFRED_ROOT
python scripts/check_thor.py

###############
## (300, 300, 3)
## Everything works!!!
