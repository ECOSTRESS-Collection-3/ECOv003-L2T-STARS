# `ECOv003-L2T-STARS` Comprehensive Development History, Architecture & Operations Record (`v1.0.1` – `v1.19.0`)

**Repository:** `ECOSTRESS-Collection-3/ECOv003-L2T-STARS`  
**Release Span:** `v1.0.1` (November 12, 2024) – `v1.19.0` (November 23, 2026)  
**Primary Tracking Issues:** [GH #90](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/90), [GH #94](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/94), [GH #95](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/95), [GH #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96)  
**Reference I&T DAG Run:** `EcostressDAG_Col3.46000.0802.20261116T001911117` (807 logs scanned; 51 unique signatures)

---

## 1. Operational Context & Release Timeline (`v1.0.1` – `v1.19.0`)

`ECOv003-L2T-STARS` produces daily 70 m gap-filled Normalized Difference Vegetation Index (`NDVI`) and broadband albedo (`albedo`) rasters with 1-sigma uncertainty (`*-UQ`), sensor bias (`*-bias`, `*-bias-UQ`), and 7-day HLS availability masks (`*-flag`) for every daytime ECOSTRESS `L2T_LSTE` tile overpass within the NASA JPL ECOSTRESS Science Data System (`ecostress-level-2-3-4`, `artifactory.jpl.nasa.gov:16001/gov/nasa/jpl/ecostress/sds/pge-v3/eco-level-2-3-4-application`).

### 1.1 Cross-Stack Operational Epochs

| Operational Epoch | Dates | `ECOv003-L2T-STARS` | Data Fusion Engine | Coarse VIIRS Source | Sister PGE (`ECOv003-L3T-L4T-JET`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Epoch 1: Initial C3 Port & Modularization** | Nov 2024 – Sep 2025 | `v1.0.1` – `v1.10.0` | Julia (`STARSDataFusion.jl`) | Suomi NPP (`VNP43NRT` / `VNP43IA4` / `VNP43MA3`) | `v1.0.1` – `v1.9.0` |
| **Epoch 1: C3 Forward-Processing Baseline** | Dec 2025 – Nov 2, 2026 | `v1.11.0` – `v1.12.1` | Julia `1.11.6` (isolated `GDAL_jll`) | Suomi NPP (`VNP43NRT`) | `v1.13.0` – `v1.18.0` |
| **Epoch 2: JPSS Cutover & Dependency Alignment** | Nov 11 – Nov 17, 2026 | `v1.13.0` – `v1.17.0` | Julia `1.11.6` | JPSS Multi-Mission (`VCD43NRT`) | `v1.19.0` – `v1.20.3` |
| **Epoch 2: Rust Fusion Core & I&T Hardening** | Nov 18 – Nov 23, 2026 | `v1.18.0` – `v1.19.0` | **Rust (`_stars_rust` default)** / Julia fallback | JPSS Multi-Mission (`VCD43NRT` + staging isolation) | `v1.21.0` – `v1.22.1` |

### 1.2 Chronological Release History

* **Phase 1 — Collection 2 Port & Hybrid Python/Julia Prototype (`v1.0.1` – `v1.1.0`, Nov 2024 – Jun 2025):**
  * **`v1.0.1` (2024-11-12):** Duplicated from `ECOv002-L2T-STARS` as a monolithic 1,777-line `L2T_STARS.py` module bundling inline `BRDF/`, `LPDAAC/`, `VIIRS/`, `VNP43NRT/`, `daterange/`, `timer/`, and `exit_codes.py`.
  * **`v1.1.0` (2025-06-24):** Adopted `ECOv003-exit-codes` and `ECOv003-granules`; integrated `STARSDataFusion.jl` (`process_ECOSTRESS_data_fusion_distributed_bias.jl`) with bias, bias-UQ, and flag layers plus `threads=1` memory controls; decomposed `ECOv003_L2T_STARS.py` into single-responsibility modules; added the `ECOv003-DL` Collection 3 Downloader PGE (`ECOv003_DL.py`, `ECOv003_DL.xml`).
* **Phase 2 — Run-Config Standardization, Credentials & Upstream Extraction (`v1.2.0` – `v1.10.0`, Jul – Sep 2025):**
  * **`v1.2.0` – `v1.3.0`:** Added `--overwrite`, standardized XML parsing on `StaticAncillaryFileGroup`, replaced `pycksum` with pure-Python POSIX `cksum` for Python 3.12+, and added Earthdata `.netrc` / environment login (`login.py`).
  * **`v1.4.0` – `v1.6.1`:** Backported `DOWNSAMPLED_products` directory structure, upgraded to `harmonized-landsat-sentinel>=2.0.0` (`HLS2Connection`), standardized layer names to `NDVI-bias-UQ` / `albedo-bias-UQ`, and fixed `ECOv003-DL` entry points.
  * **`v1.7.0` – `v1.10.0`:** Stripped Conda `GDAL_DATA` / `GDAL_DRIVER_PATH` from Julia subprocesses, switched input loading to `ECOv003_granules.L2TLSTE`, adopted `L2TSTARS.generate_granule_name(...)`, wrote `StandardMetadata.BuildID`, and added same-day prior copying (`copy_prior_to_posterior`).
* **Phase 3 — Collection 3 Forward-Processing Baseline (`v1.11.0` – `v1.12.1`, Dec 2025 – Oct 2026):**
  * **`v1.11.0` (2025-12-02):** Hardened `os.environ.copy()` isolation for Julia subprocesses and implemented direct `ArchGDAL.create` GeoTIFF writing (`safe_write_geotiff`) to eliminate `RastersArchGDALExt` driver failures across the ~11-month Suomi NPP baseline.
  * **`v1.12.0` – `v1.12.1` (Oct 2026):** Added dual `ECOv003` / `ECOv002` `L2T_LSTE` support, populated `StandardMetadata.InputPointer`, and added `julia_environment.py`, `julia_smoke_test.jl`, and `ECOv003-L2T-STARS-install-julia` pinned to Julia `1.11.6`.
* **Phase 4 — November 2, 2026 Suomi NPP Decommissioning, JPSS Cutover & Rust Core (`v1.13.0` – `v1.19.0`, Nov 2026):**
  * **`v1.13.0` (2026-11-11):** Migrated coarse VIIRS inputs from decommissioned Suomi NPP `VNP43NRT` to multi-mission JPSS `VCD43NRT` (`mission_priority = ("SNPP", "JPSS1", "JPSS2")`, `fallback_mode=True`) and removed ~3,500 lines of legacy inline VIIRS/BRDF/LPDAAC modules.
  * **`v1.14.0` – `v1.16.0` (Nov 11–12, 2026):** Synchronized dependency pins (`GEOS5FP~=2.24.0`, `numpy~=2.5.4`, `pandas~=3.1.1`, `rasterio~=1.5.2`) and Python `3.12` compatibility with `ECOv003-L3T-L4T-JET`, introduced `smoke_test.py`, and added automatic `juliaup` bootstrapping (`install_julia.py`).
  * **`v1.17.0` (2026-11-17):** Implemented coarse outage resilience and deterministic exit-code mapping (`VIIRS_GIVEUP_DAYS = 4`, exit codes `14`–`17`) plus offline verification (`test_bundle/` and `test_julia_output.py`).
  * **`v1.18.0` (2026-11-18):** Replaced the Julia fusion hot loop with a compiled Rust/PyO3 extension (`_stars_rust`, `FUSION_BACKEND = "rust"` default), isolated `VCD43NRT_staging_directory` to prevent multi-worker collisions, and downgraded `LandFilter` skips from `[ERROR]` to `[INFO]`.
  * **`v1.19.0` (2026-11-23):** Isolated intermediate posterior directories per `granule_ID` (`#94`), captured and logged Julia `stdout`/`stderr` on non-zero exit (`#95`), recorded `StandardMetadata.PGEVersion`, consolidated CLI entry points (`build_parser`, `main`), aligned `Dockerfile` with `mambaorg/micromamba:ubuntu24.04` (`libgdal-netcdf`, `libgdal-hdf5`), and expanded build-time GDAL/contract smoke tests.

---

## 2. Exception Handling Architecture & Locked Exit-Code Contract

### 2.1 Architectural Boundary (`ECOv003-L2T-STARS` $\rightarrow$ `VCD43NRT`)
* **Mission-Agnostic Provider (`VCD43NRT >= 1.5.0`):** Centralizes `VCD43NRTError`, `CMRServerUnreachable`, `DownloadFailed`, `AuxiliaryDownloadFailed`, `VIIRSUnavailableError`, and `BRDFRetrievalFailed` in `VCD43NRT/exceptions.py` with zero ECOSTRESS coupling.
* **Sole Policy Adapter (`ECOv003-L2T-STARS`):** Translates `VCD43NRT` exceptions and processing outcomes into the locked `ECOv003-exit-codes` (`0`–`18`) contract. `retrieve_STARS_sources()` defers `VIIRSUnavailableError` during `prefetch_VNP09GA(...)` so `generate_STARS_inputs()` consistently evaluates window-level `VIIRS_GIVEUP_DAYS` (`4` days) policy, while propagating `CMRServerUnreachable` (`14`) and `DownloadFailed` (`16`) immediately.

### 2.2 Locked Exit-Code Translation Matrix

*(Note: `AuxiliaryDownloadFailed` does not exist in `ECOv003_exit_codes`; `DownloadFailed` is the canonical exception for exit code `16`.)*

| Failure / Exception | Prefetch (`retrieve_STARS_sources.py`) | Per-Date Loop (`generate_STARS_inputs.py`) | Post-Window Check (`generate_STARS_inputs.py`) | Top-Level PGE (`L2T_STARS.py`) | Exit Code |
| :--- | :--- | :--- | :--- | :--- | :---: |
| `VCD43NRT.exceptions.CMRServerUnreachable` | Propagates immediately | **Re-raise immediately** | — | `AUXILIARY_SERVER_UNREACHABLE` | **`14`** |
| `VCD43NRT.exceptions.VIIRSUnavailableError` | **Catch, warn, defer to window check** | Catch, warn, record in `missing_coarse_dates` | Missing $\le$ `VIIRS_GIVEUP_DAYS` (4d) $\rightarrow$ `AuxiliaryLatency` (`15`); else `available_count == 0` $\rightarrow$ `DownloadFailed` (`16`) | `AUXILIARY_LATENCY` / `DOWNLOAD_FAILED` | **`15`** or **`16`** |
| `VCD43NRT.exceptions.DownloadFailed` *(incl. `AuxiliaryDownloadFailed`)* / `HLSDownloadFailed` | Propagates immediately | Catch, log, record in `missing_coarse_dates` | Missing $\le$ `VIIRS_GIVEUP_DAYS` $\rightarrow$ `AuxiliaryLatency` (`15`); else `available_count == 0` $\rightarrow$ `DownloadFailed` (`16`) | `DOWNLOAD_FAILED` / `AUXILIARY_LATENCY` | **`16`** *(or **`15`**)* |
| `VCD43NRT.exceptions.BRDFRetrievalFailed` | — | Catch, warn, record in `missing_coarse_dates` | Missing $\le$ `VIIRS_GIVEUP_DAYS` $\rightarrow$ `AuxiliaryLatency` (`15`); else `available_count == 0` $\rightarrow$ `DownloadFailed` (`16`) | `DOWNLOAD_FAILED` / `AUXILIARY_LATENCY` | **`16`** *(or **`15`**)* |
| Subprocess exits non-zero (`result.returncode != 0`) | — | — | — | Logs `stderr` tail, raises `RuntimeError` $\rightarrow$ `UNCLASSIFIED_FAILURE_EXIT_CODE` | **`1`** |
| Missing posterior GeoTIFF before `Raster.open()` | — | — | — | Raises `BlankOutput` (`process_STARS_product.py`) | **`17`** |

---

## 3. Data Fusion Performance Engineering: Julia Consolidation to Pure Rust

To eliminate external Julia runtime dependencies, remove multi-process worker startup overhead, and accelerate 70 m product generation, the Kalman filter and spatial Gaussian process fusion engine was first consolidated in Julia (Rounds 1–4) and then ported to a compiled Rust extension (`ECOv003_L2T_STARS._stars_rust`) built with `PyO3` and `maturin` (Cycles 1–4).

### 3.1 Engineering Progression Summary
* **Julia Rounds 1–4 (`188.00s` $\rightarrow$ `125.00s`, `-33.5%`):**
  * Removed `STARSDataFusion.jl` (`Plots`, `Cairo`, `FFMPEG`, and 25 MB `sentinel2.geojson` parsing per worker), inlined minimal Kalman/spatial kernels, derived tile grids directly from input GeoTIFFs (`sentinel_tile_dims_from_template()`), aliased `Qf` to `Q` when `state_in_cov == false`, and replaced `mapslices` in `fast_var_est` with a single-pass `@inbounds` column-major loop (`-83.4%` `cov_est` time).
  * Restored `Sobol.jl`'s Joe & Kuo base-2 `SobolSeq`, full 4-day process noise propagation ($P_{\text{pred}} = F P F^\top + Q$) across all spatial windows (`50,176` NDVI / `12,544` albedo), and exact Matérn 3/2 range scaling ($s = d / \lambda$, $n_{\text{eff}} \approx 2.0026$) to achieve exact bitwise parity (`1.89e-09` NDVI Mean RMSE, `9.19e-10` Albedo Mean RMSE).
* **Rust Cycles 1–4 (`316.25s` $\rightarrow$ `112.12s`, `-40.4%` vs. Julia R1 and `-10.3%` vs. Julia R4):**
  * **Crate & Bindings (`src/lib.rs`, `src/sobol.rs`, `src/spatial.rs`, `src/covariance.rs`, `src/kalman.rs`):** Built with `pyo3 0.23`, `numpy 0.23`, `ndarray 0.16`, `rayon 1.10`, `faer 0.20`, and `indicatif 0.17` (`opt-level = 3`, `lto = "fat"`, `codegen-units = 1`, `abi3-py311`), eliminating worker startup (`0.000s`) and reducing `cov_est` to `< 0.01s`.
  * **Linear Algebra & Resampling:** Replaced scalar triple loops with `faer` SIMD `matmul` and lower-triangular Cholesky decomposition with `partial_piv_lu` fallback (`3.0x` speedup), and aligned covariance resampling with GDAL `rasterio.warp.reproject(..., resampling=Resampling.cubic_spline)`.
  * **Numerical Bitwise Parity:** Matched exact process noise `Q[1:nf, 1:nf] = cvs * Qs * cvs`, diagonal bias process noise (`1e-6 * I`), posterior variance output `P_cur[(nf, nf)]` for `bias.UQ`, and `Sobol.jl` Dimension 2 direction numbers (`s = 2, a = 0, m = [1, 3]`) with `.round_ties_even()`.

### 3.2 Master Benchmark & Parity Progression (`11SPS` Tile, 8 Workers)

| Round / Cycle | Backend & Key Engineering Changes | NDVI Time | Albedo Time | Total Wall Time | NDVI Mean RMSE | Albedo Mean RMSE | Pixels $\le 10^{-5}$ |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Julia Round 1** | Baseline `STARSDataFusion.jl` + I/O cache (`26.68s` worker startup) | `88.02s` | `79.95s` | `188.00s` | `1.89e-09` | `9.19e-10` | `100.00%` |
| **Julia Round 2** | Pruned inline Julia + Halton sampling + skip empty windows | `62.61s` | `53.33s` | `126.00s` | `4.73e-03` | `1.52e-03` | `3.32%` / `2.28%` |
| **Julia Round 3** | Pruned inline Julia + `SobolSeq` + skip empty windows | `63.56s` | `53.57s` | `126.00s` | `1.72e-03` | `1.18e-03` | `4.70%` / `3.21%` |
| **Julia Round 4** | Pruned inline Julia + `SobolSeq` + full propagation + `s = dd/range` | `62.90s` | `53.30s` | `125.00s` | `1.89e-09` | `9.19e-10` | `100.00%` |
| **Rust Cycle 1** | Initial pure-Rust port (scalar loops, `scipy.ndimage.zoom`) | `~165s` | `~151s` | `316.25s` | `~1.2e-02` | `~4.8e-03` | `~2.5%` |
| **Rust Cycle 2** | `faer` SIMD `matmul` + GDAL `cubic_spline` + `indicatif` progress | `55.44s` | `48.74s` | `104.99s` | `3.70e-02` | `1.17e-02` | `0.00%–2.21%` |
| **Rust Cycle 3** | Exact `Q` (`cvs * Qs * cvs`), uniform `F*P*F' + Q`, `bias.UQ` variance | `53.41s` | `48.71s` | `102.91s` | `4.24e-03` | `9.78e-04` | `3.93%–100%` |
| **Rust Cycle 4** | **Exact `Sobol.jl` (`s=2, a=0, m=[1, 3]`) + `find_nearest_ind`** | **`59.02s`** | **`52.15s`** | **`112.12s`** | **`1.89e-09`** | **`9.19e-10`** | **`100.00%`** |

### 3.3 Final Rust Layer-by-Layer Parity Verification (`test_bundle/reference_outputs`)

| Output Raster | Pixels | NaN Diff | Exact % | $\le 10^{-5}$ % | Bias | MAE | RMSE | Max \|Diff\| | Pearson $r$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `STARS_NDVI_2026-10-10_11SPS_70m.tif` | 2,458,624 | 0 | 99.03% | 100.00% | `+1.0270e-12` | `1.2699e-10` | `1.8925e-09` | `5.9605e-08` | `1.000000` |
| `STARS_NDVI.UQ_2026-10-10_11SPS_70m.tif` | 2,458,624 | 0 | 87.31% | 100.00% | `+9.7304e-15` | `1.6876e-10` | `8.2671e-10` | `1.4901e-08` | `1.000000` |
| `STARS_NDVI.flag_2026-10-10_11SPS_70m.tif` | 2,458,624 | 0 | 100.00% | 100.00% | `+0.0000e+00` | `0.0000e+00` | `0.0000e+00` | `0.0000e+00` | `1.000000` |
| `STARS_NDVI.bias_2026-10-10_11SPS_70m.tif` | 50,176 | 0 | 95.63% | 100.00% | `+3.5969e-13` | `1.1746e-11` | `1.3226e-10` | `1.4901e-08` | `1.000000` |
| `STARS_NDVI.bias.UQ_2026-10-10_11SPS_70m.tif` | 50,176 | 0 | 95.43% | 100.00% | `+9.5162e-17` | `9.4777e-15` | `4.5736e-14` | `4.5475e-13` | `1.000000` |
| `STARS_albedo_2026-10-10_11SPS_70m.tif` | 2,458,624 | 0 | 99.35% | 100.00% | `+3.1735e-13` | `6.0711e-11` | `9.1891e-10` | `2.9802e-08` | `1.000000` |
| `STARS_albedo.UQ_2026-10-10_11SPS_70m.tif` | 2,458,624 | 0 | 87.95% | 100.00% | `+7.0807e-13` | `8.2761e-11` | `2.9076e-10` | `7.4506e-09` | `1.000000` |
| `STARS_albedo.flag_2026-10-10_11SPS_70m.tif` | 2,458,624 | 0 | 100.00% | 100.00% | `+0.0000e+00` | `0.0000e+00` | `0.0000e+00` | `0.0000e+00` | `1.000000` |
| `STARS_albedo.bias_2026-10-10_11SPS_70m.tif` | 12,544 | 0 | 99.27% | 100.00% | `+1.4330e-13` | `1.6236e-11` | `2.6997e-10` | `7.4506e-09` | `1.000000` |
| `STARS_albedo.bias.UQ_2026-10-10_11SPS_70m.tif` | 12,544 | 0 | 95.42% | 100.00% | `+4.0784e-16` | `1.0160e-14` | `4.7902e-14` | `4.5475e-13` | `1.000000` |

---

## 4. I&T DAG Log Triage & Operational Rollout (`EcostressDAG_Col3.46000.0802.20261116T001911117`)

Triage of 807 DAG log files (51 unique issue signatures, 755 errors, 8,436 warnings) mapped all failures to 6 root causes:

| Tracking / Log ID | Severity | Component / Signature | Status & Resolution |
| :--- | :--- | :--- | :--- |
| **[GH #94](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/94)** (Log `#12`) | `ERROR` (Bug) | `OSError: raster file not found` on shared `L2T_STARS_MODEL/<TILE>/<DATE>/` during concurrent `REMOVE_POSTERIOR = True` cleanup (2 logs, tile `31UDT`) | **Fixed in `v1.19.0`** — Scoped intermediate posteriors under `model_directory/<tile>/<date_UTC>/<granule_ID>` (`process_STARS_product.py`). |
| **[GH #95](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/95)** (Log `#3`) | `ERROR` (Logging) | `RuntimeError: Julia data fusion failed for NDVI at tile <TILE> with exit code 1` without stderr traceback in PGE log (36 logs) | **Fixed in `v1.18.0` / `v1.19.0`** — Rust default backend (`FUSION_BACKEND = "rust"`) + captured/logged Julia `stdout`/`stderr` tail on failure. |
| **[GH #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96)** (Logs `#11, #19, #22, #24, #30, #31`) | `ERROR` / `WARNING` | `VCD43NRT` multi-worker collisions (`NBAR_I1.temp.tif` `FileNotFoundError`, 2 errors; stale directory warnings, 576 warnings) | **Fixed in `v1.18.0`** (`VCD43NRT_staging_directory` + `fallback_mode=True`); awaiting I&T container deploy. |
| **[GH #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96)** (Log `#2`) | `INFO` | `Sentinel tile <TILE> is not on land. Skipping processing.` logged at `[ERROR]` in pre-`v1.18.0` builds (70 logs) | **Fixed in `v1.18.0`** (logged at `[INFO]`, exit code `11`); awaiting I&T container deploy. |
| **[GH #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96)** (Logs `#1, #5–#10, #13–#18, #27, #35–#51`) | `ERROR` / `WARNING` | `portal.nccs.nasa.gov` dropouts (`SSLEOFError`, `Errno 101`, `503`, `IncompleteRead`) leaving truncated `.nc4` files in `GEOS5FP_download/`, plus CMR `504 Gateway Time-out` | **Handled (Exit Codes `14`–`16`)** — **Ops Action:** Deploy `>=1.19.0` container, purge truncated `.nc4` files in `/runtime_ancillary/L2T_STARS_SOURCES/GEOS5FP_download/`, and re-drive failed tasks. |
| **[JET #88](https://github.com/ECOSTRESS-Collection-3/ECOv003-L3T-L4T-JET/issues/88)** (Logs `#4, #32–#34`) | Downstream | `JET3` deprecated `GEOS5FPConnection.wind_speed` / `Td_C` calls (`32TPS`, `32TPT`) and `.netrc` warnings | **Fixed in `JET3 v3.1.1` / `ECOv003-L3T-L4T-JET v1.22.1`**; awaiting container rebuild in `ecostress-level-2-3-4`. |

*(Note: Expected cloud-cover / cold-start warnings—`#20`, `#21`, `#23`, `#25`, `#26`, `#28`, `#29`, totaling 884 warnings—reflect normal orbital/cloud availability gaps and require no action.)*

### Remaining Operational Rollout Checklist ([GH #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96))
* [ ] Merge PR #97, tag `ECOv003-L2T-STARS v1.19.0`, and publish `abi3-py311` wheels.
* [ ] Rebuild `eco-level-2-3-4-application` with `ECOv003-L2T-STARS>=1.19.0` and `ECOv003-L3T-L4T-JET>=1.22.1`, verifying `ECOv003-L2T-STARS test`.
* [ ] Purge truncated/corrupted `.nc4` files under `/runtime_ancillary/L2T_STARS_SOURCES/GEOS5FP_download/` and re-drive failed DAG tasks from `EcostressDAG_Col3.46000.0802.20261116T001911117`[cite: 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16].