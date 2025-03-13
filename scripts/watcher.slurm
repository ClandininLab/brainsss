#!/bin/bash
#SBATCH --job-name=watcher
#SBATCH --time=10:00:00
#SBATCH --partition=trc
#SBATCH --output=./logs/mainlog.out
#SBATCH --open-mode=append

while true; do
    bash -u ./check_and_submit.sh
    sleep 1800  # Wait 30 min before checking again
done
