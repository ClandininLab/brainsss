#!/bin/bash
#SBATCH --job-name=postpro
#SBATCH --partition=trc
#SBATCH --time=10-00:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=./logs/mainlog.out
#SBATCH --open-mode=append
#SBATCH --mail-type=BEGIN,END,FAIL

while [[ $# -gt 0 ]]; do
  case $1 in
    -post|--postprocess)
      POSTPROCESS=True
      shift
      ;;
    -best|--best_flies)
      BEST_FLIES=True
      shift
      ;;
    -f|--flies)
      FLIES="$2"
      shift
      shift
      ;;
    -e|--events)
      EVENTS="$2"
      shift
      shift
      ;;
    -cc|--channel_change)
      CHANNEL_CHANGE="$2"
      shift
      ;;
    --redo)
      REDO=True
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
    -tSTA|--tf_to_STA)
      TF_TO_STA=True
      shift
      ;;
    --supervox)
      MAKE_SUPERVOXELS=True
      shift
      ;;
    -STA|--build_STA)
      BUILD_STA=True
      shift
      ;;
    -lt|--later_transfer)
      LATER_TRANSFER=True
      shift
      ;;
    -rn|--regress_noise)
      REGRESS_NOISE=True
      shift
      ;;
    -sc|--supercluster)
      SUPERCLUSTER="$2"
      shift
      shift
      ;;
    -giv|--get_ind_vox)
      GET_IND_VOX=True
      shift
      ;;
    -ic|--individual_clusters)
      INDIVIDUAL_CLUSTERS=True
      shift
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

ARGS="{\"PWD\":\"$PWD\",\"BEST_FLIES\":\"$BEST_FLIES\",\"POSTPROCESS\":\"$POSTPROCESS\",\"FILTER_BINS\":\"$FILTER_BINS\",\"RELATIVE_TS\":\"$RELATIVE_TS\",\
\"FLIES\":\"$FLIES\",\"EVENTS\":\"$EVENTS\",\"TEMP_FILTER\":\"$TEMP_FILTER\",\"CHANNEL_CHANGE\":\"$CHANNEL_CHANGE\",\"MAKE_SUPERVOXELS\":\"$MAKE_SUPERVOXELS\",\
\"BUILD_STA\":\"$BUILD_STA\",\"REDO\":\"$REDO\",\"LATER_TRANSFER\":\"$LATER_TRANSFER\",\"REGRESS_NOISE\":\"$REGRESS_NOISE\",\"SUPERCLUSTER\":\"$SUPERCLUSTER\",\
\"TF_TO_STA\":\"$TF_TO_STA\",\"GET_IND_VOX\":\"$GET_IND_VOX\",\"INDIVIDUAL_CLUSTERS\":\"$INDIVIDUAL_CLUSTERS\"}"

ml python/3.6
date
echo "Running: python3 -u ./postprocess.py $ARGS"
python3 -u ./postprocess.py $ARGS
