# `ECOv003-L2T-STARS` Known Issues & DAG Log Triage Report

- **Date:** November 23, 2026
- **DAG Run Analyzed:** `EcostressDAG_Col3.46000.0802.20261116T001911117`
- **Log Scope:** 807 DAG log files scanned (51 unique signatures, 755 errors, 8,436 warnings)

## Summary Table

| Issue # | Tracking | Severity | Signature | Status |
| :--- | :--- | :--- | :--- | :--- |
| **#12** | `ECOv003-L2T-STARS#94` | `ERROR` | `OSError: raster file not found: .../L2T_STARS_MODEL/<TILE>/<DATE>/STARS_NDVI_<DATE>_<TILE>_70m.tif` | **Fixed in `v1.19.0`** (posterior outputs isolated per `granule_ID`) |
| **#3** | `ECOv003-L2T-STARS#95` | `ERROR` | `Julia data fusion failed for NDVI at tile <TILE> with exit code 1` | **Fixed in `v1.19.0`** (`stdout`/`stderr` captured & logged; default backend is Rust) |
| **#1, #7–#18, #27, #35–#51** | `ECOv003-L2T-STARS#96` | `ERROR` / `WARNING` | GEOS-5 FP AOT download dropouts (`SSLEOFError`, `503`, `IncompleteRead`) & truncated `.nc4` validation errors | **Ops Action:** Deploy `>=1.19.0` (`micromamba` GDAL plugins), purge truncated `.nc4` cache, re-queue tasks |
| **#11, #19, #22, #24, #30, #31** | `ECOv003-L2T-STARS#96` | `ERROR` / `WARNING` | `VCD43NRT` multi-worker collisions (`NBAR_I1.temp.tif` `FileNotFoundError`) | **Fixed in `v1.18.0`** (`VCD43NRT_staging_directory` + `fallback_mode=True`) |
| **#2** | `v1.18.0` | `INFO` | `Sentinel tile <TILE> is not on land. Skipping processing.` | **Fixed in `v1.18.0`** (logged at `[INFO]`, exit code `11`) |
| **#4, #32–#34** | `ECOv003-L3T-L4T-JET#88` | `ERROR` / `WARNING` | `JET3` deprecated `GEOS5FPConnection.wind_speed` / `Td_C` & `.netrc` warnings | **Fixed in `JET3 v3.1.1` / `ECOv003-L3T-L4T-JET v1.22.1`** |
