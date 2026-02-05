#!/bin/bash

# Copy dataset to output directory
echo "--- Copying Progprompt dataset to output directory ---"
cp -r $PROGPROMPT_PREFIX/data/ $PROGPROMPT_DATASET_DIR/

# Run progprompt script
echo "--- Running Progprompt Script ---"
python "$PROGPROMPT_PREFIX/run_eval.py" \
  --expt-name "ProgPrompt_Eval" \
  --env-id 0 \
  --test-set "test_seen" \
  --examples-type "default" \
  --examples-num 3
