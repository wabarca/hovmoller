#!/bin/bash

# export TZ=UTC

source /home/prometheus/miniconda3/etc/profile.d/conda.sh

conda activate showcast

cd /home/prometheus/workspace/scripts/satellite/hovmoller

echo "========================================"
echo "$(date -u) UTC"
echo "========================================"

python hovmoller_goes19_ch14_1.py

python hovmoller_goes19_ch14_2.py

cp hovmoller_goes19_c14.png /home/prometheus/workspace/SHOWCast/HTML/Output/QuickLooks/

echo "Proceso finalizado"