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
    --meanpre|--temporal_mean_brain_pre)
      TEMPORAL_MEAN_BRAIN_PRE=True
      shift
      ;;
    --meanpost|--temporal_mean_brain_post)
      TEMPORAL_MEAN_BRAIN_POST=True
      shift
      ;;
    --STA)
      STA=True
      shift
      ;;
    --h52nii|--H5_TO_NII)
      H5_TO_NII=True
      shift
      ;;
    --use_warp)
      USE_WARP=True
      shift
      ;;
    --loco_dataset)
      LOCO_DATASET=True
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
    --apply_t)
      APPLY_TRANSFORMS=True
      shift
      ;;
    --grey_only)
      GREY_ONLY=True
      shift
      ;;
    --NZH)
      NO_ZSCORE_HIGHPASS=True
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
\"MOCO\":\"$MOCO\",\"ZSCORE\":\"$ZSCORE\",\"HIGHPASS\":\"$HIGHPASS\",\"CORRELATION\":\"$CORRELATION\",\
\"FICTRAC_QC\":\"$FICTRAC_QC\",\"STB\":\"$STB\",\"BLEACHING_QC\":\"$BLEACHING_QC\",\
\"TEMPORAL_MEAN_BRAIN_PRE\":\"$TEMPORAL_MEAN_BRAIN_PRE\",\"STA\":\"$STA\",\"H5_TO_NII\":\"$H5_TO_NII\",\
\"TEMPORAL_MEAN_BRAIN_POST\":\"$TEMPORAL_MEAN_BRAIN_POST\",\"USE_WARP\":\"$USE_WARP\",\
\"LOCO_DATASET\":\"$LOCO_DATASET\",\"CLEAN_ANAT\":\"$CLEAN_ANAT\",\"FUNC2ANAT\":\"$FUNC2ANAT\",\
\"ANAT2ATLAS\":\"$ANAT2ATLAS\",\"APPLY_TRANSFORMS\":\"$APPLY_TRANSFORMS\",\"GREY_ONLY\":\"$GREY_ONLY\",\
\"NO_ZSCORE_HIGHPASS\":\"$NO_ZSCORE_HIGHPASS\",\"MAKE_SUPERVOXELS\":\"$MAKE_SUPERVOXELS\"}"

source brainsss/bin/activate
ml python/3.6.1
ml py-ants/0.3.2_py36
date
python3 -u ./preprocess.py $ARGS