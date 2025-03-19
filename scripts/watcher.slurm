#!/bin/bash
#SBATCH --job-name=watcher
#SBATCH --time=07:00:00
#SBATCH --partition=trc
#SBATCH --output=./logs/mainlog.out
#SBATCH --open-mode=append

while true; do
    bash -u ./check_and_submit.sh
    sleep 600  # Wait 10 minutes before checking again
done
