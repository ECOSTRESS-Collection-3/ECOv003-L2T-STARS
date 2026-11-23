
# ECOv003-L2T-STARS I&T Error Log Analysis Report

* **Input DAG Directory:** `EcostressDAG_Col3.46000.0802.20261116T001911117`
* **Output Error Directory:** `EcostressDAG_Col3.46000.0802.20261116T001911117-error`
* **Log Files Scanned:** 807
* **Unique Issue Signatures:** 51 (755 Errors, 8,436 Warnings)

---

## Executive Summary

All 51 unique error and warning signatures scraped from the I&T run logs map cleanly to **6 root causes** across external data services, concurrency collisions on shared storage, an older pre-Rust container image, and one unrelated downstream PGE (`ECOv003-L3T-L4T-JET`).

| Category | Issue IDs | Severity | Status in Current Codebase | Recommended Action |
| :--- | :--- | :--- | :--- | :--- |
| **1. GEOS-5 FP Outages & Corrupted Cache** | `#1`, `#7–#10`, `#13–#18`, `#27`, `#35–#51` | Error / Warning | Handled (Exit Codes `15`/`16`) | Purge truncated `.nc4` files in `GEOS5FP_download/` and retry DAG tasks. |
| **2. Legacy Julia Backend & Posterior File Race** | `#3`, `#12` | Error | `#3` Replaced by Rust; `#12` Open | Deploy Rust backend (`--backend rust`) and isolate per-granule posterior directories. |
| **3. VCD43NRT Concurrent Directory Collisions** | `#11`, `#19`, `#22`, `#24`, `#30`, `#31` | Error / Warning | **Fixed** in `L2T_STARS.py` | Deploy updated `ECOv003-L2T-STARS` image containing `VCD43NRT_staging_directory`. |
| **4. NASA CMR 504 Gateway Timeouts** | `#5`, `#6` | Error | Handled (Exit Code `14`) | Re-run failed tasks via workflow orchestrator retry policy. |
| **5. Non-Land Tile Logging Level** | `#2` | Error (Historical) | **Fixed** in `L2T_STARS.py` | Deploy updated image (`LandFilter` now logs at `INFO` level). |
| **6. Unrelated PGE (`ECOv003-L3T-L4T-JET`)** | `#4`, `#32–#34` | Error / Warning | Out of Scope (`JET3` repo) | Update `GEOS5FP` method names (`wind_speed_mps`, dewpoint) and mount `.netrc` in JET. |

---

## Detailed Root-Cause Breakdown

### 1. GEOS-5 FP Infrastructure Outages & Corrupted NetCDF Cache
* **Issues:** `#1` (623 errors across 23 logs), `#7–#10`, `#13–#18`, `#27`, `#35–#51`
* **Symptoms:**
  * `FailedGEOS5FPDownload` / `AuxiliaryDownloadFailed: unable to retrieve AOT from GEOS5-FP for VCD43NRT`
  * `SSLEOFError: [SSL: UNEXPECTED_EOF_WHILE_READING]` and `[Errno 101] Network is unreachable` against `portal.nccs.nasa.gov`
  * `503 Server Error: Service Unavailable` and `IncompleteRead` stream truncations
  * `Unable to open file as NetCDF ... not recognized as being in a supported file format`
* **Root Cause:** Transient network instability and TLS disconnects on `portal.nccs.nasa.gov` interrupted downloads of `GEOS.fp.asm.tavg3_2d_aer_Nx.*.V01.nc4`. Partially written files on shared disk failed NetCDF validation and triggered 3x retry loops (`30s` backoff) across the spin-up window.
* **Codebase Status:** **Handled.** `generate_STARS_inputs.py` tolerates individual missing days when at least one valid coarse NDVI and albedo raster succeeds across the spin-up window, and exits cleanly with `AuxiliaryLatency` (`15`) or `DownloadFailed` (`16`) if an entire window fails.
* **Remediation:**
  1. Remove any truncated or invalid `.nc4` files in `/runtime_ancillary/L2T_STARS_SOURCES/GEOS5FP_download/` before re-running.
  2. Retry the 23 failed DAG jobs now that `portal.nccs.nasa.gov` connectivity has stabilized.

---

### 2. Legacy Julia Backend Failures & Shared-Storage Posterior Race Condition
* **Issues:** `#3` (36 errors across 36 logs), `#12` (2 errors across 2 logs)
* **Symptoms:**
  * **Issue #3:** `RuntimeError: Julia data fusion failed for NDVI at tile <MGRS_TILE> with exit code 1`
  * **Issue #12:** `OSError: raster file not found: /runtime_ancillary/L2T_STARS_MODEL/31UDT/2026-08-16/STARS_NDVI_2026-08-16_31UDT_70m.tif` at `process_STARS_product.py:492`
* **Root Cause:**
  * **Issue #3:** The I&T run executed an older image using the legacy Julia fusion subprocess (`process_julia_data_fusion.py`), which was susceptible to Julia/GDAL shared-library conflicts and did not capture Julia stderr into the Python log.
  * **Issue #12:** In `process_STARS_product.py`, intermediate posterior rasters are written to `model_directory/<tile>/<date_UTC>/`. When two workers concurrently process different orbits/scenes covering the same `<tile>` and `<date_UTC>` on shared storage (`/runtime_ancillary/L2T_STARS_MODEL`), Worker A finishes `granule.write_zip()` and deletes the posterior files (`REMOVE_POSTERIOR = True`) while Worker B is still between `write_zip()` and `Raster.open(posterior_NDVI_filename)` (line 492).
* **Codebase Status:**
  * **Issue #3:** **Resolved** by migrating the default fusion engine to the compiled Rust/PyO3 kernel (`FUSION_BACKEND = "rust"` in `constants.py`).
  * **Issue #12:** **Open.** Still affects concurrent runs sharing `L2T_STARS_MODEL` when `REMOVE_POSTERIOR = True`.
* **Remediation:**
  1. Run I&T with the new Rust-backed build (`--backend rust`, now default).
  2. Scope `posterior_tile_date_directory` in `process_STARS_product.py` by `granule_ID` (or stage posteriors inside `working_directory` / a per-run subdirectory) so concurrent workers cannot delete each other's intermediate files.

---

### 3. VCD43NRT Concurrent Worker Directory Collisions
* **Issues:** `#11` (2 errors), `#19` (280 warnings), `#22` (144 warnings), `#24` (126 warnings), `#30` (16 warnings), `#31` (10 warnings)
* **Symptoms:**
  * `FileNotFoundError: [Errno 2] No such file or directory: '.../VCD43NRT_A2026228_h18v04_JPSS_NBAR_I1.temp.tif'` inside `Image.to_COG()`
  * `removing stale VCD43NRT granule output directory before regeneration` / `removing incomplete VCD43NRT granule output directory before promotion`
* **Root Cause:** Multiple parallel workers generating the same MODLAND tile (`h18v03`, `h18v04`, `h19v04`) simultaneously wrote into `VCD43NRT_products/`. One worker cleaned up or promoted the directory while another worker was still deleting temporary COG artifacts.
* **Codebase Status:** **Fixed.** `L2T_STARS.py` now initializes `VCD43NRT` with an isolated `VCD43NRT_staging_directory` and `fallback_mode=True` (verified in `tests/test_VCD43NRT_upstream.py`).
* **Remediation:** Deploy the updated `ECOv003-L2T-STARS` container image.

---

### 4. NASA CMR 504 Gateway Timeouts & Downstream Abort
* **Issues:** `#5` (4 errors), `#6` (4 errors)
* **Symptoms:**
  * `HTTPError: 504 Server Error: Gateway Time-out` from `cmr.earthdata.nasa.gov/search/granules.umm_json`
  * `L2T_STARS failed for tile 32UQV with exit code 14. Aborting.`
* **Root Cause:** Transient `504 Gateway Time-out` responses from NASA CMR during `VCD43NRT_connection.prefetch_VNP09GA()` raised `CMRServerUnreachable`, which `L2T_STARS` mapped to exit code `14` (`AUXILIARY_SERVER_UNREACHABLE`), causing `ECOv003_DL` to abort and bubble up exit code `14`.
* **Codebase Status:** **Working as designed.** Exit code `14` properly signals the workflow orchestrator that an upstream data service was temporarily unreachable and the job should be retried.
* **Remediation:** Re-queue jobs that exited with code `14`.

---

### 5. Non-Land Tile Filtering Logged as `ERROR`
* **Issues:** `#2` (70 occurrences across 35 MGRS tiles)
* **Symptoms:**
  * `[ERROR] Sentinel tile 29UPS is not on land. Skipping processing.`
* **Root Cause:** Older builds logged `LandFilter` exceptions with `logger.exception()`, polluting error metrics for expected water/ocean tile skips (exit code `LAND_FILTER`).
* **Codebase Status:** **Fixed.** `L2T_STARS.py` now catches `LandFilter` separately and logs at `INFO` level (`logger.info(exception)`), verified by `tests/test_land_filter_logging.py`.
* **Remediation:** Deploy the updated `ECOv003-L2T-STARS` container image.

---

### 6. Errors Originating from `ECOv003-L3T-L4T-JET` (Unrelated PGE)
* **Issues:** `#4` (6 errors), `#32` (6 warnings), `#33` (6 warnings), `#34` (6 warnings)
* **Symptoms:**
  * `AttributeError: 'GEOS5FPConnection' object has no attribute 'Td_C'`
  * `AttributeError: 'GEOS5FPConnection' object has no attribute 'wind_speed'. Did you mean: 'wind_speed_mps'?` in `/opt/venv/lib/python3.12/site-packages/JET3/JET.py`
  * `netrc credentials not found for daac.ornl.gov` / `urs.earthdata.nasa.gov`
* **Root Cause:** These log entries were scraped from `ECOv003-L3T-L4T-JET` runs sharing the DAG directory, where `JET3` is calling deprecated `GEOS5FP` method names (`wind_speed`, `Td_C`) and running without mounted `.netrc` credentials.
* **Remediation:** Address in the `JET3` / `ECOv003-L3T-L4T-JET` repository and container configuration (not a defect in `ECOv003-L2T-STARS`).

---

## Informational / Expected Cloud-Cover Warnings (No Action Required)

The following warnings reflect normal data-availability gaps due to cloud cover or orbital revisit schedules and are handled gracefully by the pipeline:

* **Issues `#20`, `#21`:** `Sentinel is not available at tile <MGRS_TILE> on <DATE>` (260 warnings) and `Landsat is not available at tile <MGRS_TILE> on <DATE>` (200 warnings).
* **Issues `#25`, `#26`, `#28`, `#29`:** `HLS NDVI/albedo is not available on <DATE>` (284 warnings combined).
* **Issue `#23`:** `One or more required prior (mean/UQ) files are missing. Prior will not be used.` (140 warnings) — falls back cleanly to cold-start prior initialization.

---

## Action Checklist for Next I&T Run

1. [ ] **Build & deploy latest `ECOv003-L2T-STARS`** (with Rust fusion backend enabled by default and `VCD43NRT_staging_directory` isolation).
2. [ ] **Patch `process_STARS_product.py`** to isolate posterior intermediate files per `granule_ID` (eliminating Issue `#12` on shared `L2T_STARS_MODEL` storage).
3. [ ] **Purge corrupted `.nc4` files** in `/runtime_ancillary/L2T_STARS_SOURCES/GEOS5FP_download/` (e.g., via `ncdump -h` or `h5py` validation check).
4. [ ] **Update `JET3` (`ECOv003-L3T-L4T-JET`)** for `GEOS5FP` API compatibility (`wind_speed_mps`, dewpoint method) and Earthdata/ORNL `.netrc` credentials.