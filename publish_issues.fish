# Issue 1: Isolate intermediate posterior directory per granule
printf '%s\n' \
'### Summary' \
'In I&T run `EcostressDAG_Col3.46000.0802.20261116T001911117`, `process_STARS_product.py` failed with `OSError: raster file not found` when re-writing posterior GeoTIFFs after `granule.write_zip()` (affecting tile `31UDT` on `2026-08-16`).' \
'' \
'### Traceback' \
'```text' \
'File ".../ECOv003_L2T_STARS/process_STARS_product.py", line 492, in process_STARS_product' \
'  Raster.open(posterior_NDVI_filename, cmap=NDVI_COLORMAP).to_geotiff(' \
'File ".../rasters/raster.py", line 719, in open' \
'  raise IOError(f"raster file not found: {filename}")' \
'OSError: raster file not found: /runtime_ancillary/L2T_STARS_MODEL/31UDT/2026-08-16/STARS_NDVI_2026-08-16_31UDT_70m.tif' \
'```' \
'' \
'### Root Cause' \
'`posterior_tile_date_directory` is derived solely from `model_directory / tile / date_UTC` (`generate_model_state_tile_date_directory.py`). When two concurrent DAG tasks process different scenes covering the same `(tile, date_UTC)` on shared storage, Worker A hits the cleanup block (`REMOVE_POSTERIOR = True`, lines 532–546) and deletes the intermediate posterior GeoTIFFs while Worker B is still between `granule.write_zip()` and the post-zip `Raster.open(...).to_geotiff(...)` re-write step.' \
'' \
'### Proposed Fix' \
'1. Scope intermediate posterior outputs in `process_STARS_product.py` under a granule-unique directory (e.g., `working_directory / "posteriors" / granule_ID` or `model_directory / tile / date_UTC / granule_ID`) rather than a shared `tile/date_UTC` path.' \
'2. Add a unit test simulating concurrent runs on the same `(tile, date_UTC)` with `remove_posterior=True` to verify no file deletion collisions occur.' \
| gh issue create --repo ECOSTRESS-Collection-3/ECOv003-L2T-STARS \
  --title "Isolate intermediate posterior directory per granule to prevent parallel worker OSError (Issue #12)" \
  --body-file -

# Issue 2: Capture Julia subprocess stdout/stderr on failure
printf '%s\n' \
'### Summary' \
'During I&T run `EcostressDAG_Col3.46000.0802.20261116T001911117`, 36 tasks failed with:' \
'```text' \
'RuntimeError: Julia data fusion failed for NDVI at tile 29UPT with exit code 1' \
'```' \
'Because `process_julia_data_fusion.py` invokes `subprocess.run(command, check=False)` without capturing output, the underlying Julia stack trace is not recorded in the PGE log file.' \
'' \
'### Root Cause' \
'In `ECOv003_L2T_STARS/process_julia_data_fusion.py` (line 126):' \
'```python' \
'result = subprocess.run(command, check=False, env=julia_env)' \
'```' \
'When `--backend julia` is used in non-interactive DAG environments, console output may be truncated or separated from the structured PGE log.' \
'' \
'### Proposed Fix' \
'1. Stream or capture `stdout`/`stderr` in `process_julia_data_fusion.py` and emit the tail of the output via `logger.error(...)` before raising `RuntimeError` when `result.returncode != 0`.' \
'2. Ensure I&T DAG workflows use the default Rust backend (`--backend rust`) for production runs.' \
| gh issue create --repo ECOSTRESS-Collection-3/ECOv003-L2T-STARS \
  --title "Capture and log Julia subprocess output when process_julia_data_fusion fails" \
  --body-file -

# Issue 3: Upgrade I&T container & purge corrupted GEOS5FP .nc4 cache
printf '%s\n' \
'### Summary' \
'Analysis of `EcostressDAG_Col3.46000.0802.20261116T001911117` (807 logs) showed multiple failures caused by running an older `ECOv003-L2T-STARS` build and cached truncated GEOS-5 FP NetCDF files.' \
'' \
'### Action Items' \
'1. **Deploy current `ECOv003-L2T-STARS` wheel** to the I&T container image:' \
'   - Switches default fusion backend to Rust (`FUSION_BACKEND = "rust"`), eliminating the 36 legacy Julia exit code 1 failures.' \
'   - Enables `VCD43NRT_staging_directory` and `fallback_mode=True`, eliminating multi-worker directory collisions (`NBAR_I1.temp.tif` `FileNotFoundError` and stale VCD43NRT directory warnings).' \
'   - Downgrades non-land `LandFilter` skips (70 occurrences) from `[ERROR]` to `[INFO]`.' \
'2. **Purge truncated `.nc4` files** in `/runtime_ancillary/L2T_STARS_SOURCES/GEOS5FP_download/` left behind by `portal.nccs.nasa.gov` `SSLEOFError` / `IncompleteRead` dropouts (e.g., `GEOS.fp.asm.tavg3_2d_aer_Nx.20260809_0730.V01.nc4` and other files failing NetCDF validation).' \
'3. **Re-queue failed DAG tasks** once `portal.nccs.nasa.gov` and CMR (`504 Gateway Time-out`) recover.' \
| gh issue create --repo ECOSTRESS-Collection-3/ECOv003-L2T-STARS \
  --title "Deploy updated ECOv003-L2T-STARS wheel (Rust backend + VCD43NRT staging) and purge truncated GEOS5FP .nc4 files" \
  --body-file -

# Issue 4: Fix GEOS5FPConnection attribute names & .netrc mount in JET
printf '%s\n' \
'### Summary' \
'I&T logs from `EcostressDAG_Col3.46000.0802.20261116T001911117` captured 6 failures in `ECOv003-L3T-L4T-JET` (`JET3/JET.py`) on tiles `32TPS` and `32TPT` due to outdated `GEOS5FPConnection` method names and missing `.netrc` credentials.' \
'' \
'### Tracebacks & Errors' \
'```text' \
'[2026-11-20 02:18:18 WARNING] netrc credentials not found for daac.ornl.gov' \
'[2026-11-20 02:18:18 WARNING] netrc credentials not found for urs.earthdata.nasa.gov' \
"[2026-11-20 02:18:59 ERROR] 'GEOS5FPConnection' object has no attribute 'Td_C'" \
'[2026-11-20 02:18:59 WARNING] unable to sharpen meteorology' \
'  File "/opt/venv/lib/python3.12/site-packages/JET3/JET.py", line 283, in JET' \
'    wind_speed_mps = GEOS5FP_connection.wind_speed(time_UTC=time_UTC, geometry=geometry, resampling=downsampling)' \
"AttributeError: 'GEOS5FPConnection' object has no attribute 'wind_speed'. Did you mean: 'wind_speed_mps'?" \
'```' \
'' \
'### Proposed Fix' \
'1. In `JET3/JET.py` (line 283), replace `GEOS5FP_connection.wind_speed(...)` with `GEOS5FP_connection.wind_speed_mps(...)`.' \
'2. Update `GEOS5FP_connection.Td_C(...)` calls in `JET3` to match the current `GEOS5FP` dewpoint API.' \
'3. Verify `.netrc` credentials for `urs.earthdata.nasa.gov` and `daac.ornl.gov` (or Earthdata environment variables) are mounted into the `ECOv003-L3T-L4T-JET` runtime environment.' \
| gh issue create --repo ECOSTRESS-Collection-3/ECOv003-L3T-L4T-JET \
  --title "Update deprecated GEOS5FPConnection.wind_speed / Td_C calls and verify .netrc credentials in JET" \
  --body-file -