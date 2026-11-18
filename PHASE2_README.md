# Phase 2: Rust STARS Data Fusion Kernels (`_stars_rust`)

## Included Files
- `Cargo.toml` — Adds `ndarray = "0.16"`, `rlib` target for `cargo test`, and release LTO optimizations.
- `src/sobol.rs` — 2D Joe & Kuo base-2 Sobol sequence matching `Sobol.jl`.
- `src/spatial.rs` — Grid indexing, extent merging, and row-normalized centroid observation operator.
- `src/covariance.rs` — `compute_n_eff` (`s = d / range` Matérn 3/2 parameterization), `fast_var_est`, and `exp_cor`.
- `src/kalman.rs` — `faer` Cholesky Kalman filter and `rayon` parallel spatial window solver.
- `src/lib.rs` — PyO3 bindings (`estimate_spatial_variance`, `fuse_stars_product`, `smoke_test`).
- `ECOv003_L2T_STARS/_stars_rust.pyi` — Python type stubs for `_stars_rust`.
- `ECOv003_L2T_STARS/process_rust_data_fusion.py` — Python wrapper loading inputs, calling `_stars_rust`, and writing GeoTIFFs.
- `test_rust_output.py` — Offline benchmark and 10-layer numerical parity verification against `test_bundle/reference_outputs/`.

## Build & Verify
```bash
cargo test --release
make install
python test_rust_output.py
```
