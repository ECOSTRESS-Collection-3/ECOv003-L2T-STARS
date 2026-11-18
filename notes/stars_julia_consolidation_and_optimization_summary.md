# STARS Data Fusion Julia Consolidation & Optimization Summary

## Overview

To streamline the `ECOv003-L2T-STARS` pipeline, reduce worker initialization overhead, and eliminate heavy unused dependencies, the core distributed Kalman filter fusion routines from `STARSDataFusion.jl` were pruned, optimized, and consolidated directly into `ECOv003_L2T_STARS/process_ECOSTRESS_data_fusion_distributed_bias.jl`.

Across four iterative engineering and verification rounds on the `test_bundle` benchmark (`11SPS` MGRS tile, 8 Julia distributed workers, 2026-10-03 to 2026-10-10), end-to-end execution time across both `NDVI` (`490m` $\rightarrow$ `70m`) and `albedo` (`980m` $\rightarrow$ `70m`) decreased by **33.5%** (from **3m 08s** down to **2m 05s**) while maintaining **100.00% numerical parity** (`~1e-9` RMSE, `NaN Diff = 0`, Pearson $r = 1.000000$) against the baseline reference outputs.

---

## Engineering & Optimization Process

### 1. Dependency Pruning & Worker Startup Optimization (`-68.7%` worker startup time)
* **Bottleneck:** Importing `STARSDataFusion` on every distributed worker via `@everywhere using STARSDataFusion` loaded heavy transitive dependencies unused in the ECOSTRESS pipeline—including `Plots` (`GR_jll`, `Cairo`, `FFMPEG`), `GeoDataFrames` (which parsed the 25 MB `sentinel2.geojson` file on every worker process), `GaussianRandomFields`, `HLS.jl`, `VNP43.jl`, and `VIIRS.jl`.
* **Solution:**
  * Removed `STARSDataFusion` from `ECOv003_L2T_STARS/Project.toml` and replaced it with minimal direct dependencies (`Sobol`, `SparseArrays`).
  * Inlined only the required state-space Kalman filter, covariance, and spatial indexing functions inside an `@everywhere begin ... end` block.
  * Replaced static `sentinel2.geojson` tile lookup with `sentinel_tile_dims_from_template()`, deriving exact UTM `X`/`Y` `Projected` grid dimensions and CRS metadata directly from the already-available downsampled input GeoTIFFs.

### 2. In-Place Matrix Operations & Buffer Reuse (`-23.5%` Kalman fusion time)
* **Bottleneck:** Inside `coarse_fine_fusion_cbias_dict` and `kalman_filter!`, heap allocations occurred on every timestep across 50,176 (`NDVI`) and 12,544 (`albedo`) spatial windows—specifically from copying the full state covariance matrix (`Qf .= Q`) when `state_in_cov == false` and constructing `Diagonal(err_vars)` matrices during innovation covariance updates ($S = H_t P_{\text{pred}} H_t^\top + R$).
* **Solution:**
  * Aliased `Qf` directly to `Q` when `state_in_cov == false`, eliminating redundant $n \times n$ matrix copies per timestep.
  * Added observation error variances `err_vars` directly to the diagonal of $S$ in an `@inbounds` loop rather than allocating `Diagonal(err_vars)`.
  * Replaced `Distances.pairwise` calls with allocation-light Euclidean distance and centroid overlap kernels (`_pairwise_col_euclidean`, `unif_weighted_obs_operator_centroid`).

### 3. Single-Pass Covariance Estimation (`-83.4%` variance estimation time)
* **Bottleneck:** `fast_var_est` previously relied on `mapslices` over 3D rasters with `NaN` filtering per slice.
* **Solution:** Replaced `mapslices` with an `@inbounds` column-major loop over the raw array using a single reusable workspace vector `diffs`, cutting covariance estimation time from `~2.35s` down to `0.39s` per product.

### 4. Numerical Parity Alignment (`RMSE ~ 1e-9`)
Iterative verification against `test_bundle/reference_outputs` identified and resolved three subtle numerical discrepancies during the port:
1. **Quasi-Random Background Sampling (`SobolSeq`):** Replacing `Sobol.jl`'s Joe & Kuo base-2 direction numbers (`SobolSeq`) with a Halton base-2/3 sequence in Round 2 altered the 100 background Basic Areal Unit (BAU) coordinates per window, introducing a `4.73e-3` RMSE shift. Restoring `SobolSeq` eliminated this sampling variance.
2. **Process Uncertainty Propagation on Empty Windows:** Skipping Kalman time-stepping on all-`NaN` spatial windows in Rounds 2–3 prevented the state covariance from propagating process noise ($P_{\text{pred}} = F P F^\top + Q$) across the 4-day fusion window, causing a `+4.6e-3` bias in posterior uncertainty (`UQ`). Dispatching all windows through full time-stepping restored exact uncertainty propagation.
3. **Matérn 3/2 Range Parameterization in `compute_n_eff`:** `GaussianRandomFields.Matern(range, 1.5)` parameterizes the Matérn 3/2 correlation as $(1 + d/\lambda)\exp(-d/\lambda)$ without the $\sqrt{3}$ scaling factor. Removing $\sqrt{3}$ in `compute_n_eff` (`s = dd ./ range`) restored the exact effective sample size ($n_{\text{eff}} \approx 2.0026$ vs. $3.6321$) and eliminated the `1.81x` spatial variance inflation.

---

## Iterative Performance Benchmarks

All benchmarks were executed on macOS (Apple Silicon) with 8 distributed Julia workers (`--threads 1`) on tile `11SPS`:
* **NDVI:** `490m` coarse $\rightarrow$ `70m` fine (`224 x 224` = `50,176` spatial windows; `1568 x 1568` = `2,458,624` output pixels)
* **Albedo:** `980m` coarse $\rightarrow$ `70m` fine (`112 x 112` = `12,544` spatial windows; `1568 x 1568` = `2,458,624` output pixels)

| Pipeline Stage | Round 1: Baseline + I/O Cache (`STARSDataFusion.jl`) | Round 2: Pruned Inline + Halton + Skip Empty | Round 3: Pruned Inline + `SobolSeq` + Skip Empty | Round 4: Pruned Inline + `SobolSeq` + Full Propagation (`s = dd/range`) | Net Change (R1 $\rightarrow$ R4) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Worker Startup (NDVI / Albedo)** | `13.39s` / `13.29s` | `4.64s` / `3.73s` | `4.52s` / `4.44s` | **`3.95s` / `4.41s`** | **-68.7%** (`-18.32s`) |
| **Inputs & Preprocessing** | `2.75s` / `2.75s` | `2.78s` / `2.73s` | `2.76s` / `2.76s` | **`2.88s` / `2.83s`** | +3.8% (`+0.21s`) |
| **Spatial Variance Est (`cov_est`)** | `2.34s` / `2.36s` | `0.45s` / `0.47s` | `0.45s` / `0.47s` | **`0.39s` / `0.39s`** | **-83.4%** (`-3.92s`) |
| **Kalman Fusion (`pmap`)** | `67.60s` / `59.51s` | `52.74s` / `44.17s` | `53.82s` / `43.81s` | **`53.51s` / `43.66s`** | **-23.5%** (`-29.94s`) |
| **Worker Teardown (`rmprocs`)** | `0.24s` / `0.27s` | `0.26s` / `0.28s` | `0.25s` / `0.25s` | **`0.24s` / `0.24s`** | -5.9% (`-0.03s`) |
| **GeoTIFF Writing** | `1.04s` / `1.11s` | `1.02s` / `1.08s` | `1.04s` / `1.08s` | **`1.13s` / `1.08s`** | +2.8% (`+0.06s`) |
| **Product Total (NDVI / Albedo)** | `88.02s` / `79.95s` | `62.61s` / `53.33s` | `63.56s` / `53.57s` | **`62.90s` / `53.30s`** | **-30.8%** (`-51.77s`) |
| **End-to-End Python Wall Time** | **`3m 08s` (`188s`)** | **`2m 06s` (`126s`)** | **`2m 06s` (`126s`)** | **`2m 05s` (`125s`)** | **-33.5%** (`-63s`) |

---

## Numerical Accuracy Progression Across Rounds

Comparison of generated outputs against `test_bundle/reference_outputs`:

| Metric (NDVI / Albedo Mean) | Round 1 | Round 2 | Round 3 | Round 4 (Final) |
| :--- | :---: | :---: | :---: | :---: |
| **Mean RMSE** | `1.89e-09` / `9.19e-10` | `4.73e-03` / `1.52e-03` | `1.72e-03` / `1.18e-03` | **`1.89e-09` / `9.19e-10`** |
| **UQ RMSE** | `8.27e-10` / `2.91e-10` | `8.69e-03` / `4.60e-03` | `8.62e-03` / `4.53e-03` | **`8.27e-10` / `2.91e-10`** |
| **Pixels $\le 10^{-5}$** | `100.00%` / `100.00%` | `3.32%` / `2.28%` | `4.70%` / `3.21%` | **`100.00%` / `100.00%`** |
| **NaN Diff / Flag Exact %** | `0` / `100.00%` | `0` / `100.00%` | `0` / `100.00%` | **`0` / `100.00%`** |

### Final Round 4 Layer-by-Layer Verification Table

| Output Raster | Pixels | NaN Diff | Exact % | $\le 10^{-5}$ % | Bias | MAE | RMSE | Max \|Diff\| | Pearson $r$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `STARS_NDVI_2026-10-10_11SPS_70m.tif` | 2,458,624 | 0 | 99.03% | 100.00% | `+1.0270e-12` | `1.2699e-10` | `1.8925e-09` | `5.9605e-08` | `1.000000` |
| `STARS_NDVI.UQ_2026-10-10_11SPS_70m.tif` | 2,458,624 | 0 | 87.31% | 100.00% | `+9.7304e-15` | `1.6876e-10` | `8.2671e-10` | `1.4901e-08` | `1.000000` |
| `STARS_NDVI.flag_2026-10-10_11SPS_70m.tif` | 2,458,624 | 0 | 100.00% | 100.00% | `+0.0000e+00` | `0.0000e+00` | `0.0000e+00` | `0.0000e+00` | `1.000000` |
| `STARS_NDVI.bias_2026-10-10_11SPS_70m.tif` | 50,176 | 0 | 95.63% | 100.00% | `+3.5969e-13` | `1.1746e-11` | `1.3226e-10` | `1.4901e-08` | `1.000000` |
| `STARS_NDVI.bias.UQ_2026-10-10_11SPS_70m.tif` | 50,176 | 0 | 95.43% | 100.00% | `+9.5162e-17` | `9.4777e-15` | `4.5736e-14` | `4.5475e-13` | `1.000000` |
| `STARS_albedo_2026-10-10_11SPS_70m.tif` | 2,458,624 | 0 | 99.35% | 100.00% | `+3.1735e-13` | `6.0711e-11` | `9.1891e-10` | `2.9802e-08` | `1.000000` |
| `STARS_albedo.UQ_2026-10-10_11SPS_70m.tif` | 2,458,624 | 0 | 87.95% | 100.00% | `+7.0826e-13` | `8.2761e-11` | `2.9076e-10` | `7.4506e-09` | `1.000000` |
| `STARS_albedo.flag_2026-10-10_11SPS_70m.tif` | 2,458,624 | 0 | 100.00% | 100.00% | `+0.0000e+00` | `0.0000e+00` | `0.0000e+00` | `0.0000e+00` | `1.000000` |
| `STARS_albedo.bias_2026-10-10_11SPS_70m.tif` | 12,544 | 0 | 99.27% | 100.00% | `+1.4330e-13` | `1.6236e-11` | `2.6997e-10` | `7.4506e-09` | `1.000000` |
| `STARS_albedo.bias.UQ_2026-10-10_11SPS_70m.tif` | 12,544 | 0 | 95.42% | 100.00% | `+4.0784e-16` | `1.0160e-14` | `4.7902e-14` | `4.5475e-13` | `1.000000` |