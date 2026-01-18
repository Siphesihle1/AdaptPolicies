#!/bin/bash

OLLAMA_PREFIX=~/.local/ollama
OLLAMA_EXEC=$OLLAMA_PREFIX/bin/ollama

# Run the background, in a way that survives to the next step
nohup OLLAMA_DEBUG=1 $OLLAMA_EXEC serve > $HOME/ollama.log 2>&1 &

# Block using the ready endpoint
time curl --retry 360 --retry-connrefused --retry-delay 2 -sf $OLLAMA_HOST

