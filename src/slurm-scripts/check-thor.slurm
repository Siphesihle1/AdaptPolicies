#!/bin/bash
# specify a partition
#SBATCH -p stampede
# specify number of nodes
#SBATCH -N 1
# specify number of cores
##SBATCH -n 1
# specify memory pool for all cores
##SBATCH --mem 10
# specify the wall clock time limit for the job
##SBATCH -t 00:10:00
# specify the job name
#SBATCH -J check-thor
# specify the filename to be used for writing output
#SBATCH -o /home-mscluster/smthethwa/slurm-logs/check-thor/%j.out
# specify the filename for stderr
#SBATCH -e /home-mscluster/smthethwa/slurms-logs/check-thor/%j.err

echo ------------------------------------------------------
echo -n 'Job is running on node ' $SLURM_JOB_NODELIST
echo ------------------------------------------------------
echo SLURM: sbatch is running on $SLURM_SUBMIT_HOST
echo SLURM: job ID is $SLURM_JOB_ID
echo SLURM: submit directory is $SLURM_SUBMIT_DIR
echo SLURM: number of nodes allocated is $SLURM_JOB_NUM_NODES
echo SLURM: number of cores is $SLURM_NTASKS
echo SLURM: job name is $SLURM_JOB_NAME
echo ------------------------------------------------------

cd $SLURM_SUBMIT_DIR

JOB_OUTPUT_DIR=~/outputs/check-thor/$SLURM_JOB_ID

# Create output directory for the job
if [ ! -d "$JOB_OUTPUT_DIR" ]; then
  mkdir -p $JOB_OUTPUT_DIR
fi

# Load conda to environment
source ~/.bashrc

# Update conda env
conda env update -f $SCRIPT_DIR/../environment.yml -n research_proj
conda run --live-stream -n research_proj patch-package

# Run test script
conda run --live-stream -n research_proj -- JOB_OUTPUT_DIR=$JOB_OUTPUT_DIR bash src/ai2thor_test.sh
