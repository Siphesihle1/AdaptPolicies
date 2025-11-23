#!/bin/bash
# specify a partition
#SBATCH -p bigbatch
# specify number of nodes
#SBATCH -N 1
# specify number of cores
##SBATCH -n 1
# specify memory pool for all cores
##SBATCH --mem 10
# specify the wall clock time limit for the job
##SBATCH -t 00:10:00
# specify the job name
#SBATCH -J ollama-install
# specify the filename to be used for writing output
#SBATCH -o /home-mscluster/smthethwa/ollama-install-slurm.%N.%j.out
# specify the filename for stderr
#SBATCH -e /home-mscluster/smthethwa/ollama-install-slurm.%N.%j.err

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

OLLAMA_PREFIX=~/.local/ollama
OLLAMA_EXEC=$OLLAMA_PREFIX/bin/ollama
MODEL="deepseek-r1:14b"

cd $SLURM_SUBMIT_DIR

if [ ! -d ./Downloads ]; then
  mkdir Downloads
fi

cd Downloads

if [ ! -d "$OLLAMA_PREFIX" ]; then
  mkdir -p $OLLAMA_PREFIX
fi

if [ ! -f "./Downloads/ollama-linux-amd64.tgz" ]; then
  echo "Downloading ollama executable..."
  curl -fsSL https://ollama.com/download/ollama-linux-amd64.tgz -o ollama-linux-amd64.tgz
  tar -C $OLLAMA_PREFIX ollama-linux-amd64.tgz
  chmod +x $OLLAMA_EXEC

  echo 'export PATH="$PATH:~/.local/ollama/bin"' >> ~/.bashrc
fi

$OLLAMA_EXEC --version
$OLLAMA_EXEC serve
$OLLAMA_EXEC pull $MODEL

echo "Testing the deepseek model"

TEST_PROMPT="Write a python function to print the names of all the files in a directory"

time -f "Time without tinking: %E" $OLLAMA_EXEC run $MODEL --think=false $TEST_PROMPT 
time -f "Time with thinking: %E" $OLLAMA_EXEC run $MODEL --think $TEST_PROMPT 

