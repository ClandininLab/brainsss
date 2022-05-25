#!/bin/bash
#SBATCH --job-name=ash
#SBATCH --partition=trc
#SBATCH --time=2-00:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=./logs/mainlog.out
#SBATCH --open-mode=append

ml python/3.6
date
python3 -u ./quick_ashley_mean.py
