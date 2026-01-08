#!/bin/bash
#SBATCH --partition=stampede
#SBATCH --job-name=setup-vh-sim
#SBATCH --output=/home-mscluster/smthethwa/slurm-logs/setup-vh-sim/%j.out
#SBATCH --error=/home-mscluster/smthethwa/slurm-logs/setup-vh-sim/%j.err

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

# Load conda to environment
source ~/.bashrc

# Update conda env
conda env update -f environment.yml -n research_proj

# Run setup script
conda run --live-stream -n research_proj bash helper-scripts/setup-virtual-home.sh

echo "-- Job Completed --"

