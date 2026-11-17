# `ECOv003-L2T-STARS` Development Plan: Align `ECOv003_DL` (`sources_only=True`) VIIRS Prefetch Error Handling with `VIIRS_GIVEUP_DAYS`

**Date:** 2026-11-16  
**Target Repository:** `ECOv003-L2T-STARS` (`1.16.0`)  
**Affected Files:**  
- `ECOv003_L2T_STARS/retrieve_STARS_sources.py`  
- `tests/test_retrieve_STARS_sources.py` *(new)*  

---

## 1. Problem Summary

In `ECOv003_DL.py`, the Collection 3 Downloader PGE invokes `L2T_STARS(runconfig_filename=..., sources_only=True)` for every land tile in a scene. When `sources_only=True` is active in `L2T_STARS.py` (lines 387–419), execution runs two sequential steps:

1. `retrieve_STARS_sources(...)` — downloads HLS tiles and calls `VCD43NRT_connection.prefetch_VNP09GA(...)` across `[VIIRS_download_start_date, VIIRS_end_date]` (`spinup_days + 16` days before `date_UTC`).
2. `generate_STARS_inputs(...)` — generates the coarse NDVI/albedo rasters across `[VIIRS_start_date, VIIRS_end_date]` and evaluates window-level failure policy:
   - If any missing coarse dates fall within `VIIRS_GIVEUP_DAYS` (`4` days), raise `AuxiliaryLatency` (exit code `15`).
   - Otherwise, if zero coarse NDVI or zero coarse albedo rasters exist across the window, raise `DownloadFailed` (exit code `16`).

### Edge Case
If `VCD43NRT_connection.prefetch_VNP09GA(...)` raises `VCD43NRT.exceptions.VIIRSUnavailableError` directly during Step 1, it currently bypasses `generate_STARS_inputs()` and bubbles straight out to the top-level exception handler in `L2T_STARS.py`, which unconditionally maps `VCD43NRTVIIRSUnavailableError` to `AUXILIARY_LATENCY` (`15`):

- For historical granules older than `VIIRS_GIVEUP_DAYS` (`4` days), `ECOv003_DL` would return retryable exit code `15` (`AUXILIARY_LATENCY`) instead of `16` (`DOWNLOAD_FAILED`).
- If an earlier spin-up day (`VIIRS_download_start_date`) had no VIIRS granule on one mission while the actual fusion window `[VIIRS_start_date, VIIRS_end_date]` has sufficient granules (or fallback missions `JPSS1`/`JPSS2`), `ECOv003_DL` would abort prematurely during prefetch.

---

## 2. Design Principles

1. **Prefetch is an optimization, not a window-level verdict:** `retrieve_STARS_sources()` should defer `VIIRSUnavailableError` classification to `generate_STARS_inputs()`, which owns the `[VIIRS_start_date, VIIRS_end_date]` window and `VIIRS_GIVEUP_DAYS` policy.
2. **Preserve immediate propagation for outages and transfer errors:**
   - `VCD43NRT.exceptions.CMRServerUnreachable` must still propagate immediately to `L2T_STARS.py` $\rightarrow$ `AUXILIARY_SERVER_UNREACHABLE` (`14`).
   - `VCD43NRT.exceptions.DownloadFailed` (including `AuxiliaryDownloadFailed`) must still propagate immediately to `L2T_STARS.py` $\rightarrow$ `DOWNLOAD_FAILED` (`16`).
3. **Keep top-level `L2T_STARS.py` fallback intact:** Retain `VCD43NRTVIIRSUnavailableError` in `L2T_STARS.py`'s `AUXILIARY_LATENCY` (`15`) handler in case any direct `VCD43NRT` call outside `retrieve_STARS_sources()` raises it.

---

## 3. Implementation Plan

### Step 1: Catch & Log `VCD43NRTVIIRSUnavailableError` in `ECOv003_L2T_STARS/retrieve_STARS_sources.py`

Import `VIIRSUnavailableError as VCD43NRTVIIRSUnavailableError` from `VCD43NRT.exceptions` and wrap `VCD43NRT_connection.prefetch_VNP09GA(...)` in a `try ... except VCD43NRTVIIRSUnavailableError` block that logs a warning and allows execution to proceed into `generate_STARS_inputs()`.

```diff
--- a/ECOv003_L2T_STARS/retrieve_STARS_sources.py
+++ b/ECOv003_L2T_STARS/retrieve_STARS_sources.py
@@ -16,6 +16,7 @@ from harmonized_landsat_sentinel import (
 from ECOv003_exit_codes import *
 
 from VCD43NRT import VCD43NRT
+from VCD43NRT.exceptions import VIIRSUnavailableError as VCD43NRTVIIRSUnavailableError
 
 logger = logging.getLogger(__name__)
 
@@ -40,7 +41,6 @@ def retrieve_STARS_sources(
 
     Raises:
         DownloadFailed: If an HLS download fails.
-        AuxiliaryLatency: If HLS data for a given tile/date is not available (latency issue).
     """
     logger.info(
         f"Retrieving HLS sources for tile {cl.place(tile)} from {cl.time(HLS_start_date)} to {cl.time(HLS_end_date)}"
@@ -78,9 +78,14 @@ def retrieve_STARS_sources(
     logger.info(
         f"Retrieving VIIRS sources for tile {cl.place(tile)} from {cl.time(VIIRS_start_date)} to {cl.time(VIIRS_end_date)}"
     )
-    # Prefetch VNP09GA data for the specified VIIRS date range and geometry
-    VCD43NRT_connection.prefetch_VNP09GA(
-        start_date=VIIRS_start_date,
-        end_date=VIIRS_end_date,
-        geometry=geometry,
-    )
+    # Prefetch VNP09GA data for the specified VIIRS date range and geometry.
+    # Defer VIIRSUnavailableError to generate_STARS_inputs() so VIIRS_GIVEUP_DAYS
+    # latency vs. total-window failure is evaluated consistently.
+    try:
+        VCD43NRT_connection.prefetch_VNP09GA(
+            start_date=VIIRS_start_date,
+            end_date=VIIRS_end_date,
+            geometry=geometry,
+        )
+    except VCD43NRTVIIRSUnavailableError as e:
+        logger.warning(f"VIIRS prefetch reported unavailable granules: {e}")
```

### Step 2: Add Unit Tests in `tests/test_retrieve_STARS_sources.py`

Add unit tests covering `retrieve_STARS_sources()` behavior:
1. `test_viirs_unavailable_during_prefetch_is_deferred` — verifies `VCD43NRTVIIRSUnavailableError` raised by `prefetch_VNP09GA` is caught and logged rather than aborting before `generate_STARS_inputs()`.
2. `test_cmr_server_unreachable_during_prefetch_propagates` — verifies `VCD43NRTCMRServerUnreachable` still propagates immediately (`exit_code = 14`).
3. `test_download_failed_during_prefetch_propagates` — verifies `VCD43NRTDownloadFailed` still propagates immediately (`exit_code = 16`).
4. `test_hls_download_failed_raises_download_failed` — verifies `HLSDownloadFailed` raises `ECOv003_exit_codes.DownloadFailed` (`exit_code = 16`).

---

## 4. Verification Plan

1. Run the unit test suite and smoke tests:
   ```bash
   make test
   ECOv003-L2T-STARS test-python
   ```
2. Confirm all tests pass with `0` warnings and commit the update to `main`.