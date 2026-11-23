# `ECOv003-L2T-STARS` Known Issues & DAG Log Triage Report

- **Date:** November 23, 2026
- **DAG Run Analyzed:** `EcostressDAG_Col3.46000.0802.20261116T001911117`
- **Log Scope:** 807 total DAG log files scanned (51 unique issue signatures; 755 errors, 8,436 warnings)
- **Affected Packages:** `ECOv003-L2T-STARS` (`v1.18.0`), `VCD43NRT` (`~=1.6.0`), `GEOS5FP` (`~=2.24.0`), `modland` (`~=1.2.0`)

---

## 1. Executive Summary

Triage of the 51 unique error and warning signatures scraped across 807 I&T DAG logs isolates **47 issues** to `ECOv003-L2T-STARS` and its upstream ancillary dependencies (`VCD43NRT`, `GEOS5FP`, `modland`), while the remaining **4 issues** (`#4`, `#32–#34`) originated downstream in `ECOv003-L3T-L4T-JET` (`JET3 v3.1.0`).

Across `ECOv003-L2T-STARS`, the findings fall into **three categories**:

1. **Resolved in `ECOv003-L2T-STARS v1.18.0` (Awaiting I&T Container Deployment — [Issue #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96)):**
   - Legacy Julia fusion failures (`exit code 1`, 36 logs) replaced by the compiled Rust/PyO3 kernel (`FUSION_BACKEND = "rust"`).
   - Multi-worker `VCD43NRT` directory collisions (`NBAR_I1.temp.tif` `FileNotFoundError` and stale directory warnings) resolved via `VCD43NRT_staging_directory` isolation and `fallback_mode=True`.
   - Non-land `LandFilter` skips (70 occurrences across 35 MGRS tiles) downgraded from `[ERROR]` to `[INFO]`.
2. **Open Code & Packaging Items in `ECOv003-L2T-STARS`:**
   - **[Issue #94](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/94):** Concurrent worker race condition on shared `model_directory/<tile>/<date_UTC>` when `REMOVE_POSTERIOR = True` (`OSError: raster file not found` at `process_STARS_product.py:492`).
   - **[Issue #95](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/95):** Uncaptured Julia `stdout`/`stderr` in `process_julia_data_fusion.py` when `--backend julia` exits non-zero.
   - **Container `Dockerfile` & Smoke-Test Drift:** Standalone `Dockerfile` still uses Debian `apt` `libgdal-dev` rather than `JET`'s `micromamba` + `conda-forge` (`libgdal-netcdf`, `libgdal-hdf5`) runtime with explicit `GDAL_DRIVER_PATH` / HDF5 plugin assertions.
3. **External Infrastructure Outages & Cached Truncated NetCDF Files ([Issue #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96)):**
   - Transient network dropouts (`Errno 101`), `SSLEOFError`, HTTP `503`s, and `IncompleteRead` stream truncations on `portal.nccs.nasa.gov` left corrupted `.nc4` files in `GEOS5FP_download/`, while NASA CMR returned `504 Gateway Time-out` on `VNP09GA` queries.

---

## 2. STARS-Specific Issues Summary

| Tracking / Log Issue # | Severity | Log Signature | Occurrences | Status |
| :--- | :--- | :--- | :--- | :--- |
| **[GH #94](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/94)** / Log `#12` | `ERROR` (Bug) | `OSError: raster file not found: /runtime_ancillary/L2T_STARS_MODEL/<TILE>/<DATE>/STARS_NDVI_<DATE>_<TILE>_70m.tif` | 2 across 2 logs (`31UDT`) | **Open** — Needs per-granule posterior directory isolation |
| **[GH #95](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/95)** / Log `#3` | `ERROR` (Logging) | `RuntimeError: Julia data fusion failed for NDVI at tile <MGRS_TILE> with exit code 1` | 36 across 36 logs (18 tiles) | **Mitigated by Rust default**; open to capture Julia stderr |
| **[GH #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96)** / Log `#11, #19, #22, #24, #30, #31` | `ERROR` / `WARNING` | `FileNotFoundError: ...VCD43NRT_A<DOY>_<TILE>_JPSS_NBAR_I1.temp.tif` & `removing stale VCD43NRT granule output directory` | 2 errors, 576 warnings | **Fixed in `v1.18.0`** (`VCD43NRT_staging_directory`); deploy container |
| **[GH #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96)** / Log `#2` | `ERROR` (Historical) | `Sentinel tile <MGRS_TILE> is not on land. Skipping processing.` | 70 across 70 logs (35 tiles) | **Fixed in `v1.18.0`** (now logged at `INFO`); deploy container |
| **[GH #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96)** / Log `#1, #7–#10, #13–#18, #27, #35–#51` | `ERROR` / `WARNING` | `unable to retrieve AOT from GEOS5-FP for VCD43NRT` / `SSLEOFError` / `IncompleteRead` / `Unable to open file as NetCDF` | 627 errors, 6,665 warnings | **Handled (Exit Codes `15`/`16`)**; purge truncated `.nc4` files & retry |
| Log `#5, #6` | `ERROR` (Transient) | `504 Server Error: Gateway Time-out` (`cmr.earthdata.nasa.gov`) / `L2T_STARS failed for tile <TILE> with exit code 14` | 4 errors each (`32UQV`) | **Handled (Exit Code `14`)**; retryable via orchestrator |
| Log `#20, #21, #23, #25, #26, #28, #29` | `WARNING` (Expected) | `Sentinel/Landsat is not available`, `HLS NDVI/albedo is not available`, `One or more required prior (mean/UQ) files are missing` | 884 warnings | **Expected** cloud-cover / cold-start fallback behavior |

---

## 3. Detailed Issue Analysis

### 3.1. [Issue #94](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/94) (Open Bug): Parallel Worker Race Condition on Shared Posterior Directory

- **Severity:** High (`OSError` crash after ZIP creation)
- **Occurrences:** 2 across 2 log files (tile `31UDT`, date `2026-08-16`)
- **Representative Traceback:**
  ```text
  [2026-11-18 15:43:56 ERROR] raster file not found: /runtime_ancillary/L2T_STARS_MODEL/31UDT/2026-08-16/STARS_NDVI_2026-08-16_31UDT_70m.tif
  Traceback (most recent call last):
    File "/opt/venv/lib/python3.12/site-packages/ECOv003_L2T_STARS/L2T_STARS.py", line 448, in L2T_STARS
      process_STARS_product(
    File "/opt/venv/lib/python3.12/site-packages/ECOv003_L2T_STARS/process_STARS_product.py", line 492, in process_STARS_product
      Raster.open(posterior_NDVI_filename, cmap=NDVI_COLORMAP).to_geotiff(
    File "/opt/venv/lib/python3.12/site-packages/rasters/raster.py", line 719, in open
      raise IOError(f"raster file not found: {filename}")
  OSError: raster file not found: /runtime_ancillary/L2T_STARS_MODEL/31UDT/2026-08-16/STARS_NDVI_2026-08-16_31UDT_70m.tif
  ```
- **Root Cause:**
  - `process_STARS_product.py` writes intermediate posterior GeoTIFFs into `model_directory/<tile>/<date_UTC>/` (`generate_model_state_tile_date_directory.py`).
  - When two concurrent DAG tasks process different orbits/scenes covering the same `(tile, date_UTC)` on shared storage (`/runtime_ancillary/L2T_STARS_MODEL`), Worker A completes `granule.write_zip()` and executes the cleanup block (`REMOVE_POSTERIOR = True`), deleting the intermediate posterior files while Worker B is still between `granule.write_zip()` and the post-zip `Raster.open(...).to_geotiff(...)` re-write step.
- **Recommended Fix:**
  - Scope intermediate posterior rasters under a granule-unique directory (e.g., `working_directory / "posteriors" / granule_ID` or `model_directory / tile / date_UTC / granule_ID`) and add a concurrency regression test.

---

### 3.2. [Issue #95](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/95) (Open Enhancement) & Legacy Julia Backend Failures

- **Severity:** Medium (36 legacy Julia failures in I&T; missing stderr diagnostics in PGE log)
- **Occurrences:** 36 across 36 log files (18 tiles: `29UPT`, `29UPU`, `29UPV`, `29UQS`, `29UQU`, `30UUB`, `30UUD`, `30UVA`, `30UVB`, `30UVD`, `30UVV`, `32TPS`, `32TPT`, `32UMU`, `32UPU`, `32UQV`, `33TWL`, `33TXK`)
- **Representative Traceback:**
  ```text
  [2026-11-18 17:22:36 ERROR] Julia data fusion failed for NDVI at tile 29UPT with exit code 1
  Traceback (most recent call last):
    File "/opt/venv/lib/python3.12/site-packages/ECOv003_L2T_STARS/process_julia_data_fusion.py", line 129, in process_julia_data_fusion
      raise RuntimeError(
  RuntimeError: Julia data fusion failed for NDVI at tile 29UPT with exit code 1
  ```
- **Root Cause:**
  - The I&T run executed a pre-`v1.18.0` container using the legacy Julia data-fusion subprocess (`process_julia_data_fusion.py`), which was vulnerable to Julia/GDAL shared-library conflicts.
  - Because `subprocess.run(command, check=False, env=julia_env)` does not capture `stdout`/`stderr`, the underlying Julia traceback is omitted from the PGE `.log` file.
- **Recommended Fix:**
  - Production DAGs should run the default Rust backend (`FUSION_BACKEND = "rust"`, introduced in `v1.18.0`).
  - Capture `stdout`/`stderr` in `process_julia_data_fusion.py` and log the error output via `logger.error(...)` whenever `result.returncode != 0`.

---

### 3.3. [Issue #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96) (Fixed in `v1.18.0`, Awaiting Deploy): `VCD43NRT` Directory Collisions & `LandFilter` Error Logging

- **Severity:** High in pre-`v1.18.0` builds; **Resolved in `v1.18.0`**
- **Occurrences:**
  - `FileNotFoundError` on `...NBAR_I1.temp.tif`: 2 errors across 2 logs (`h18v04`)
  - `removing stale/incomplete VCD43NRT granule output directory`: 576 warnings across 27 logs (`h18v03`, `h18v04`, `h19v03`, `h19v04`)
  - `Sentinel tile <TILE> is not on land`: 70 `[ERROR]` entries across 70 logs (35 tiles)
- **Root Cause:**
  - Concurrent workers generating the same MODLAND tile collided in `VCD43NRT_products/` while promoting/cleaning temporary COG files.
  - `L2T_STARS.py` previously logged `LandFilter` exceptions with `logger.exception()`.
- **Resolution:**
  - `ECOv003-L2T-STARS v1.18.0` passes `VCD43NRT_staging_directory` and `fallback_mode=True` to `VCD43NRT` and logs `LandFilter` at `INFO` level (`tests/test_VCD43NRT_upstream.py`, `tests/test_land_filter_logging.py`). Deploy `>=1.18.0` to I&T.

---

### 3.4. [Issue #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96) (External / Ops): GEOS-5 FP Outages & Corrupted `.nc4` Cache

- **Severity:** External service outage + stale corrupted cache files on shared storage
- **Occurrences:** 623 `unable to retrieve AOT from GEOS5-FP for VCD43NRT` errors across 23 logs; 4 `SSLEOFError` errors; 1,904 NetCDF validation warnings
- **Representative Log Snippet:**
  ```text
  [2026-11-16 15:40:28 WARNING]   validation error: Unable to open file as NetCDF: '/runtime_ancillary/L2T_STARS_SOURCES/GEOS5FP_download/2026.08.09/GEOS.fp.asm.tavg3_2d_aer_Nx.20260809_0730.V01.nc4' not recognized as being in a supported file format.
  [2026-11-16 15:41:37 ERROR] unable to retrieve AOT from GEOS5-FP for VCD43NRT
  ```
- **Root Cause:**
  - `portal.nccs.nasa.gov` experienced network dropouts (`[Errno 101] Network is unreachable`), TLS `SSLEOFError` disconnects, HTTP `503`s, and `IncompleteRead` stream truncations while serving `GEOS.fp.asm.tavg3_2d_aer_Nx.*.V01.nc4`.
  - Partially downloaded files persisted on disk, failing NetCDF validation on subsequent attempts until `GEOS5FP` exhausted its retries and `generate_STARS_inputs.py` raised `DownloadFailed` (`exit code 16`) or `AuxiliaryLatency` (`exit code 15`).
- **Operational Action:**
  - Purge truncated/unreadable `.nc4` files under `/runtime_ancillary/L2T_STARS_SOURCES/GEOS5FP_download/` and re-queue the 23 affected DAG tasks.

---

### 3.5. Container `Dockerfile` & Smoke-Test Drift vs. `ECOv003-L3T-L4T-JET`

- **Severity:** Medium (packaging consistency)
- **Root Cause:**
  - `ECOv003-L3T-L4T-JET` (`v1.22.1`) uses a 3-stage `mambaorg/micromamba:ubuntu24.04` `Dockerfile` (`toolchain` → `build` → `runtime`) with `conda-forge` `libgdal-netcdf` and `libgdal-hdf5`, explicit `GDAL_DRIVER_PATH="/opt/venv/lib/gdalplugins"`, `GDAL_DATA`, and `PROJ_DATA`, and upstream API/driver checks in `smoke_test.py`.
  - `ECOv003-L2T-STARS`'s standalone `Dockerfile` still uses `python:3.12-bookworm` + `apt-get install libgdal-dev` without explicit `GDAL_DRIVER_PATH` / NetCDF4 / HDF5 driver verification in `smoke_test.py`.
- **Recommended Fix:**
  - Align `ECOv003-L2T-STARS/Dockerfile` with `JET`'s `micromamba` multi-stage layout (building `_stars_rust` via `maturin`) and add GDAL NetCDF/HDF5 driver + `VCD43NRT` contract checks to `ECOv003_L2T_STARS/smoke_test.py`.

---

## 4. Downstream Issues Observed in Shared DAG Logs (`ECOv003-L3T-L4T-JET`)

Four signatures in the scraped log bundle originated from `ECOv003-L3T-L4T-JET` (`JET3 v3.1.0`) rather than `ECOv003-L2T-STARS`:

- **Log `#4` & `#34` (`6 errors`, tiles `32TPS`, `32TPT`):** `'GEOS5FPConnection' object has no attribute 'Td_C'` and `AttributeError: 'GEOS5FPConnection' object has no attribute 'wind_speed'` in `JET3/JET.py:283`. **Fixed** in `JET3 v3.1.1` and `ECOv003-L3T-L4T-JET v1.22.1` (`JET3~=3.2.0` pinned; tracked in [ECOv003-L3T-L4T-JET #88](https://github.com/ECOSTRESS-Collection-3/ECOv003-L3T-L4T-JET/issues/88)).
- **Log `#32` & `#33` (`6 warnings each`):** `netrc credentials not found for daac.ornl.gov` / `urs.earthdata.nasa.gov`. Benign when `StaticAncillaryFileGroup/L3T_L4T_STATIC` is pre-cached on `/runtime_ancillary`.

---

## 5. Remediation & Verification Checklist

- [x] **`ECOv003-L2T-STARS v1.18.0`:** Default to compiled Rust fusion backend (`FUSION_BACKEND = "rust"`), isolate `VCD43NRT` staging directories, and log `LandFilter` skips at `INFO` level.
- [ ] **[Issue #94](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/94):** Isolate intermediate posterior rasters under a per-granule directory in `process_STARS_product.py` to prevent concurrent worker deletion races.
- [ ] **[Issue #95](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/95):** Capture and log Julia subprocess `stdout`/`stderr` on non-zero exit codes in `process_julia_data_fusion.py`.
- [ ] **Container & Smoke-Test Alignment:** Standardize `Dockerfile` on `micromamba` + `conda-forge` GDAL (`libgdal-netcdf`, `libgdal-hdf5`) with pinned `GDAL_DRIVER_PATH`, and expand `smoke_test.py` to verify GDAL drivers and `VCD43NRT` interfaces.
- [ ] **[Issue #96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96) (I&T Operations):** Deploy updated `eco-level-2-3-4-application` image (`ECOv003-L2T-STARS>=1.18.0`, `ECOv003-L3T-L4T-JET>=1.22.1`), purge truncated `.nc4` files in `GEOS5FP_download/`, and re-drive failed DAG tiles.