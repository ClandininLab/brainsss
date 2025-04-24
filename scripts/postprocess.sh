#!/bin/bash
#SBATCH --job-name=postpro
#SBATCH --partition=trc
#SBATCH --time=10:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=./logs/mainlog.out
#SBATCH --open-mode=append

while [[ $# -gt 0 ]]; do
  case $1 in
    -pp|--postprocess)
      POSTPROCESS="$2"
      shift
      shift
      ;;
    -best|--best_flies)
      BEST_FLIES=True
      shift
      shift
      ;;
     -fb|--filter_bins)
      FILTER_BINS=True
      shift
      ;;
    -rts|--relative_ts)
      RELATIVE_TS=True
      shift
      ;;
    -tf|--temp_filter)
      TEMP_FILTER=True
      shift
      ;;
    -wbi|--whole_brain_interp)
      WHOLE_BRAIN_INTERP=True
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

ARGS="{\"PWD\":\"$PWD\",\"POSTPROCESS\":\"$POSTPROCESS\",\"BEST_FLIES\":\"$BEST_FLIES\",\"FILTER_BINS\":\"$FILTER_BINS\",\"RELATIVE_TS\":\"$RELATIVE_TS\",\
\"WHOLE_BRAIN_INTERP\":\"$WHOLE_BRAIN_INTERP\",\"TEMP_FILTER\":\"$TEMP_FILTER\",\"MAKE_SUPERVOXELS\":\"$MAKE_SUPERVOXELS\"}"

ml python/3.6
date
python3 -u ./postprocess.py $ARGS
