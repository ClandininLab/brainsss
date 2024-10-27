#!/bin/bash
#SBATCH --job-name=prepro
#SBATCH --partition=trc
#SBATCH --time=4-00:00:00
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
    -cc|--channel_change)
      CHANNEL_CHANGE=True
      shift
      ;;
    -bg|--background_subtraction)
      BACKGROUND_SUBTRACTION=True
      shift
      ;;
    -rw|--raw_warp)
      RAW_WARP=True
      shift
      ;;
    -tsw|--timestamp_warp)
      TIMESTAMP_WARP=True
      shift
      ;;
    --fictrac_qc)
      FICTRAC_QC=True
      shift
      ;;
    --bleaching_qc)
      BLEACHING_QC=True
      shift
      ;;
    --meanpre|--temporal_mean_brain_pre)
      TEMPORAL_MEAN_BRAIN_PRE=True
      shift
      ;;
    --meanpost|--temporal_mean_brain_post)
      TEMPORAL_MEAN_BRAIN_POST=True
      shift
      ;;
    --h52nii|--H5_TO_NII)
      H5_TO_NII=True
      shift
      ;;
    --clean_anat)
      CLEAN_ANAT=True
      shift
      ;;
    --f2a)
      FUNC2ANAT=True
      shift
      ;;
    --a2a)
      ANAT2ATLAS=True
      shift
      ;;
    --supervox)
      MAKE_SUPERVOXELS=True
      shift
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

ARGS="{\"PWD\":\"$PWD\",\"BUILDFLIES\":\"$BUILDFLIES\",\"FLIES\":\"$FLIES\",\"DIRTYPE\":\"$DIRTYPE\",\
\"MOCO\":\"$MOCO\",\"CHANNEL_CHANGE\":\"$CHANNEL_CHANGE\",\"BACKGROUND_SUBTRACTION\":\"$BACKGROUND_SUBTRACTION\",\
\"RAW_WARP\":\"$RAW_WARP\",\"TIMESTAMP_WARP\":\"$TIMESTAMP_WARP\",\"FICTRAC_QC\":\"$FICTRAC_QC\",\
\"BLEACHING_QC\":\"$BLEACHING_QC\",\"TEMPORAL_MEAN_BRAIN_PRE\":\"$TEMPORAL_MEAN_BRAIN_PRE\",\"H5_TO_NII\":\"$H5_TO_NII\",\
\"TEMPORAL_MEAN_BRAIN_POST\":\"$TEMPORAL_MEAN_BRAIN_POST\",\"CLEAN_ANAT\":\"$CLEAN_ANAT\",\
\"FUNC2ANAT\":\"$FUNC2ANAT\",\"ANAT2ATLAS\":\"$ANAT2ATLAS\",\"MAKE_SUPERVOXELS\":\"$MAKE_SUPERVOXELS\"}"

ml python/3.6
date
python3 -u ./preprocess.py $ARGS
