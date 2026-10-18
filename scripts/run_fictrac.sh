#!/bin/bash
#SBATCH -J fictrac
#SBATCH -p trc,normal
#SBATCH -t 2:00:00
#SBATCH -c 4
#SBATCH --mem=8G
#SBATCH --constraint=CPU_MNF:INTEL
#SBATCH -o ./logs/fictrac_%j.out

# Run FicTrac offline on one Jackfish series.
# Usage: sbatch run_fictrac.sh <jackfish_root> <fictrac_output_root> <date> <fly> <series>
# Intel-only: Sherlock's opencv/4.12.0 module dies with Illegal Instruction on the AMD (MLN) nodes.

set -e

if [ "$#" -ne 5 ]; then
    echo "Usage: sbatch run_fictrac.sh <jackfish_root> <fictrac_output_root> <date> <fly> <series>" >&2
    exit 1
fi
JACKFISH_ROOT=$1
FICTRAC_OUTPUT_ROOT=$2
DATE=$3
FLY=$4
SERIES=$5

VID_DIR=$JACKFISH_ROOT/$DATE/$FLY/$SERIES
OUT_DIR=$FICTRAC_OUTPUT_ROOT/$DATE/$FLY/$SERIES
mkdir -p "$OUT_DIR"

shopt -s nullglob
MP4S=("$VID_DIR"/*.mp4)
shopt -u nullglob
if [ "${#MP4S[@]}" -ne 1 ]; then
    echo "Expected exactly 1 .mp4 in $VID_DIR, found ${#MP4S[@]}" >&2
    exit 1
fi
MP4=${MP4S[0]}
MP4_NAME=$(basename "$MP4")

cp "$VID_DIR/config_CL.txt" "$OUT_DIR/config_used.txt"
cd "$OUT_DIR"

# FicTrac writes its outputs next to the source video, so point it at a local symlink
ln -sf "$MP4" "./$MP4_NAME"
trap 'rm -f "$OUT_DIR/$MP4_NAME"' EXIT

sed -i -E \
    -e "s|^([[:space:]]*src_fn[[:space:]]*:).*|\1 ./$MP4_NAME|" \
    -e "s|^([[:space:]]*do_display[[:space:]]*:).*|\1 n|" \
    -e "/^[[:space:]]*sock_(host|port)[[:space:]]*:/d" \
    config_used.txt

# sbatch runs a spooled copy of this script, so $0 is not in scripts/ under Slurm; fall back to the submit dir
ENV_SH="$(dirname "$0")/fictrac_env.sh"
if [ ! -f "$ENV_SH" ]; then
    ENV_SH="$SLURM_SUBMIT_DIR/fictrac_env.sh"
fi
source "$ENV_SH"

# -v must come before the config; after it, it is ignored and the log grows to hundreds of MB
fictrac -v WRN config_used.txt

rm -f "./$MP4_NAME"
chgrp -R oak_trc "$OUT_DIR"

ls "$OUT_DIR"/*.dat
