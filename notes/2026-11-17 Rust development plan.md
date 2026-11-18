# Development Plan: Migrating STARS Data Fusion to a Pure Rust (`PyO3` / `maturin`) Extension

## 1. Executive Summary

Following the consolidation and pruning of the Julia data fusion script (`ECOv003_L2T_STARS/process_ECOSTRESS_data_fusion_distributed_bias.jl`), the entire STARS Kalman filter and spatial Gaussian process algorithm is self-contained (~520 lines of pure numerical logic with zero external geospatial library dependencies).

This plan outlines the migration of the data fusion core into a compiled Rust extension (`ECOv003_L2T_STARS._stars_rust`) built with `PyO3` and `maturin`.

### Key Goals
1. **Zero Julia Runtime Dependency for End Users:** Standard `pip install ECOv003-L2T-STARS` installs prebuilt platform wheels (`manylinux`, `macos-arm64`, `windows`) with compiled Rust binaries—no Julia installation, `Manifest.toml` instantiation, or GDAL C-library isolation required.
2. **Eliminate Multi-Process Startup & Serialization Overhead:** Replace `Distributed.addprocs` worker spawning (`~4.5s` per product) and `pmap` IPC serialization with in-process `rayon` thread-pool parallelism over shared read-only NumPy memory views.
3. **Preserve Optional Legacy Julia Path:** Retain `process_julia_data_fusion.py` and `process_ECOSTRESS_data_fusion_distributed_bias.jl` behind an opt-in `backend="julia"` flag for side-by-side regression benchmarking, without requiring Julia at package installation or import time.
4. **Bitwise Numerical Parity:** Validate all 10 output rasters (`NDVI` and `albedo` mean, `UQ`, `flag`, `bias`, and `bias.UQ`) against `test_bundle/reference_outputs/` to `RMSE <= 1e-8`, `NaN Diff = 0`, and Pearson $r = 1.000000$.

---

## 2. Target Package & Repository Layout

```text
ECOv003-L2T-STARS/
├── Cargo.toml                                        # Rust crate configuration (cdylib + rlib)
├── pyproject.toml                                    # maturin build-backend & Python metadata
├── src/
│   ├── lib.rs                                        # PyO3 module entry point & NumPy zero-copy bindings
│   ├── sobol.rs                                      # Joe & Kuo base-2 Sobol sequence matching Sobol.jl
│   ├── spatial.rs                                    # Grid indexing, BAU selection, observation operator H
│   ├── covariance.rs                                 # compute_n_eff, fast_var_est, exp_cor, cubic resampling
│   └── kalman.rs                                     # Cholesky Kalman filter & rayon window fusion
├── ECOv003_L2T_STARS/
│   ├── __init__.py
│   ├── process_rust_data_fusion.py                   # Python wrapper calling _stars_rust & writing GeoTIFFs
│   ├── process_julia_data_fusion.py                  # Optional legacy Julia backend (lazy-loaded)
│   ├── process_ECOSTRESS_data_fusion_distributed_bias.jl
│   ├── process_STARS_product.py                      # Backend router ("rust" default, "julia" legacy)
│   └── ...
├── tests/
│   ├── test_rust_data_fusion.py                      # Unit & numerical parity tests vs test_bundle/
│   └── ...
└── .github/workflows/
    ├── ci.yml                                        # cargo test + maturin develop + pytest
    └── python-publish.yml                            # PyO3/maturin-action multi-platform wheel builds
```

---

## 3. Julia-to-Rust Component Mapping

| Julia Component (`process_ECOSTRESS_data_fusion_distributed_bias.jl`) | Rust Crate / Module | Implementation Strategy |
| :--- | :--- | :--- |
| `addprocs(wrkrs)` + `pmap(...)` | `rayon` (`ThreadPoolBuilder`) | Build a scoped `rayon::ThreadPool` sized to `num_workers` and execute `par_iter()` across all spatial windows (`50,176` NDVI / `12,544` albedo) with zero-copy shared slice references. |
| `LAPACK.potrf!` / `potri!` / `BLAS.symm` | `faer` (`0.20+`) | Pure-Rust SIMD Cholesky decomposition (`S.llt(Side::Lower)`) and triangular solve (`llt.solve_in_place(...)`)—avoids explicit matrix inversion (`potri!`), improves numerical conditioning, and eliminates OpenBLAS/MKL linking issues in wheels. |
| `Sobol.SobolSeq([is[1], js[1]], [is[2], js[2]])` | `src/sobol.rs` | Implement Joe & Kuo base-2 direction numbers matching `Sobol.jl`'s exact sequence (skipping index `0` and scaling `is[1] + u1 * (is[2] - is[1])`) so the 100 background BAU coordinates per window match bit-for-bit. |
| `fast_var_est` & `compute_n_eff` | `src/covariance.rs` | Single-pass `@inbounds`-equivalent slice variance over temporal first-differences (`min_num_obs = 8`, `default_var = 1e-4`) and Matérn 3/2 correlation ($s = d / \lambda$, no $\sqrt{3}$ factor). |
| `Rasters.resample(..., method=:cubicspline)` | Python (`scipy.ndimage` / `rasters`) or `src/covariance.rs` | Resample `log(sqrt(sp_var))` from the coarse grid (`224x224` or `112x112`) to the fine grid (`1568x1568`) using natural cubic B-spline interpolation matching `Interpolations.jl`. |
| `unif_weighted_obs_operator_centroid` | `src/spatial.rs` | Construct row-normalized sparse/dense weights where $|s_x - t_x| \le \Delta x / 2 + 10^{-12}$ and $|s_y - t_y| \le \Delta y / 2 + 10^{-12}$. |
| `ArchGDAL` GeoTIFF I/O | Python (`rasters.Raster.to_geotiff`) | Pass `Float32`/`Int32` NumPy arrays back to `process_rust_data_fusion.py` and write compressed, tiled GeoTIFFs using the existing `rasters` / `rasterio` stack. |

---

## 4. Build & Packaging Configuration (`maturin` + `PyO3`)

### 4.1 `Cargo.toml`

```toml
[package]
name = "ecov003-l2t-stars-rust"
version = "1.19.0"
edition = "2021"

[lib]
name = "_stars_rust"
crate-type = ["cdylib", "rlib"]

[dependencies]
pyo3 = { version = "0.23", features = ["extension-module"] }
numpy = "0.23"
rayon = "1.10"
faer = "0.20"

[profile.release]
opt-level = 3
lto = "fat"
codegen-units = 1
```

### 4.2 `pyproject.toml` Updates

Switch `[build-system]` from `setuptools` to `maturin` while keeping all existing Python dependencies, package data (`*.xml`, `Project.toml`, `*.jl`), and console scripts intact:

```toml
[build-system]
requires = ["maturin>=1.7,<2.0"]
build-backend = "maturin"

[tool.maturin]
module-name = "ECOv003_L2T_STARS._stars_rust"
python-source = "."
include = [
    "ECOv003_L2T_STARS/*.xml",
    "ECOv003_L2T_STARS/*.toml",
    "ECOv003_L2T_STARS/*.jl",
]
```

---

## 5. Python–Rust Interface & Dual-Backend Architecture

### 5.1 Zero-Copy PyO3 Function Signature (`src/lib.rs`)

Expose a single high-level entry point `fuse_stars_product` accepting read-only NumPy arrays (`PyReadonlyArray2` / `PyReadonlyArray3`) and returning a tuple of 5 NumPy arrays `(fused_mean, fused_sd, hls_flag, fused_bias, fused_bias_sd)`:

```rust
#[pyfunction]
#[pyo3(signature = (
    coarse_cov_stack,
    coarse_stack,
    coarse_time_indices,
    fine_stack,
    fine_time_indices,
    flag_fine_stack,
    coarse_origin,
    coarse_cell_size,
    fine_origin,
    fine_cell_size,
    target_time_index,
    is_ndvi,
    prior_mean=None,
    prior_sd=None,
    prior_bias_mean=None,
    prior_bias_sd=None,
    num_workers=8,
    nsamp=100,
    window_buffer=4,
    cov_wt=0.2,
    nb_coarse=2.0
))]
fn fuse_stars_product<'py>(
    py: Python<'py>,
    // ... typed NumPy array arguments ...
) -> PyResult<(
    Bound<'py, PyArray2<f32>>,
    Bound<'py, PyArray2<f32>>,
    Bound<'py, PyArray2<i32>>,
    Bound<'py, PyArray2<f32>>,
    Bound<'py, PyArray2<f32>>,
)>
```

### 5.2 Optional Legacy Julia Backend (`ECOv003_L2T_STARS/process_STARS_product.py`)

Add a `backend: Literal["rust", "julia"] = "rust"` parameter to `L2T_STARS()`, `process_STARS_product()`, and the `ECOv003-L2T-STARS` CLI (`--backend rust|julia`):

```python
if backend == "rust":
    from .process_rust_data_fusion import process_rust_data_fusion
    process_rust_data_fusion(...)
elif backend == "julia":
    from .process_julia_data_fusion import process_julia_data_fusion
    process_julia_data_fusion(...)
else:
    raise ValueError(f"Unsupported STARS fusion backend: {backend!r}")
```

* When `backend == "rust"` (default), `julia_environment.py` is never invoked, and users do not need Julia installed.
* When `backend == "julia"` is explicitly requested, `find_julia_command()` validates the local Julia installation and raises `JuliaEnvironmentError` if unavailable.
* Keep `ECOv003-L2T-STARS-install-julia` as an optional helper command for users who wish to run the legacy Julia backend.

---

## 6. Phased Implementation Roadmap

### Phase 1: Rust Crate Scaffolding & Numerical Kernel Unit Tests (Week 1)
1. Create `Cargo.toml` and `src/` modules (`sobol.rs`, `spatial.rs`, `covariance.rs`, `kalman.rs`, `lib.rs`).
2. Update `pyproject.toml` to use `maturin` and verify local editable builds via `maturin develop --release`.
3. Write pure-Rust `#[cfg(test)]` unit tests verifying:
   * `sobol.rs` first 100 2D points match `Sobol.jl` output to `1e-15`.
   * `covariance.rs` `compute_n_eff(7, 2.0, 1.5)` equals `2.0026...` and `compute_n_eff(14, 2.0, 1.5)` matches Julia bit-for-bit.
   * `kalman.rs` single-window filter update matches `kalman_filter!` to `1e-13`.

### Phase 2: Full-Scene `rayon` Fusion & Golden Parity Verification (Week 2)
1. Implement `process_rust_data_fusion.py` to load downsampled GeoTIFFs via `rasters`, call `_stars_rust.fuse_stars_product(...)`, and write the 5 posterior GeoTIFFs (`mean`, `UQ`, `flag`, `bias`, `bias.UQ`).
2. Add `test_rust_output.py` (modeled on `test_julia_output.py`) and run against `test_bundle/` for both `NDVI` (`490m` $\rightarrow$ `70m`) and `albedo` (`980m` $\rightarrow$ `70m`).
3. Verify acceptance criteria across all 10 layers:
   * `NaN Diff == 0`
   * `Flag Exact % == 100.00%`
   * `RMSE <= 1e-7`
   * `Pearson r >= 0.999999`
4. Benchmark end-to-end runtime against the Round 4 Julia baseline (`2m 05s` total; expected Rust runtime `< 35s` with zero worker startup overhead).

### Phase 3: Dual-Backend Integration & Multi-Platform CI/CD (Week 3)
1. Wire `backend="rust"` (default) and `--backend` CLI option into `L2T_STARS.py`, `process_STARS_product.py`, and `main.py`.
2. Update `ECOv003_L2T_STARS/smoke_test.py` so `ECOv003-L2T-STARS test` tests Python + `_stars_rust` by default, while `ECOv003-L2T-STARS test-julia` remains available when Julia is present.
3. Update `.github/workflows/ci.yml` to run `cargo test`, `maturin develop --release`, and `pytest`.
4. Update `.github/workflows/python-publish.yml` to use `PyO3/maturin-action@v1` to build and publish wheels for:
   * Linux (`x86_64`, `aarch64` `manylinux`)
   * macOS (`arm64`, `x86_64`)
   * Windows (`x64`)
   * Source distribution (`sdist`)
5. Update `Dockerfile` to install via `pip install .` (removing the Julia tarball download for standard production builds unless `--build-arg INCLUDE_JULIA=1` is passed).

---

## 7. Verification & Rollback Checklist

- [ ] `cargo test --release` passes all numerical kernel tests.
- [ ] `maturin develop --release` builds cleanly in the `ECOv003-L2T-STARS` conda environment.
- [ ] `python test_rust_output.py` achieves `NaN Diff = 0` and `RMSE <= 1e-7` across all 10 layers in `test_bundle/`.
- [ ] `PYTHONPATH=. pytest` passes all existing unit tests without Julia installed on `PATH`.
- [ ] `backend="julia"` runs and matches `backend="rust"` when Julia is installed.
- [ ] Wheel build (`maturin build --release --out dist`) succeeds and installs cleanly into a fresh virtual environment without Rust or Julia toolchains.