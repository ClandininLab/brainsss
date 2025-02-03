#!/bin/bash
#SBATCH --job-name=watcher
#SBATCH --time=00:3:00
#SBATCH --partition=trc
#SBATCH --output=./logs/mainlog.out

while true; do
    bash -u ./check_and_submit.sh
    sleep 600  # Wait 10 minutes before checking again
done
