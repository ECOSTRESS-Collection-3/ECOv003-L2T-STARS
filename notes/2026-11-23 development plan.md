# `ECOv003-L2T-STARS` Comprehensive Development Plan (`v1.0.1` → `v1.19.0`)

* **Date:** November 23, 2026

* **Current Baseline Release:** `v1.18.0`

* **Target Release:** `v1.19.0`

* **Primary Tracking Issues:** [GH #94](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/94), [GH #95](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/95), [GH #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96)

* **Reference I&T DAG Run:** `EcostressDAG_Col3.46000.0802.20261116T001911117` (807 logs scanned)

## 1. Completed Release History (`v1.0.1` – `v1.18.0`)

### Phase 1: Collection 2 Port & Hybrid Python/Julia Prototype (`v1.0.1` – `v1.1.0`, Nov 2024 – Jun 2025)

* \[x\] **`v1.0.1` (2024-11-12) — Initial Collection 3 Port:**

  * Duplicated from `ECOv002-L2T-STARS` as a monolithic Python/Julia hybrid package (`L2T_STARS.py`, 1,777 lines) bundling inline `BRDF/`, `LPDAAC/`, `VIIRS/`, `VNP43NRT/`, `daterange/`, `timer/`, `exit_codes.py`, and `STARS.jl` / `VNP43NRT.jl` Julia wrappers.

  * Removed unused `ECOSTRESS_tiled_granule.py` and unified `PGEVersion` with package version metadata.

* \[x\] **`v1.1.0` (2025-06-24) — Package Modularization, Distributed Bias Model & Downloader PGE:**

  * Replaced inline exit codes and granule serialization with `ECOv003-exit-codes` and `ECOv003-granules`.

  * Integrated `STARSDataFusion.jl` (`process_ECOSTRESS_data_fusion_distributed_bias.jl`), adding `NDVI-flag`, `albedo-flag`, `NDVI-bias`, `NDVI-bias-UQ`, `albedo-bias`, and `albedo-bias-UQ` layers alongside `threads=1` memory-profile controls.

  * Decomposed `ECOv003_L2T_STARS.py` into single-responsibility modules (`L2TSTARSConfig.py`, `L2T_STARS.py`, `constants.py`, `generate_L2T_STARS_runconfig.py`, `generate_STARS_inputs.py`, `retrieve_STARS_sources.py`, `load_prior.py`, `prior.py`, `process_STARS_product.py`, `process_julia_data_fusion.py`).

  * Added the `ECOv003-DL` Collection 3 Downloader PGE (`ECOv003_DL.py`, `ECOv003_DL.xml`) and `argparse` CLI interfaces.

### Phase 2: Run-Config Standardization, Credentials & Upstream Extraction (`v1.2.0` – `v1.10.0`, Jul – Sep 2025)

* \[x\] **`v1.2.0` (2025-07-03):** Added `--overwrite` CLI flag, fixed `generate_L2T_STARS_runconfig` return values, and reverted XML run-config parsing from `StaticAuxiliaryFileGroup` back to `StaticAncillaryFileGroup`.

* \[x\] **`v1.3.0` (2025-07-09):** Replaced `pycksum` with a pure-Python POSIX `cksum` module for Python 3.12+ compatibility, added Earthdata `.netrc` / environment authentication (`login.py`), and wired `ECOv003-L2T-STARS` CLI entry points.

* \[x\] **`v1.4.0` – `v1.4.1` (2025-07-15 to 2025-07-16):** Backported `DOWNSAMPLED_products` directory layout (`generate_downsampled_filename.py`), defaulted `initialize_julia=False`, wired prior bias layers, and resolved `VNP09GA` DataFrame search/warning spam.

* \[x\] **`v1.5.0` (2025-07-17):** Standardized constant names in `constants.py` and upgraded to `harmonized-landsat-sentinel>=2.0.0` (`HLS2Connection`).

* \[x\] **`v1.6.0` – `v1.6.1` (2025-07-17 to 2025-07-22):** Standardized layer naming to `NDVI-bias-UQ` / `albedo-bias-UQ` and corrected the `ECOv003-DL` script entry point in `pyproject.toml`.

* \[x\] **`v1.7.0` – `v1.7.5` (2025-07-29 to 2025-09-08):** Stripped Conda `GDAL_DATA` / `GDAL_DRIVER_PATH` from Julia subprocess environments, fixed `LPDAACServerUnreachable` imports and HLS missing-date formatting, wrote `StandardMetadata.BuildID`, and switched input granule loading to `ECOv003_granules.L2TLSTE`.

* \[x\] **`v1.8.0` – `v1.10.0` (2025-09-11 to 2025-09-25):** Adopted `L2TSTARS.generate_granule_name(...)` for Collection 3 granule IDs, fixed `job_ID` timestamp initialization, fixed `HLS_connection.listing` exception reporting, and added same-day prior copying (`copy_prior_to_posterior`) with Zip VFS flag URIs.

### Phase 3: Collection 3 Forward-Processing Baseline (`v1.11.0` – `v1.12.1`, Dec 2025 – Oct 2026)

* \[x\] **`v1.11.0` (2025-12-02) — Subprocess GDAL Isolation & Direct `ArchGDAL` Writing:** Hardened `os.environ.copy()` handling when stripping `GDAL_DATA` / `GDAL_DRIVER_PATH` for Julia subprocesses and implemented direct `ArchGDAL.create` GeoTIFF serialization (`safe_write_geotiff`) to eliminate `RastersArchGDALExt` driver failures across the \~11-month Suomi NPP baseline.

* \[x\] **`v1.12.0` (2026-10-12) — Dual-Collection Input & InputPointer Metadata:** Added support for both `ECOv003` and `ECOv002` `L2T_LSTE` inputs, populated `StandardMetadata.InputPointer`, and pinned core dependencies (`GEOS5FP~=2.21.0`, `ECOv003-granules~=1.13.2`).

* \[x\] **`v1.12.1` (2026-10-19) — Pinned Julia Environment Management:** Added `julia_environment.py`, `julia_smoke_test.jl`, and `ECOv003-L2T-STARS-install-julia` to validate the pinned Julia `Project.toml` / `Manifest.toml` environment.

### Phase 4: Suomi NPP → JPSS Transition & Rust Data-Fusion Core (`v1.13.0` – `v1.18.0`, Nov 2026)

* \[x\] **`v1.13.0` (2026-11-11) — Multi-Mission JPSS Transition (`VCD43NRT`):** Migrated coarse VIIRS processing from decommissioned Suomi NPP `VNP43NRT` to multi-mission JPSS `VCD43NRT` (`mission_priority = ("SNPP", "JPSS1", "JPSS2")`, `fallback_mode=True`), removed \~3,500 lines of legacy inline VIIRS/BRDF/LPDAAC modules, and added `ECOv003-CMR` download examples.

* \[x\] **`v1.14.0` – `v1.16.0` (2026-11-11 to 2026-11-12) — Cross-PGE Alignment & Smoke Testing:** Aligned dependency pins with `ECOv003-L3T-L4T-JET` (`GEOS5FP~=2.23.0`, `numpy~=2.5.4`, `pandas~=3.1.1`, `rasterio~=1.5.2`), introduced `smoke_test.py` (`test`, `test-python`, `test-julia`), added `install_julia.py` with automatic `juliaup` bootstrapping, and standardized on Julia `1.11.6` and Python `3.12`.

* \[x\] **`v1.17.0` (2026-11-17) — Coarse Window Outage Resilience & Offline Verification:** Tolerated partial-window GEOS-5 FP / VIIRS outages when at least one coarse NDVI and albedo raster succeeds, raised `AuxiliaryLatency` (`15`) within `VIIRS_GIVEUP_DAYS = 4` or `DownloadFailed` (`16`) when zero coarse inputs exist across historical windows, validated all 5 posterior GeoTIFFs (`BlankOutput` `17`), and added `test_bundle/` + `test_julia_output.py`.

* \[x\] **`v1.18.0` (2026-11-18) — Compiled Rust Data-Fusion Core & Multi-Worker Isolation:**

  * Implemented the compiled Rust/PyO3 STARS data-fusion kernel (`_stars_rust` in `src/lib.rs`, `src/kalman.rs`, `src/covariance.rs`, `src/sobol.rs`, `src/spatial.rs`, `process_rust_data_fusion.py`) built via `maturin` with `abi3-py311` wheel support, making `FUSION_BACKEND = "rust"` the default while retaining `--backend julia` as a fallback.

  * Added `VCD43NRT_staging_directory` isolation in `L2T_STARS.py` to prevent multi-worker collisions in `VCD43NRT_products/`.

  * Downgraded non-land `LandFilter` skips from `[ERROR]` (`logger.exception`) to `[INFO]` (`logger.info`).

## 2. Pending Development Plan for `v1.19.0`

The `v1.19.0` release resolves all remaining I&T defects uncovered in `EcostressDAG_Col3.46000.0802.20261116T001911117` and aligns repository structure, container packaging, and build-time smoke testing with `ECOv003-L3T-L4T-JET v1.22.1`.

### Workstream 1: Concurrency & Subprocess Reliability (`#94`, `#95`)

#### 1.1. Isolate Intermediate Posterior Rasters Per Granule ([GH #94](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/94))

* **Problem:** `process_STARS_product.py` writes intermediate posterior rasters into shared `model_directory/<tile>/<date_UTC>/`. Concurrent workers processing different scenes on the same tile/date collide on `REMOVE_POSTERIOR = True`, causing `OSError: raster file not found` between `granule.write_zip()` and post-zip `Raster.open(...).to_geotiff(...)`.

* **Tasks:**

  * \[ \] Update `process_STARS_product.py` to write intermediate posterior GeoTIFFs into a granule-unique working path (`join(working_directory, "posteriors", granule_ID)` or `join(model_directory, tile, f"{date_UTC:%Y-%m-%d}", granule_ID)`) while preserving `generate_model_state_tile_date_directory` for persisted prior state.

  * \[ \] Clean up the empty per-granule posterior directory after `remove_posterior` finishes so `L2T_STARS_MODEL` / `working_directory` does not accumulate empty subdirectories.

  * \[ \] Add a concurrency regression test in `tests/test_process_STARS_product.py` verifying two overlapping `(tile, date_UTC)` invocations with distinct `granule_ID`s and `remove_posterior=True` do not interfere.

#### 1.2. Capture & Log Legacy Julia Subprocess Output ([GH #95](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/95))

* **Problem:** `process_julia_data_fusion.py` runs `subprocess.run(command, check=False, env=julia_env)` without capturing output, leaving non-zero Julia exit codes (`exit code 1`) without diagnostic tracebacks in the PGE `.log` file.

* **Tasks:**

  * \[ \] Stream combined `stdout`/`stderr` via `subprocess.Popen(..., stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)` (or `subprocess.run(..., capture_output=True, text=True)`), forwarding lines to `logger.info` and emitting the trailing output block via `logger.error` when `returncode != 0` before raising `RuntimeError`.

  * \[ \] Update `tests/test_process_julia_data_fusion.py` to verify stderr/stdout capture and logging on non-zero return codes.

### Workstream 2: Repository Alignment with `ECOv003-L3T-L4T-JET`

#### 2.1. Multi-Stage `micromamba` + Rust `Dockerfile` & Container Smoke Tests

* **Problem:** `ECOv003-L2T-STARS`'s standalone `Dockerfile` uses `python:3.12-bookworm` + Debian `apt` `libgdal-dev` without explicit `GDAL_DRIVER_PATH` / HDF5 / NetCDF4 plugin wiring, diverging from `ECOv003-L3T-L4T-JET`'s 3-stage `mambaorg/micromamba:ubuntu24.04` runtime (`libgdal-netcdf`, `libgdal-hdf5`).

* **Tasks:**

  * \[ \] Refactor `Dockerfile` into 3 stages (`toolchain` → `build` → `runtime`) matching `JET`:

    1. `toolchain`: `mambaorg/micromamba:ubuntu24.04` with `conda-forge` `python=3.12`, `libgdal-netcdf`, `libgdal-hdf5`, `rasterio~=1.5.2`, `numpy~=2.5.4`, `pandas~=3.1.1`, `scipy~=1.18.1`, `scikit-image~=0.26.0`, `shapely~=2.2.0`, `h5py~=3.14.0`, `matplotlib-base~=3.10.9`, plus minimal `rustup` / `cargo` / `maturin`.

    2. `build`: Lock conda packages via `/tmp/conda-constraints.txt`, install Python dependencies and build the `_stars_rust` release extension wheel into `/opt/venv`.

    3. `runtime`: Set `GDAL_DRIVER_PATH="/opt/venv/lib/gdalplugins"`, `GDAL_DATA="/opt/venv/share/gdal"`, `PROJ_DATA="/opt/venv/share/proj"`, `MPLCONFIGDIR=/opt/matplotlib`, and `SHELL=/usr/bin/fish`.

  * \[ \] Add `tests/test_docker_smoke.py` and wire `make docker-smoke-test` in `makefile`.

#### 2.2. Expand `smoke_test.py` with GDAL Plugin & Upstream Contract Assertions

* **Tasks:**

  * \[ \] Add GDAL driver verification to `ECOv003_L2T_STARS/smoke_test.py` asserting that `osgeo.gdal.GetDriverByName("netCDF")` and `GetDriverByName("HDF5")` are non-null (catching missing `libgdal-netcdf` / `libgdal-hdf5` plugins at build time).

  * \[ \] Add upstream API signature assertions verifying `VCD43NRT.__init__` accepts `VCD43NRT_staging_directory`, `fallback_mode`, `mission_priority`, and `GEOS5FP_download`, and exposes `.NDVI()`, `.albedo()`, and `.prefetch_VNP09GA()`.

  * \[ \] Add a synthetic `_stars_rust.fuse_stars_product(...)` end-to-end kernel call to `test_rust()` in `smoke_test.py`.

#### 2.3. CLI Cleanup, Metadata Provenance & Directory Hygiene

* **Tasks:**

  * \[ \] Refactor `ECOv003_L2T_STARS/main.py` to expose `build_parser()` and `main(argv=None)` (matching `JET`), fix `install-julia` exit code (`sys.exit(install_julia() or SUCCESS_EXIT_CODE)`), and support `--test` alongside the `test` subcommand.

  * \[ \] Set `metadata["StandardMetadata"]["PGEVersion"] = __version__` in `process_STARS_product.py` (matching `JET` and Collection 3 metadata specifications).

  * \[ \] Reuse the already-parsed `L2TLSTE` granule object from `L2TSTARSConfig` in `L2T_STARS.py` to avoid opening the input ZIP archive twice.

  * \[ \] Update `ECOv003_DL.py` log messages from `"ECOSTRESS Collection 2 Downloader PGE"` to `"ECOSTRESS Collection 3 Downloader PGE"`.

  * \[ \] Organize root-level scripts into `examples/` (`demo.py`, `example_download.py`, `example_L2T_STARS_with_download.py`, `example_VCD43NRT.py`) and commit `notes/` (`2026-11-23 ECOv003-L2T-STARS repository history.md`, `2026-11-23 ECOv003-L2T-STARS known issues.md`).

### Workstream 3: I&T Operational Rollout & Verification ([GH #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96))

* **Tasks:**

  * \[ \] Tag and publish `ECOv003-L2T-STARS v1.19.0` (with pre-built `abi3-py311` wheels on PyPI / Artifactory).

  * \[ \] Rebuild the shared `eco-level-2-3-4-application` container with `ECOv003-L2T-STARS>=1.19.0` and `ECOv003-L3T-L4T-JET>=1.22.1`, verifying `ECOv003-L2T-STARS test` and `ECOv003-L3T-L4T-JET test`.

  * \[ \] Purge truncated/corrupted `.nc4` files in `/runtime_ancillary/L2T_STARS_SOURCES/GEOS5FP_download/` left by `portal.nccs.nasa.gov` `SSLEOFError` / `IncompleteRead` dropouts.

  * \[ \] Re-drive failed tiles from `EcostressDAG_Col3.46000.0802.20261116T001911117` and confirm zero concurrency or GDAL plugin errors.

## 3. Release Verification Gate (`v1.19.0`)

Before tagging `v1.19.0`, all of the following checks must pass:

1. `make test-rust` (`cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test --release`)

2. `make test` (`pytest` suite including new concurrency and Julia stderr capture tests)

3. `make verify` (offline Rust fusion parity against `test_bundle/reference_outputs/`, `RMSE < 1e-7`, `0` NaN mask disagreements)

4. `make wheel-test` (isolated wheel installation + `python -I -m ECOv003_L2T_STARS.smoke_test`)

5. `make docker-smoke-test` (container GDAL NetCDF/HDF5 plugin checks + CLI smoke tests)