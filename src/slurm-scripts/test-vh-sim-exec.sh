#!/bin/bash
#SBATCH --partition=bigbatch
##SBATCH -w mscluster59
#SBATCH --job-name=test-vh-sim-exec
#SBATCH --output=/home-mscluster/smthethwa/slurm-logs/test-vh-sim-exec/%j.out
#SBATCH --error=/home-mscluster/smthethwa/slurm-logs/test-vh-sim-exec/%j.err

echo ------------------------------------------------------
echo "Job is running on node  $SLURM_JOB_NODELIST"
echo ------------------------------------------------------
echo SLURM: sbatch is running on $SLURM_SUBMIT_HOST
echo SLURM: job ID is $SLURM_JOB_ID
echo SLURM: submit directory is $SLURM_SUBMIT_DIR
echo SLURM: number of nodes allocated is $SLURM_JOB_NUM_NODES
echo SLURM: job name is $SLURM_JOB_NAME
echo ------------------------------------------------------

cd $SLURM_SUBMIT_DIR

JOB_OUTPUT_DIR=$HOME/outputs/test-vh-sim-exec/$SLURM_JOB_ID
LOCAL_OUTPUT_DIR=/scratch/smthethwa/outputs/test-vh-sim-exec/$SLURM_JOB_ID
DATASET_DIR=/scratch/smthethwa/datasets/progprompt

# Create output directory for the job
if [ ! -d "$JOB_OUTPUT_DIR" ]; then
  mkdir -p $JOB_OUTPUT_DIR
fi

if [ ! -d "$LOCAL_OUTPUT_DIR" ]; then
  mkdir -p $LOCAL_OUTPUT_DIR
fi

# Create dataset directory
if [ ! -d "$DATASET_DIR" ]; then
  mkdir -p $DATASET_DIR
fi

# Load conda to environment
source ~/.bashrc

# Run setup script
conda run --live-stream -n research_proj DATASET_DIR=$DATASET_DIR JOB_OUTPUT_DIR=$LOCAL_OUTPUT_DIR bash src/test-scripts/virtual_home_exec_test.sh

# Copy results back to home directory
mv $LOCAL_OUTPUT_DIR/ $JOB_OUTPUT_DIR/

echo "-- Job Completed --"

