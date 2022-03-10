#!/bin/bash

while [[ $# -gt 0 ]]; do
  case $1 in
    -e|--extension)
      EXTENSION="$2"
      shift # past argument
      shift # past value
      ;;
    -s|--searchpath)
      SEARCHPATH="$2"
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

echo "FILE EXTENSION  = ${EXTENSION}"
echo "SEARCH PATH     = ${SEARCHPATH}"
echo "DEFAULT         = ${DEFAULT}"