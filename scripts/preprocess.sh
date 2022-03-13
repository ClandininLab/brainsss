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
      shift # past argument
      shift # past value
      ;;
    -f|--flies)
      FLIES="$2"
      shift # past argument
      shift # past value
      ;;
    -d|--dirtype)
      DIRTYPE="$2"
      shift # past argument
      shift # past value
      ;;
    -m|--moco)
      MOCO=True
      shift # past argument
      ;;
    -z|--zscore)
      ZSCORE=True
      shift # past argument
      ;;
    -h|--highpass)
      HIGHPASS=True
      shift # past argument
      ;;
    --fictrac_qc)
      FICTRAC_QC=True
      shift # past argument
      ;;
    --STB) # stimulus triggered behavior
      STB=True
      shift # past argument
      ;;
    --bleaching_qc) # stimulus triggered behavior
      BLEACHING_QC=True
      shift # past argument
      ;;
    --temporal_mean_brain) # stimulus triggered behavior
      TEMPORAL_MEAN_BRAIN=True
      shift # past argument
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

ARGS="{\"PWD\":\"$PWD\",\"BUILDFLIES\":\"$BUILDFLIES\",\"FLIES\":\"$FLIES\",\"DIRTYPE\":\"$DIRTYPE\",\"MOCO\":\"$MOCO\",\"ZSCORE\":\"$ZSCORE\",\"HIGHPASS\":\"$HIGHPASS\",\"FICTRAC_QC\":\"$FICTRAC_QC\",\"STB\":\"$STB\",\"BLEACHING_QC\":\"$BLEACHING_QC\",\"TEMPORAL_MEAN_BRAIN\":\"$TEMPORAL_MEAN_BRAIN\"}"

ml python/3.6
date
python3 -u ./preprocess.py $ARGS