#!/bin/bash
#SBATCH --job-name=moco
#SBATCH --partition=trc
#SBATCH --time=4-00:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --output=./logs/mainlog.out
#SBATCH --open-mode=append

date

directory=$1
master_brain=$2
mirror_brain=$3

echo $directory
echo $master_brain
echo $mirror_brain

args="{\"directory\":\"$directory\",\"master_brain\":\"$master_brain\",\"mirror_brain\":\"$mirror_brain\"}"

ml python/3.6 antspy/0.2.2

python3 -u ./motion_correction.py $args