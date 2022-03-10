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
    -d|--default)
      DEFAULT=YES
      shift # past argument
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

echo "BUILDFLIES  = ${BUILDFLIES}"
echo "FLIES       = ${FLIES}"
echo "DIRTYPE     = ${DIRTYPE}"
echo "DEFAULT     = ${DEFAULT}"

ARGS="{\"PWD\":\"$PWD\",\"BUILDFLIES\":\"$BUILDFLIES\",\"FLIES\":\"$FLIES\",\"DIRTYPE\":\"$DIRTYPE\"}"

ml python/3.6
date
python3 -u ./preprocess.py $ARGS