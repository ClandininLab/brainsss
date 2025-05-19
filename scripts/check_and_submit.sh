#!/bin/bash

# Define the job name or ID you want to check
JOB_NAME="postpro"

# Check if the job is running
if ! squeue -u $USER | grep -q "$JOB_NAME"; then
    echo "Job $JOB_NAME not running. Submitting a new job..."
    sbatch postprocess.sh -post -e 10flies -best
else
    echo "Job $JOB_NAME is still running."
fi
