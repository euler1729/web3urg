#!/usr/bin/env bash
# Reproduce the full simulation study: data -> experiments -> figures.
set -euo pipefail
cd "$(dirname "$0")"
python3 generate_data.py
# sensitivity first: its sweeps reuse experiment functions that overwrite
# the baseline result CSVs, which run_experiments.py then regenerates
python3 run_sensitivity.py
python3 run_experiments.py
python3 make_figures.py
