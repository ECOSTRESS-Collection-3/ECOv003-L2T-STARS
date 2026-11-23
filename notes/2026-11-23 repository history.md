
# `ECOv003-L2T-STARS` Repository History & Collection 3 Operational Context (`v1.0.1` – `v1.18.0`)

The `ECOv003-L2T-STARS` repository evolved from its initial Collection 2 port in November 2024 (`v1.0.1`) through `v1.18.0` (November 2026), transforming from a monolithic Python/Julia hybrid script into a modular, JPSS-compatible Collection 3 operational Product Generating Executable (PGE) powered by a compiled Rust/PyO3 Kalman-filter data-fusion core (`_stars_rust`).

---

## 1. Operational Context: Collection 3 Forward Processing & the Suomi NPP → JPSS Transition

The release history of `ECOv003-L2T-STARS` is closely tied to the operational lifecycle of the NASA JPL ECOSTRESS Science Data System (SDS) forward-processing stack (`ecostress-level-2-3-4`, published to `artifactory.jpl.nasa.gov:16001/gov/nasa/jpl/ecostress/sds/pge-v3/eco-level-2-3-4-application`):

### 1.1. Collection 3 Forward-Processing Baseline (`v1.11.0` – `v1.12.1`)
* **Deployment Baseline (`v1.11.0`):** Entering operational Collection 3 forward processing in late 2025 (`eco-level-2-3-4-application` `v1.7.0` / `v1.7.1`, pinning `ECOv003-L2T-STARS>=1.11.0`), `L2T_STARS` ingested Suomi NPP VIIRS (`VNP43NRT`) coarse surface reflectance and albedo inputs alongside Harmonized Landsat Sentinel (`HLS2Connection`) fine-resolution observations to produce 70 m daily NDVI and albedo fields (`BuildID` `0700`).
* **Output Consistency & Julia Isolation (`v1.11.0` – `v1.12.1`):** During the ~11-month Suomi NPP operational run, maintenance focused on isolating Julia's bundled `GDAL_jll` environment from host/Conda GDAL variables (`GDAL_DATA`, `GDAL_DRIVER_PATH`), hardening GeoTIFF writing via direct `ArchGDAL.create` calls, correcting `StandardMetadata.InputPointer` provenance, and pinning the Julia `1.11.6` manifest environment.

### 1.2. November 2, 2026 Suomi NPP Decommissioning, JPSS Cutover & Rust Migration (`v1.13.0` – `v1.18.0`)
* **Upstream Sensor Cutover:** On **November 2, 2026**, Suomi NPP VIIRS was decommissioned, terminating upstream `VNP43NRT` coarse inputs.
* **Multi-Mission JPSS & Rust Core Migration:**
  1. `ECOv003-L2T-STARS v1.13.0` migrated coarse VIIRS processing from single-mission Suomi NPP `VNP43NRT` to multi-mission JPSS `VCD43NRT` (`mission_priority = ("SNPP", "JPSS1", "JPSS2")`, `fallback_mode=True`) and removed ~3,500 lines of legacy inline VIIRS/BRDF/LPDAAC modules.
  2. Across `v1.14.0`–`v1.16.0`, dependency pins (`GEOS5FP~=2.24.0`, `numpy~=2.5.4`, `pandas~=3.1.1`, `rasterio~=1.5.2`) and Python `3.12` compatibility were synchronized with `ECOv003-L3T-L4T-JET` for coordinated container builds.
  3. `v1.17.0` added fast-fail and latency handling (`VIIRS_GIVEUP_DAYS = 4`) when upstream GEOS-5 FP or VIIRS granules are unavailable.
  4. `v1.18.0` replaced the Julia distributed data-fusion hot loop with a compiled Rust/PyO3 extension (`_stars_rust` built with `maturin`, `faer`, and `rayon`), eliminating Julia subprocess overhead and GDAL library conflicts while preserving numerical parity (`RMSE < 1e-7`) with reference outputs and retaining `--backend julia` as an optional fallback.

### 1.3. Cross-Stack Forward-Processing Version Matrix

| Operational Epoch | Dates | `ECOv003-L2T-STARS` | Data Fusion Engine | Coarse VIIRS Source | Sister PGE (`ECOv003-L3T-L4T-JET`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Epoch 1: Initial C3 Port & Modularization** | Nov 2024 – Sep 2025 | `v1.0.1` – `v1.10.0` | Julia (`STARSDataFusion.jl`) | Suomi NPP (`VNP43NRT` / `VNP43IA4` / `VNP43MA3`) | `v1.0.1` – `v1.9.0` |
| **Epoch 1: C3 Forward-Processing Baseline** | Dec 2025 – Nov 2, 2026 | `v1.11.0` – `v1.12.1` | Julia `1.11.6` (isolated `GDAL_jll`) | Suomi NPP (`VNP43NRT`) | `v1.13.0` – `v1.18.0` |
| **Epoch 2: JPSS Cutover & Dependency Alignment** | Nov 11 – Nov 17, 2026 | `v1.13.0` – `v1.17.0` | Julia `1.11.6` | JPSS Multi-Mission (`VCD43NRT`) | `v1.19.0` – `v1.20.3` |
| **Epoch 2: Rust Fusion Core & Concurrency Hardening** | Nov 18, 2026 – Present | `v1.18.0` | **Rust (`_stars_rust` default)** / Julia fallback | JPSS Multi-Mission (`VCD43NRT` + staging isolation) | `v1.21.0` – `v1.22.1` |

---

## 2. Chronological Release History (`v1.0.1` – `v1.18.0`)

### Phase 1: Collection 2 Port & Hybrid Python/Julia Prototype (`v1.0.1` – `v1.1.0`, Nov 2024 – Jun 2025)

* **`v1.0.1` (2024-11-12) — Initial Collection 3 Port:**
  * Duplicated from `ECOv002-L2T-STARS` as a Python/Julia hybrid package (`100827b`), initially housing the entire pipeline in a single 1,777-line `L2T_STARS.py` module alongside bundled `BRDF/`, `LPDAAC/`, `VIIRS/`, `VNP43NRT/`, `daterange/`, `timer/`, and `exit_codes.py` sub-modules.
  * Removed the unused `ECOSTRESS_tiled_granule.py` module (`5c9cbfb`) and replaced `PGEVersion.txt` with package version metadata (`b7dfd6e`).
* **Spring 2025 Algorithm & Bias Model Integration (`Dec 2024 – May 2025`):**
  * Added single-threaded Julia execution controls (`threads=1`, `1ad8e4e`) to reduce memory pressure during distributed tile processing.
  * Integrated `STARSDataFusion.jl` and `process_ECOSTRESS_data_fusion_distributed_bias.jl` (`c71c90d`, `5674451`), adding posterior and prior bias and bias-uncertainty layers (`NDVI-bias`, `NDVI-bias-UQ`, `albedo-bias`, `albedo-bias-UQ`) as well as `NDVI-flag` and `albedo-flag` layers.
* **`v1.1.0` (2025-06-24) — Package Modularization & Downloader PGE:**
  * Replaced local `exit_codes.py` with the shared `ECOv003-exit-codes` package (`b966a9b`, `0e6dfed`).
  * Decomposed `ECOv003_L2T_STARS.py` into focused modules (`99e459f`): `L2TSTARSConfig.py`, `L2T_STARS.py`, `constants.py`, `generate_L2T_STARS_runconfig.py`, `generate_STARS_inputs.py`, `retrieve_STARS_sources.py`, `load_prior.py`, `prior.py`, `process_STARS_product.py`, `process_julia_data_fusion.py`, and raster generation/calibration helpers.
  * Added the `ECOv003-DL` Collection 3 Downloader PGE (`ECOv003_DL.py`, `1f8f6b3`) and `argparse` CLI interfaces (`9d6fb82`, `cb2ca5f`).

### Phase 2: XML Run-Config, Authentication & Upstream Extraction (`v1.2.0` – `v1.10.0`, Jul – Sep 2025)

* **`v1.2.0` (2025-07-03):** Added `--overwrite` CLI support (`2263392`), fixed `generate_L2T_STARS_runconfig` return values (`b7e8675`), and reverted XML run-config parsing from `StaticAuxiliaryFileGroup` back to `StaticAncillaryFileGroup` (`87a8f41`).
* **`v1.3.0` (2025-07-09):** Replaced `pycksum` with a pure-Python POSIX `cksum` implementation for Python 3.12+ compatibility (`883a6c7`, `625ba08`), added Earthdata `.netrc` / environment authentication (`login.py`, `cdca702`), and wired `ECOv003-L2T-STARS` CLI entry points (`09073f1`).
* **`v1.4.0` – `v1.4.1` (2025-07-15 to 2025-07-16):**
  * Backported `DOWNSAMPLED_products` directory organization (`generate_downsampled_filename.py`, `35e5bea`), defaulted `initialize_julia=False` (`903c14b`), assumed prior bias layers (`7cecf12`), and fixed `VNP09GA` DataFrame search and warning spam (`28706fd`, `e7b82a3`, `a2f8334`).
* **`v1.5.0` (2025-07-17):** Standardized constant names in `constants.py` (`6342c58`, `3cc9803`) and upgraded to `harmonized-landsat-sentinel>=2.0.0` (`HLS2Connection`, `40ef4bc`).
* **`v1.6.0` – `v1.6.1` (2025-07-17 to 2025-07-22):** Standardized layer naming to `NDVI-bias-UQ` / `albedo-bias-UQ` (`cd0c4d1`) and fixed the `ECOv003-DL` script entry point in `pyproject.toml` (`cd0d3ca`).
* **`v1.7.0` – `v1.7.5` (2025-07-29 to 2025-09-08):**
  * Isolated Julia subprocess environments from Conda `GDAL_DATA` / `GDAL_DRIVER_PATH` (`ebebcd3`, `1b598f2`), fixed `LPDAACServerUnreachable` imports (`2388767`), fixed HLS missing-date string formatting (`bdd275e`), explicitly wrote `StandardMetadata.BuildID` (`68cf946`), and switched input granule loading to `ECOv003_granules.L2TLSTE` (`ba9fa03`).
* **`v1.8.0` – `v1.10.0` (2025-09-11 to 2025-09-25):**
  * Adopted `L2TSTARS.generate_granule_name(...)` for Collection 3 granule IDs (`0f434f4`, `8576b56`), fixed `job_ID` timestamp initialization (`63ab61a`), fixed `HLS_connection.listing` exception reporting (`2d776f6`), and added same-day prior copying (`copy_prior_to_posterior`) with Zip VFS flag URIs (`d878146`).

### Phase 3: Collection 3 Forward-Processing Baseline (`v1.11.0` – `v1.12.1`, Dec 2025 – Oct 2026)

* **`v1.11.0` (2025-12-02):** Hardened `os.environ.copy()` handling so stripping `GDAL_DATA` and `GDAL_DRIVER_PATH` for Julia subprocesses never mutates parent process environment variables or raises `KeyError`, and expanded unit test coverage (`966c62a`, `3e5a223`, `bd73f64`).
* **`v1.12.0` (2026-10-12):** Added support for both `ECOv003` and `ECOv002` `L2T_LSTE` inputs in `L2T_STARS.py` and `generate_L2T_STARS_runconfig.py`, populated `StandardMetadata.InputPointer`, and pinned core dependencies (`GEOS5FP~=2.21.0`, `ECOv003-granules~=1.13.2`, `6b9e960`).
* **`v1.12.1` (2026-10-19):** Added `julia_environment.py`, `julia_smoke_test.jl`, and the `ECOv003-L2T-STARS-install-julia` CLI entry point to validate the pinned Julia `Project.toml` / `Manifest.toml` environment (`6232a93`).

### Phase 4: JPSS Transition & Rust Data-Fusion Core (`v1.13.0` – `v1.18.0`, Nov 2026)

* **`v1.13.0` (2026-11-11):**
  * Migrated coarse VIIRS processing from decommissioned Suomi NPP `VNP43NRT` to multi-mission JPSS `VCD43NRT` (`mission_priority = ("SNPP", "JPSS1", "JPSS2")`, `fallback_mode=True`, `496e96e`).
  * Removed obsolete inline `BRDF/`, `LPDAAC/`, `VIIRS/`, `VNP43NRT/`, `daterange/`, and `timer/` packages (`4e815f3`, `d248dce`, `d06a7cc`) and added `ECOv003-CMR` download examples (`dc438a6`).
* **`v1.14.0` – `v1.16.0` (2026-11-11 to 2026-11-12):**
  * Added `set_julia_version.py` (`f45f171`), aligned dependency versions with `ECOv003-L3T-L4T-JET` (`GEOS5FP~=2.23.0`, `numpy~=2.5.4`, `pandas~=3.1.1`, `rasterio~=1.5.2`, `60b5995`), introduced `smoke_test.py` (`test`, `test-python`, `test-julia`, `86937d1`, `0fb036e`), added `install_julia.py` with automatic `juliaup` bootstrapping (`3456900`), and standardized on Julia `1.11.6` and Python `3.12` (`187c64c`, `7e3de6a`).
* **`v1.17.0` (2026-11-17):**
  * Added fail-fast and latency error handling in `generate_STARS_inputs.py` and `retrieve_STARS_sources.py` (`d8b288a`, `2d8ef80`): raises `AuxiliaryLatency` (exit code `15`) if coarse dates within `VIIRS_GIVEUP_DAYS = 4` are missing, raises `DownloadFailed` (exit code `16`) if zero coarse NDVI/albedo images are available across the window, validates all 5 posterior GeoTIFFs (`BlankOutput` exit code `17`), and adds offline verification (`test_bundle/` and `test_julia_output.py`, `b00b5da`).
* **`v1.18.0` (2026-11-18):**
  * Implemented the compiled Rust/PyO3 STARS data-fusion kernel (`_stars_rust` in `src/lib.rs`, `src/kalman.rs`, `src/covariance.rs`, `src/sobol.rs`, `src/spatial.rs`, `process_rust_data_fusion.py`) built via `maturin` with `abi3-py311` wheel support (`1a71a47`, `61e9034`, `08f09f6`, `05db869`, `eeea353`), making `FUSION_BACKEND = "rust"` the default while keeping `--backend julia` as a fallback.
  * Passed `VCD43NRT_staging_directory` to `VCD43NRT` (`a4b5127`) to prevent multi-worker collisions in `VCD43NRT_products/`.
  * Changed `LandFilter` exception logging from `logger.exception` (`[ERROR]`) to `logger.info` (`[INFO]`, `a4b5127`).

---

## 3. Known Issues & Active Action Items

Triage of I&T DAG run `EcostressDAG_Col3.46000.0802.20261116T001911117` (807 logs scanned) and review of the current `v1.18.0` codebase identified the following active issues:

| Tracking ID | Severity | Component | Description & Root Cause | Status |
| :--- | :--- | :--- | :--- | :--- |
| **`ECOv003-L2T-STARS` #94** | **Bug (High)** | `process_STARS_product.py` | **Parallel worker race condition on shared posterior directory:** `posterior_tile_date_directory` is shared across concurrent runs (`model_directory/<tile>/<date_UTC>`). When two workers process different scenes on the same tile/date, Worker A's `REMOVE_POSTERIOR = True` cleanup deletes intermediate posterior `.tif` files while Worker B is between `granule.write_zip()` and the post-zip `Raster.open(...).to_geotiff(...)` re-write step (`OSError: raster file not found`, seen on tile `31UDT`). | **Open** — Scope intermediate posterior files under a per-granule directory. |
| **`ECOv003-L2T-STARS` #95** | **Logging (Medium)** | `process_julia_data_fusion.py` | **Unlogged Julia subprocess errors:** `subprocess.run(command, check=False, env=julia_env)` does not capture `stdout`/`stderr`, leaving legacy `--backend julia` exit code 1 failures without a traceback in the PGE `.log` file (36 occurrences in I&T). | **Open** — Capture and log Julia `stdout`/`stderr` on non-zero exit codes. |
| **`ECOv003-L2T-STARS` #96** | **Operations (High)** | Container & `/runtime_ancillary` | **Pre-`v1.18.0` I&T image & corrupted `.nc4` cache:** The I&T run executed an older build prior to `v1.18.0` (hitting legacy Julia crashes, `VCD43NRT` `NBAR_I1.temp.tif` collisions, and `LandFilter` `[ERROR]` logs) and left truncated `GEOS.fp.asm.tavg3_2d_aer_Nx.*.nc4` files in `GEOS5FP_download/` from `portal.nccs.nasa.gov` `SSLEOFError` / `IncompleteRead` dropouts. | **Open (Ops)** — Deploy `>=1.18.0` container, purge truncated `.nc4` files, and re-queue failed tasks. |
| **Container `Dockerfile` Alignment** | **Packaging (Medium)** | `Dockerfile` & `smoke_test.py` | **Debian `apt` GDAL vs. Conda-Forge GDAL:** `ECOv003-L2T-STARS`'s standalone `Dockerfile` uses `python:3.12-bookworm` + `apt` `libgdal-dev` without explicit `GDAL_DRIVER_PATH` / HDF5/NetCDF4 plugin wiring, unlike `ECOv003-L3T-L4T-JET`'s multi-stage `micromamba` + `conda-forge` (`libgdal-netcdf`, `libgdal-hdf5`) runtime. | **Open** — Align `Dockerfile` and `smoke_test.py` with `ECOv003-L3T-L4T-JET` (`v1.22.1`). |
| **`ECOv003-L3T-L4T-JET` #88** | **Downstream Bug** | `JET3` / `ECOv003-L3T-L4T-JET` | **Deprecated `GEOS5FPConnection` calls (`wind_speed`, `Td_C`):** Observed in I&T logs on tiles `32TPS` and `32TPT`. Already resolved in `JET3 v3.1.1` and `ECOv003-L3T-L4T-JET v1.22.1`; awaiting container rebuild in `ecostress-level-2-3-4`. | **Fixed in code; awaiting container deploy** |
| **External NASA Service Outages** | **Transient (External)** | `portal.nccs.nasa.gov` & CMR | Network unreachable (`Errno 101`), `SSLEOFError`, HTTP `503` on GEOS-5 FP AOT downloads, and HTTP `504 Gateway Time-out` on CMR `VNP09GA` queries. Mapped to retryable exit codes `14` (`AUXILIARY_SERVER_UNREACHABLE`), `15` (`AUXILIARY_LATENCY`), and `16` (`DOWNLOAD_FAILED`). | **Handled by exit codes; retryable** |