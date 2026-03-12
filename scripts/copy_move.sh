#!/bin/bash
#SBATCH --job-name=copy_new_files
#SBATCH --time=24:00:00
#SBATCH --mem=8G
#SBATCH --cpus-per-task=1
#SBATCH --output=copy_%j.log
#SBATCH --error=copy_%j.err

# Copy only files that don't exist in destination
rsync -av --ignore-existing --inplace --progress \
  /scratch/groups/trc/ilanazs/ /scratch/users/ilanazs/