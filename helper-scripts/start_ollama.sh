#!/bin/bash

OLLAMA_HOST=$(python -c 'from methods.config import get_llm_settings; print(get_llm_settings()["base_url"])') || exit 1
export OLLAMA_HOST

# Remote endpoints are managed externally.
case "$OLLAMA_HOST" in
http://localhost:* | http://127.0.0.1:*) ;;
*) exit 0 ;;
esac

if curl -sf "$OLLAMA_HOST" >/dev/null; then
  exit 0
fi

echo "--- Starting local Ollama server ---"
OLLAMA_PREFIX=~/.local/ollama
OLLAMA_EXEC=$OLLAMA_PREFIX/bin/ollama

# Run the background, in a way that survives to the next step
export OLLAMA_DEBUG=1
nohup $OLLAMA_EXEC serve >$HOME/ollama.log 2>&1 &

# Block using the ready endpoint
time curl --retry 360 --retry-connrefused --retry-delay 2 -sf $OLLAMA_HOST
