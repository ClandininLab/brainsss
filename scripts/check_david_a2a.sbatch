#!/bin/bash
#SBATCH --job-name=check_a2a
#SBATCH --partition=trc
#SBATCH --time=02:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=./logs/check_david_a2a_%j.out
#SBATCH --open-mode=append

# Run from scripts/:  sbatch check_david_a2a.sbatch [--flip-z]
TEMPLATE=/path/to/david_meanbrain.nii
ANAT=/path/to/fly_001/anat_0/moco/anatomy_channel_1_moc_mean_clean.nii
OUT_DIR=/path/to/check_david_a2a/fly_001

date

ml python/3.6

export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$SLURM_CPUS_PER_TASK

python3 -u ./check_david_a2a.py "$TEMPLATE" "$ANAT" "$OUT_DIR" "$@"

date
