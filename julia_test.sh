#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root so all paths are relative to it
cd "$(dirname "${BASH_SOURCE[0]}")"

mkdir -p test_outputs

# Coarse (VIIRS) and fine (HLS) downsampled inputs for the fusion; override as needed
DOWNSAMPLED_DIR="${DOWNSAMPLED_DIR:-$HOME/data/ECOv003_testing/L2T_STARS_SOURCES/VCD43NRT_DOWNSAMPLED_products}"

# Run the package's Julia data fusion code on the priors in test_inputs.
# Experimental posteriors are written to test_outputs; the reference
# posteriors are in expected_outputs. Julia 1.13 matches the Manifest.toml.
julia +1.13 --project=ECOv003_L2T_STARS \
  --threads 1 \
  ECOv003_L2T_STARS/process_ECOSTRESS_data_fusion_distributed_bias.jl \
  8 \
  11SPS \
  980 \
  70 \
  2026-10-03 \
  2026-10-10 \
  2026-10-07 \
  2026-10-10 \
  "$DOWNSAMPLED_DIR" \
  albedo \
  test_outputs/STARS_albedo_2026-10-10_11SPS_70m.tif \
  test_outputs/STARS_albedo.UQ_2026-10-10_11SPS_70m.tif \
  test_outputs/STARS_albedo.flag_2026-10-10_11SPS_70m.tif \
  test_outputs/STARS_albedo.bias_2026-10-10_11SPS_70m.tif \
  test_outputs/STARS_albedo.bias.UQ_2026-10-10_11SPS_70m.tif \
  test_inputs/STARS_albedo_2026-10-06_11SPS_70m.tif \
  test_inputs/STARS_albedo.UQ_2026-10-06_11SPS_70m.tif \
  test_inputs/STARS_albedo.bias_2026-10-06_11SPS_70m.tif \
  test_inputs/STARS_albedo.bias.UQ_2026-10-06_11SPS_70m.tif
