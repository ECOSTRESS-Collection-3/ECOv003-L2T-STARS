# Development Plan: Migrating STARS Data Fusion to a Pure Rust (`PyO3` / `maturin`) Extension

## 1. Executive Summary

Following the consolidation and pruning of the Julia data fusion script (`ECOv003_L2T_STARS/process_ECOSTRESS_data_fusion_distributed_bias.jl`), the entire STARS Kalman filter and spatial Gaussian process algorithm is self-contained (~520 lines of pure numerical logic with zero external geospatial library dependencies)[cite: 8].

This plan tracks the migration of the data fusion core into a compiled Rust extension (`ECOv003_L2T_STARS._stars_rust`) built with `PyO3` and `maturin`[cite: 8].

### Key Goals
1. **Zero Julia Runtime Dependency for End Users:** Standard `pip install ECOv003-L2T-STARS` installs prebuilt platform wheels (`manylinux`, `macos-arm64`, `windows`) with compiled Rust binaries—no Julia installation, `Manifest.toml` instantiation, or GDAL C-library isolation required[cite: 8].
2. **Eliminate Multi-Process Startup & Serialization Overhead:** Replace `Distributed.addprocs` worker spawning (`~4.5s` per product) and `pmap` IPC serialization with in-process `rayon` thread-pool parallelism over shared read-only NumPy memory views[cite: 8].
3. **Preserve Optional Legacy Julia Path:** Retain `process_julia_data_fusion.py` and `process_ECOSTRESS_data_fusion_distributed_bias.jl` behind an opt-in `backend="julia"` flag for side-by-side regression benchmarking, without requiring Julia at package installation or import time[cite: 8].
4. **Bitwise Numerical Parity:** Validate all 10 output rasters (`NDVI` and `albedo` mean, `UQ`, `flag`, `bias`, and `bias.UQ`) against `test_bundle/reference_outputs/` to `RMSE <= 1e-7`, `NaN Diff = 0`, and Pearson $r \ge 0.999999$[cite: 8].

---

## 2. Engineering Progress & Iterative Milestones Completed

### Phase 1: Rust Crate Scaffolding, Build System & Unit Tests (Completed)
* [x] **Created Rust crate (`Cargo.toml`) & `maturin` build configuration (`pyproject.toml`):** Configured `_stars_rust` as `crate-type = ["cdylib", "rlib"]` with `pyo3 0.23`, `numpy 0.23`, `ndarray 0.16`, `rayon 1.10`, `faer 0.20`, and `indicatif 0.17`, plus `opt-level = 3`, `lto = "fat"`, and `codegen-units = 1` release optimizations.
* [x] **Resolved macOS / Conda `libpython` dynamic linking:** Enabled `extension-module` feature in `pyproject.toml` and verified via `otool -L` that `_stars_rust.cpython-312-darwin.so` links cleanly against system libraries without hardcoding a Conda `libpython` path.
* [x] **Implemented pure-Rust numerical modules & PyO3 bindings:**
  * `src/sobol.rs` — 2D Sobol sequence generator (`SobolSeq2D`) and `sobol_bau_ij` sub-grid sampler.
  * `src/spatial.rs` — Grid coordinate/index transforms (`find_nearest_ind`, `find_all_ij_ext`, `find_overlapping_ext`, `merge_extents`, `bbox_from_centroid`).
  * `src/covariance.rs` — Matérn 3/2 effective sample size (`compute_n_eff` with $s = d / \lambda$) and parallel temporal first-difference spatial variance estimator (`fast_var_est`).
  * `src/kalman.rs` — State-space Kalman filter and `rayon` parallel window solver (`run_scene_fusion`).
  * `src/lib.rs` & `ECOv003_L2T_STARS/_stars_rust.pyi` — Zero-copy NumPy bindings (`smoke_test`, `estimate_spatial_variance`, `fuse_stars_product`) and Python type stubs.
* [x] **Added smoke test (`tests/test_rust_smoke.py`) and updated `makefile` / `.gitignore`:** Automated `maturin develop --release` in `make install` and verified clean editable builds (`~7.8s` release compile).

### Phase 2: Full-Scene Fusion, Performance Optimization & Parity Alignment (In Progress)
* [x] **Implemented Python orchestration wrapper (`ECOv003_L2T_STARS/process_rust_data_fusion.py`) & offline verification harness (`test_rust_output.py`):**
  * Transposes `(row=y, col=x)` GeoTIFF bands into Julia/STARS `(x, y)` memory orientation and computes 7-day HLS availability flags (`100.00%` exact match across all `2,458,624` pixels).
  * Fixed GeoTIFF block-size alignment (`BLOCKYSIZE` / `BLOCKXSIZE` stripped from input profiles and `tiled=True` enabled only when dimensions $\ge 256 \times 256$).
  * Replaced `scipy.ndimage.zoom` with GDAL `Resampling.cubic_spline` coordinate reprojection (`rasterio.warp.reproject`) to align pixel centroids with Julia's `Rasters.resample(..., method=:cubicspline)`.
* [x] **Accelerated Kalman solver (`3.0x` speedup: `316.25s` $\rightarrow$ `102.91s` total):**
  * Replaced scalar triple-nested matrix loops with `faer 0.20` SIMD `matmul` microkernels and lower-triangular Cholesky (`cholesky(Side::Lower)`) with `partial_piv_lu` fallback.
  * Preallocated reusable matrix scratch buffers (`ht_buf`, `h_t_buf`, `hp_pt_buf`, `s_buf`, `rhs_buf`, `k_buf`, `hp_pred_buf`) outside the time loop to eliminate per-timestep heap allocations.
  * Added live `indicatif` atomic progress bars (`961.4 windows/s` for NDVI, `264.8 windows/s` for albedo) and structured stage timing telemetry (`inputs`, `cov_est`, `resample`, `pool_init`, `kalman_solve`, `assemble`, `write`, `total`).
* [x] **Resolved major Kalman filter numerical discrepancies:**
  * Fixed `SobolSeq2D` Dimension 2 direction numbers (`s = 2, a = 1, m = [1, 1]`) and `.round_ties_even()` to match `Sobol.jl`'s exact sequence (`[0.5, 0.5]`, `[0.75, 0.25]`, `[0.25, 0.75]`, `[0.375, 0.375]`, ...).
  * Removed erroneous `cov_wt` scaling on `Q[1:nf, 1:nf]` when `state_in_cov = false` (`Q[1:nf, 1:nf] = cvs * Qs * cvs`) and set bias process noise to diagonal `1e-6 * I`.
  * Applied uniform `x_pred = F * x_cur` and `P_pred = F * P_cur * F' + Q` prediction across all timesteps `t = 1..n_times`.
  * Aligned `bias.UQ` output to write posterior variance `P_cur[(nf, nf)]` directly (`RMSE = 2.35e-09` for NDVI, `1.36e-09` for albedo).
* [x] **Aligned `sobol_bau_ij` boundary rounding and dense-grid fallback (`src/sobol.rs`):** Updated `sobol_bau_ij` to use `find_nearest_ind` (`.round()`) with `1e-9` upper-extent offset (`inclusive = false`) and exhaustive `(i, j)` enumeration when `nsamp >= ni * nj`.
* [ ] **Rebuild & verify `src/sobol.rs` parity update on `test_rust_output.py`:** Confirm final `Mean` RMSE drops from `4.24e-03` (NDVI) / `9.78e-04` (albedo) into the `1e-7`–`1e-9` target band.
* [ ] **Investigate further SIMD / workspace optimizations in `src/kalman.rs` (optional):** Profile `p_pred` transition update and `rhs` transpose to push total runtime below `60s` (`< 30s` per product).

### Phase 3: Dual-Backend Integration & Multi-Platform CI/CD (Pending)
* [ ] **Wire `backend="rust"` (default) and `--backend rust|julia` CLI option** into `ECOv003_L2T_STARS/L2T_STARS.py`, `ECOv003_L2T_STARS/process_STARS_product.py`, and `ECOv003_L2T_STARS/main.py`[cite: 8].
* [ ] **Update `ECOv003_L2T_STARS/smoke_test.py`:** Test Python + `_stars_rust` by default (`ECOv003-L2T-STARS test`), keeping `test-julia` opt-in when Julia is present[cite: 8].
* [ ] **Add automated Rust parity & unit test suite (`tests/test_rust_data_fusion.py`):** Cover `sobol.rs`, `covariance.rs`, `kalman.rs`, and full-tile parity checks[cite: 8].
* [ ] **Update `.github/workflows/ci.yml` and `.github/workflows/python-publish.yml`:** Run `cargo test`, `maturin develop --release`, and `pytest` in CI, and build multi-platform wheels (`manylinux` x86_64/aarch64, macOS arm64/x86_64, Windows x64) via `PyO3/maturin-action`[cite: 8].
* [ ] **Update `Dockerfile`:** Default to standard `pip install .` without downloading the Julia tarball unless `--build-arg INCLUDE_JULIA=1` is passed[cite: 8].

---

## 3. Current Benchmark & Parity Status (`11SPS` Test Bundle, 8 Workers)

| Pipeline Metric | Round 4 Julia Baseline | Current Rust (`_stars_rust`) | Status |
| :--- | :---: | :---: | :--- |
| **Worker Startup Overhead** | `3.95s` / `4.41s` | **`0.000s` / `0.000s`** | Eliminated |
| **Spatial Variance Est (`cov_est`)** | `0.39s` / `0.39s` | **`0.00s` / `0.00s`** | ~100x faster |
| **NDVI Total Time (`490m -> 70m`)** | `62.90s` | **`53.41s`** | **-15.1% faster** |
| **Albedo Total Time (`980m -> 70m`)** | `53.30s` | **`48.71s`** | **-8.6% faster** |
| **End-to-End Verification Time** | `125.00s` (`2m 05s`) | **`102.91s`** (`1m 43s`) | **-17.7% faster** |
| **`NaN Diff` / `flag Exact %`** | `0` / `100.00%` | **`0` / `100.00%`** | Exact match |
| **`bias.UQ` RMSE (NDVI / Albedo)** | `4.57e-14` / `4.79e-14` | **`2.35e-09` / `1.36e-09`** | Parity achieved (`100% <= 1e-5`) |
| **`UQ` RMSE (NDVI / Albedo)** | `8.27e-10` / `2.91e-10` | **`7.01e-05` / `2.61e-05`** | $r = 0.999995$ / $0.999988$ |
| **`Mean` RMSE (NDVI / Albedo)** | `1.89e-09` / `9.19e-10` | **`4.24e-03` / `9.78e-04`** | Rebuilding `sobol.rs` next |

---

## 4. Verification & Rollback Checklist

- [x] `maturin develop --release` builds cleanly in the `ECOv003-L2T-STARS` conda environment without linking `libpython`.
- [x] `NaN Diff == 0` and `flag Exact % == 100.00%` across all 10 output layers in `test_bundle/`.
- [ ] `cargo test --release` passes all Rust unit tests (`sobol`, `covariance`, `spatial`, `kalman`).
- [ ] `python test_rust_output.py` achieves `RMSE <= 1e-7` across all 10 layers in `test_bundle/`.
- [ ] `PYTHONPATH=. pytest` passes all existing and new unit tests without Julia installed on `PATH`.
- [ ] `backend="julia"` runs and matches `backend="rust"` when Julia is installed.
- [ ] Wheel build (`maturin build --release --out dist`) succeeds and installs cleanly into a fresh virtual environment without Rust or Julia toolchains.