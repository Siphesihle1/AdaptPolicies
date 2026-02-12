#!/bin/bash

# Copy dataset to output directory
echo "--- Copying Progprompt dataset to output directory ---"
cp -r $PROGPROMPT_PREFIX/data/* $PROGPROMPT_DATASET_DIR/

# Run progprompt script
echo "--- Running Progprompt Script ---"
python "$PROGPROMPT_PREFIX/run_eval.py" \
  --expt-name "ProgPrompt_Eval_Train_VH_Timeout_Error" \
  --env-id 0 \
  --test-set "train" \
  --examples-type "random" \
  --examples-num 3
