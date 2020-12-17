#!/bin/sh

if [ -z "$1" ] || [ -z "$2" ]
  then
    >&2 echo "Usage:\n  $0 <output file> <size>"
    exit 1
fi

python -m pathways --num-simulations 1 --num-consignments $2 --config-file config.yml --output-file $1
