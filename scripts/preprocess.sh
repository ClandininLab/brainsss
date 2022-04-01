#!/bin/bash
#SBATCH --job-name=prepro
#SBATCH --partition=trc
#SBATCH --time=7-00:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=./logs/mainlog.out
#SBATCH --open-mode=append

while [[ $# -gt 0 ]]; do
  case $1 in
    -b|--build_flies)
      BUILDFLIES="$2"
      shift
      shift
      ;;
    -f|--flies)
      FLIES="$2"
      shift
      shift
      ;;
    -d|--dirtype)
      DIRTYPE="$2"
      shift
      shift
      ;;
    -m|--moco)
      MOCO=True
      shift
      ;;
    -z|--zscore)
      ZSCORE=True
      shift
      ;;
    -h|--highpass)
      HIGHPASS=True
      shift
      ;;
    -c|--correlation)
      CORRELATION=True
      shift
      ;;
    --fictrac_qc)
      FICTRAC_QC=True
      shift
      ;;
    --STB)
      STB=True
      shift
      ;;
    --bleaching_qc)
      BLEACHING_QC=True
      shift
      ;;
    --temporal_mean_brain_pre)
      TEMPORAL_MEAN_BRAIN_PRE=True
      shift
      ;;
    --temporal_mean_brain_post)
      TEMPORAL_MEAN_BRAIN_POST=True
      shift
      ;;
    --STA)
      STA=True
      shift
      ;;
    --H5_TO_NII)
      H5_TO_NII=True
      shift
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

ARGS="{\"PWD\":\"$PWD\",\"BUILDFLIES\":\"$BUILDFLIES\",\"FLIES\":\"$FLIES\",\"DIRTYPE\":\"$DIRTYPE\", \
\"MOCO\":\"$MOCO\",\"ZSCORE\":\"$ZSCORE\",\"HIGHPASS\":\"$HIGHPASS\",\"CORRELATION\":\"$CORRELATION\", \
\"FICTRAC_QC\":\"$FICTRAC_QC\",\"STB\":\"$STB\",\"BLEACHING_QC\":\"$BLEACHING_QC\", \
\"TEMPORAL_MEAN_BRAIN_PRE\":\"$TEMPORAL_MEAN_BRAIN_PRE\",\"STA\":\"$STA\",\"H5_TO_NII\":\"$H5_TO_NII\", \
\"TEMPORAL_MEAN_BRAIN_POST\":\"$TEMPORAL_MEAN_BRAIN_POST\"}"

ml python/3.6
date
python3 -u ./preprocess.py $ARGS