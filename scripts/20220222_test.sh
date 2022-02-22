#!/bin/bash
#SBATCH --job-name=testing
#SBATCH --partition=trc
#SBATCH --time=00:05:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=./logs/mainlog.out
#SBATCH --open-mode=append

ml python/3.6.1
ml antspy/0.2.2
date
python3 -u ./20220222_test.py $1 $PWD