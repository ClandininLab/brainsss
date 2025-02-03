#!/bin/bash

# Define the job name or ID you want to check
JOB_NAME="prepro"

# Check if the job is running
if ! squeue -u $USER | grep -q "$JOB_NAME"; then
    echo "Job $JOB_NAME not running. Submitting a new job..."
    sbatch preprocess.sh -f fly_208 -fb -rts -tf --supervox
else
    echo "Job $JOB_NAME is still running."
fi
