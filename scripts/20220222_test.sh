#!/bin/bash
#SBATCH --job-name=testing
#SBATCH --partition=trc
#SBATCH --time=4-00:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=./logs/mainlog.out
#SBATCH --open-mode=append

ml python/3.6
ml antspy/0.2.2
ml py-numpy/1.14.3_py36
date
python3 -u ./20220222_test.py $PWD $1