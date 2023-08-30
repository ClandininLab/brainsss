#!/bin/bash
#SBATCH --job-name=moco
#SBATCH --partition=trc
#SBATCH --time=2-00:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --output=./logs/mainlog.out
#SBATCH --open-mode=append

date

directory=$1
brain_master=$2
brain_mirror=$3

echo $directory
echo $brain_master
echo $brain_mirror

# Optional params
type_of_transform=${4:-"SyN"}
output_format=${5:-"h5"}
echo $type_of_transform
echo $output_format

args="{\"directory\":\"$directory\",\"brain_master\":\"$brain_master\",\"brain_mirror\":\"$brain_mirror\","\
"\"type_of_transform\":\"$type_of_transform\",\"output_format\":\"$output_format\"}"

# ml python/3.6 antspy/0.2.2

python3 -u ./motion_correction.py $args
