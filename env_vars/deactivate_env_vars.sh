#!/bin/bash

export PATH=$(echo $PATH | sed -e "s|$CONDA_PREFIX/bin:||g")
unset PROJECT_ROOT
unset ALFRED_ROOT
unset PYTHONPATH
unset ALFRED_DATA
unset LIBGL_ALWAYS_INDIRECT
unset DISPLAY
unset AI2THOR_PREFIX
