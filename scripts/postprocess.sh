#!/bin/bash
#SBATCH --job-name=postpro
#SBATCH --partition=trc
#SBATCH --time=10:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=./logs/mainlog.out
#SBATCH --open-mode=append

echo "====== Starting postprocess.sh at $(date) ======"
echo "Environment info:"
echo "User: $(whoami)"
echo "Host: $(hostname)"
echo "Working directory: $PWD"

while [[ $# -gt 0 ]]; do
  case $1 in
    -pp|--postprocess)
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
      CHANNEL_CHANGE=True
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

ARGS="{\"PWD\":\"$PWD\",\"BEST_FLIES\":\"$BEST_FLIES\",\"POSTPROCESS\":\"$POSTPROCESS\",\"FILTER_BINS\":\"$FILTER_BINS\",\"RELATIVE_TS\":\"$RELATIVE_TS\",\
\"FLIES\":\"$FLIES\",\"EVENTS\":\"$EVENTS\",\"TEMP_FILTER\":\"$TEMP_FILTER\",\"CHANNEL_CHANGE\":\"$CHANNEL_CHANGE\",\"MAKE_SUPERVOXELS\":\"$MAKE_SUPERVOXELS\"}"

# ml python/3.6
# date
# echo "Running: python3 -u ./postprocess.py $ARGS"
# python3 -u ./postprocess.py $ARGS

echo "Arguments prepared:"
echo "$ARGS"
echo "$ARGS" > ./args_temp.json

# Check for Python and script
echo "Looking for Python and script files..."
echo "Files in current directory:"
ls -la *.py

# Load Python module
echo "Loading Python module..."
ml python/3.6
PYTHON_STATUS=$?
if [ $PYTHON_STATUS -ne 0 ]; then
    echo "WARNING: Module loading returned status $PYTHON_STATUS"
fi

# Check Python availability
PYTHON_PATH=$(which python3)
echo "Python path: $PYTHON_PATH"
echo "Python version: $(python3 --version 2>&1)"

# Check if postprocess.py exists
SCRIPT_PATH="$PWD/postprocess.py"
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "ERROR: $SCRIPT_PATH does not exist!"
    exit 1
else
    echo "Script found: $SCRIPT_PATH"
    echo "Script permissions: $(ls -l $SCRIPT_PATH)"
fi

# Make sure script is executable
chmod +x "$SCRIPT_PATH"
echo "Made script executable"

# Try running a simple Python command
echo "Testing Python with simple command..."
python3 -c "print('Python is working correctly')" 
if [ $? -ne 0 ]; then
    echo "ERROR: Basic Python test failed"
    exit 1
fi

# Run the actual script with arguments
echo "====== Running postprocess.py at $(date) ======"
echo "Command: $PYTHON_PATH -u $SCRIPT_PATH $(cat ./args_temp.json)"

# Run with error capturing
$PYTHON_PATH -u "$SCRIPT_PATH" "$(cat ./args_temp.json)" 2>./python_errors.log
PYTHON_EXIT=$?

# Check for errors
if [ $PYTHON_EXIT -ne 0 ]; then
    echo "ERROR: Python script exited with code $PYTHON_EXIT"
    echo "Error output:"
    cat ./python_errors.log
else
    echo "Script completed with exit code $PYTHON_EXIT"
fi

# Clean up
rm -f ./args_temp.json
rm -f ./python_errors.log

echo "====== Completed postprocess.sh at $(date) ======"