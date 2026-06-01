#!/bin/bash

source /home/prometheus/miniconda3/etc/profile.d/conda.sh

conda activate showcast

cd /home/prometheus/workspace/scripts/satellite/hovmoller

echo "========================================"
echo "$(date -u) UTC"
echo "========================================"

python hovmoller_goes19_ch14_1.py

python hovmoller_goes19_ch14_2.py

echo "Proceso finalizado"