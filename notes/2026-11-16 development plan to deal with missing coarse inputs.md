# `ECOv003-L2T-STARS` Error-Handling Diagnosis & Development Plan

**Date:** 2026-11-16  
**Affected Package:** `ECOv003-L2T-STARS` (`1.16.0`)  
**Upstream Dependency:** `VCD43NRT` (`1.5.0`)  
**Exit Code Contract:** `ECOv003-exit-codes` (`1.2.0` — locked for Collection 3 deployment)  
**Tracked Issue:** [ECOv003-L2T-STARS#90](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/90)

---

## 1. Incident Summary & Failure Chain

During a production run for tile `07KCA` on target date `2026-08-26`, `L2T_STARS` exited with unclassified failure exit code `1` (`OSError: raster file not found: <model_directory>/07KCA/2026-08-26/STARS_NDVI_2026-08-26_07KCA_70m.tif`).

Tracing the execution path through `ECOv003_L2T_STARS` identified three compounding error-handling gaps that masked an upstream auxiliary input failure behind a late-stage `OSError`:

1. **Silent Continuation When Zero Coarse Inputs Succeed (`ECOv003_L2T_STARS/generate_STARS_inputs.py`, lines 122–233):**
   - During the `[VIIRS_start_date, VIIRS_end_date]` lookback window (`2026-08-19` to `2026-08-26`), `generate_NDVI_coarse_image` and `generate_albedo_coarse_image` failed for every date due to upstream `VCD43NRT` / `GEOS5FP` input failures.
   - `generate_STARS_inputs` caught each exception, logged `WARNING: Unable to produce coarse NDVI/albedo`, and recorded the dates in `missing_coarse_dates`.
   - At lines 222–233, `generate_STARS_inputs` only raises `AuxiliaryLatency` (exit code `15`) if missing dates fall within `VIIRS_GIVEUP_DAYS` (`4` days) of the current UTC date. Because `2026-08-26` was older than 4 days, `coarse_latency_dates` was empty and `generate_STARS_inputs` returned normally with **zero** coarse GeoTIFFs written to `<downsampled_directory>`.

2. **All-`NaN` Coarse Arrays in Julia Data Fusion (`ECOv003_L2T_STARS/process_ECOSTRESS_data_fusion_distributed_bias.jl`, lines 165–176 & 283–286):**
   - With `length(coarse_images) == 0`, `covariance_images` is initialized as an all-`NaN` array (`fill(NaN, x_coarse_size, y_coarse_size, 1)`).
   - `fast_var_est` and `coarse_fine_scene_fusion_cbias_pmap` abort on all-`NaN` covariance parameters, causing the Julia worker script to exit non-zero before reaching `safe_write_geotiff` (line 369).

3. **Unchecked Subprocess Exit Code & Missing Posterior File Guard (`process_julia_data_fusion.py:129`, `process_STARS_product.py:284`):**
   - `process_julia_data_fusion` runs `subprocess.run(command, check=False, env=julia_env)` without inspecting `result.returncode`.
   - Control returns to `process_STARS_product`, which immediately calls `Raster.open(posterior_NDVI_filename)` at line 284 without checking whether the posterior files exist on disk, converting an upstream download/fusion failure into an unclassified `OSError` (`exit_code = 1`).

---

## 2. Locked Exit Code Mapping & `VCD43NRT` `1.5.0` Coordination

Because ECOSTRESS Collection 3 is in operational deployment, the exit code contract in `ECOv003-exit-codes` (`0`–`18`) is fixed and must not be modified. `VCD43NRT` `1.5.0` centralizes its mission-agnostic domain exceptions in `VCD43NRT.exceptions` (`CMRServerUnreachable`, `DownloadFailed`, `AuxiliaryDownloadFailed`, `VIIRSUnavailableError`, `BRDFRetrievalFailed`) with zero ECOSTRESS coupling, and `ECOv003-L2T-STARS` translates them into the locked exit codes:

| Failure Condition | `VCD43NRT` / Processing Exception | `ECOv003_exit_codes` Exception | Exit Code | Constant |
| :--- | :--- | :--- | :---: | :--- |
| CMR or Earthdata authentication unreachable | `VCD43NRT.exceptions.CMRServerUnreachable` (re-raised immediately in `generate_STARS_inputs.py`) | *(Caught in `L2T_STARS.py`)* | `14` | `AUXILIARY_SERVER_UNREACHABLE` |
| Coarse VIIRS dates missing within `VIIRS_GIVEUP_DAYS` (`4` days), or direct `VIIRSUnavailableError` | `VCD43NRT.exceptions.VIIRSUnavailableError` | `AuxiliaryLatency` | `15` | `AUXILIARY_LATENCY` |
| Zero coarse NDVI or zero coarse albedo rasters available across lookback window | `VIIRSUnavailableError` / `DownloadFailed` / `BRDFRetrievalFailed` across all dates | `DownloadFailed` | `16` | `DOWNLOAD_FAILED` |
| Direct VIIRS / GEOS-5 FP or HLS transfer failure | `VCD43NRT.exceptions.DownloadFailed` *(incl. `AuxiliaryDownloadFailed`)* / `HLSDownloadFailed` | `DownloadFailed` | `16` | `DOWNLOAD_FAILED` |
| Julia data fusion subprocess exits non-zero (`result.returncode != 0`) | `RuntimeError` | *(Caught in `L2T_STARS.py`)* | `1` | `UNCLASSIFIED_FAILURE_EXIT_CODE` |
| Any expected posterior GeoTIFF missing on disk before `Raster.open()` | *(Missing file check in `process_STARS_product.py`)* | `BlankOutput` | `17` | `BLANK_OUTPUT` |

*(Note: `AuxiliaryDownloadFailed` does not exist in `ECOv003_exit_codes`; `DownloadFailed` is the canonical exception for exit code `16` and is already handled by `L2T_STARS.py`.)*

---

## 3. Development Plan

### Step 1: Bump `VCD43NRT` Minimum Version (`pyproject.toml`)
Require `VCD43NRT~=1.5.0` so `VCD43NRT.exceptions` exposes `VIIRSUnavailableError`, `DownloadFailed`, `AuxiliaryDownloadFailed`, and `BRDFRetrievalFailed`, along with atomic granule/staging writes and HDF5 download validation.

```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -36,7 +36,7 @@ dependencies = [
     "sentinel-tiles~=1.1.1",
     "shapely~=2.2.0",
     "untangle~=1.3.0",
-    "VCD43NRT~=1.3.0",
+    "VCD43NRT~=1.5.0",
     "xmltodict~=1.0.4"
 ]
```

---

### Step 2: Coordinate `VCD43NRT` Exceptions & Fail Fast When Zero Coarse Inputs Exist (`ECOv003_L2T_STARS/generate_STARS_inputs.py`)
1. Import `DownloadFailed` (not `AuxiliaryDownloadFailed`) alongside `AuxiliaryLatency` from `ECOv003_exit_codes`, and import `CMRServerUnreachable` from `VCD43NRT.exceptions`.
2. Re-raise `VCD43NRTCMRServerUnreachable` immediately during the daily loop so CMR outages fail fast with `AUXILIARY_SERVER_UNREACHABLE` (`14`) rather than retrying across all 8 days.
3. Track `available_NDVI_coarse_count` and `available_albedo_coarse_count` across `[VIIRS_start_date, VIIRS_end_date]`. After the `VIIRS_GIVEUP_DAYS` `AuxiliaryLatency` (`15`) check, raise `DownloadFailed` (`16`) if either count is zero before entering Julia data fusion.

```diff
--- a/ECOv003_L2T_STARS/generate_STARS_inputs.py
+++ b/ECOv003_L2T_STARS/generate_STARS_inputs.py
@@ -1,14 +1,15 @@
 from typing import Union
-from datetime import date, datetime, timedelta
+from datetime import date, datetime, timedelta, timezone
 from os.path import exists
 import logging
 
 import colored_logging as cl
 from rasters import Raster, RasterGeometry
 from harmonized_landsat_sentinel import HLS2Connection
 from VCD43NRT import VCD43NRT
+from VCD43NRT.exceptions import CMRServerUnreachable as VCD43NRTCMRServerUnreachable
 
-from ECOv003_exit_codes import AuxiliaryLatency
+from ECOv003_exit_codes import AuxiliaryLatency, DownloadFailed
 
 from .constants import VIIRS_GIVEUP_DAYS
 from .generate_filename import generate_filename
@@ -74,8 +75,12 @@ def generate_STARS_inputs(
 
     Raises:
         AuxiliaryLatency: If coarse VIIRS data is missing within the VIIRS_GIVEUP_DAYS window.
+        DownloadFailed: If zero coarse NDVI or albedo images are available across the window.
+        VCD43NRTCMRServerUnreachable: If the NASA CMR server cannot be reached.
     """
     missing_coarse_dates = set()  # Track dates where coarse data could not be generated
+    available_NDVI_coarse_count = 0
+    available_albedo_coarse_count = 0
 
     logger.info(f"preparing coarse and fine images for STARS at {cl.place(tile)}")
 
@@ -128,6 +133,9 @@ def generate_STARS_inputs(
                     f"saving coarse image for STARS NDVI at {cl.place(tile)} on {cl.time(processing_date)}: {NDVI_coarse_filename}")
                 NDVI_coarse_image.to_geotiff(NDVI_coarse_filename)
 
+            if exists(NDVI_coarse_filename):
+                available_NDVI_coarse_count += 1
+
             if processing_date >= HLS_start_date:
                 try:
                     if not exists(NDVI_fine_filename):
@@ -149,6 +157,8 @@ def generate_STARS_inputs(
                 except Exception as e:
                     logger.warning(f"HLS NDVI is not available on {processing_date}: {e}")
                     logger.debug(f"Exception details: ", exc_info=True)
+        except VCD43NRTCMRServerUnreachable:
+            raise
         except Exception as e:
             logger.exception(e)
             logger.warning(
@@ -177,6 +187,9 @@ def generate_STARS_inputs(
                     f"saving coarse image for STARS albedo at {cl.place(tile)} on {cl.time(processing_date)}: {albedo_coarse_filename}")
                 albedo_coarse_image.to_geotiff(albedo_coarse_filename)
 
+            if exists(albedo_coarse_filename):
+                available_albedo_coarse_count += 1
+
             if processing_date >= HLS_start_date:
                 try:
                     if not exists(albedo_fine_filename):
@@ -199,6 +212,8 @@ def generate_STARS_inputs(
                 except Exception as e:
                     logger.warning(f"HLS albedo is not available on {processing_date}: {e}")
                     logger.debug(f"Exception details: ", exc_info=True)
+        except VCD43NRTCMRServerUnreachable:
+            raise
         except Exception as e:
             logger.exception(e)
             logger.warning(
@@ -220,11 +235,22 @@ def generate_STARS_inputs(
     #  as needing a retry at a later date.
     coarse_latency_dates = [
         d
         for d in missing_coarse_dates
-        if (datetime.utcnow().date() - d).days <= VIIRS_GIVEUP_DAYS
+        if (datetime.now(timezone.utc).date() - d).days <= VIIRS_GIVEUP_DAYS
     ]
 
     if len(coarse_latency_dates) > 0:
         raise AuxiliaryLatency(
             f"Missing coarse dates within {VIIRS_GIVEUP_DAYS}-day window: "
             f"{', '.join([str(d) for d in sorted(list(coarse_latency_dates))])}"
         )
+
+    if available_NDVI_coarse_count == 0:
+        raise DownloadFailed(
+            f"No coarse NDVI images available for tile {tile} from {VIIRS_start_date} to {VIIRS_end_date}"
+        )
+
+    if available_albedo_coarse_count == 0:
+        raise DownloadFailed(
+            f"No coarse albedo images available for tile {tile} from {VIIRS_start_date} to {VIIRS_end_date}"
+        )
```

---

### Step 3: Align `L2T_STARS.py` & `retrieve_STARS_sources.py` with `VCD43NRT` `1.5.0` & `ECOv003-exit-codes`
1. In `ECOv003_L2T_STARS/L2T_STARS.py`, import `CMRServerUnreachable`, `DownloadFailed`, and `VIIRSUnavailableError` from `VCD43NRT.exceptions` and include `VCD43NRTVIIRSUnavailableError` in the `AUXILIARY_LATENCY` (`15`) handler.
2. In `ECOv003_L2T_STARS/retrieve_STARS_sources.py`, replace the undefined `AuxiliaryDownloadFailed` reference with `DownloadFailed` (`16`).

```diff
--- a/ECOv003_L2T_STARS/L2T_STARS.py
+++ b/ECOv003_L2T_STARS/L2T_STARS.py
@@ -30,8 +30,11 @@ from ECOv002_granules import L2TLSTE as ECOv002L2TLSTE
 from ECOv003_granules import L2TLSTE
 import urllib
 
-from VCD43NRT.exceptions import CMRServerUnreachable as VCD43NRTCMRServerUnreachable
-from VCD43NRT.VIIRS import DownloadFailed as VCD43NRTDownloadFailed
+from VCD43NRT.exceptions import (
+    CMRServerUnreachable as VCD43NRTCMRServerUnreachable,
+    DownloadFailed as VCD43NRTDownloadFailed,
+    VIIRSUnavailableError as VCD43NRTVIIRSUnavailableError,
+)
 
 from .version import __version__
 from .constants import *
@@ -435,7 +438,7 @@ def L2T_STARS(
     except HLSNotAvailable as exception:
         logger.exception(exception)
         exit_code = LAND_FILTER  # This might indicate no HLS data for the tile, similar to land filter
-    except (HLSSentinelMissing, HLSLandsatMissing) as exception:
+    except (HLSSentinelMissing, HLSLandsatMissing, VCD43NRTVIIRSUnavailableError) as exception:
         logger.exception(exception)
         exit_code = AUXILIARY_LATENCY
     except ECOSTRESSExitCodeException as exception:
```

```diff
--- a/ECOv003_L2T_STARS/retrieve_STARS_sources.py
+++ b/ECOv003_L2T_STARS/retrieve_STARS_sources.py
@@ -63,7 +63,7 @@ def retrieve_STARS_sources(
             HLS_connection.landsat(tile=tile, date_UTC=processing_date)
         except HLSDownloadFailed as e:
             logger.exception(e)
-            raise AuxiliaryDownloadFailed(e)
+            raise DownloadFailed(e)
         except (
             HLSTileNotAvailable,
             HLSSentinelNotAvailable,
```

---

### Step 4: Check Julia Subprocess Return Code (`ECOv003_L2T_STARS/process_julia_data_fusion.py`)
Inspect `result.returncode` immediately after `subprocess.run(...)` and raise a `RuntimeError` if the Julia fusion process exits non-zero.

```diff
--- a/ECOv003_L2T_STARS/process_julia_data_fusion.py
+++ b/ECOv003_L2T_STARS/process_julia_data_fusion.py
@@ -126,4 +126,8 @@ def process_julia_data_fusion(
 
     logger.info(f"Executing Julia command: {' '.join(command)}")
     # Execute the Julia command, adding the environment changes
-    subprocess.run(command, check=False, env=julia_env)
+    result = subprocess.run(command, check=False, env=julia_env)
+    if result.returncode != 0:
+        raise RuntimeError(
+            f"Julia data fusion failed for {product_name} at tile {tile} with exit code {result.returncode}"
+        )
```

---

### Step 5: Validate Posterior Outputs Before Opening (`ECOv003_L2T_STARS/process_STARS_product.py`)
Verify that all 5 expected posterior GeoTIFFs (`mean`, `UQ`, `flag`, `bias`, `bias.UQ`) exist on disk before calling `Raster.open(...)` for both NDVI and albedo, raising `BlankOutput` (exit code `17`) if any expected file is missing.

```diff
--- a/ECOv003_L2T_STARS/process_STARS_product.py
+++ b/ECOv003_L2T_STARS/process_STARS_product.py
@@ -280,6 +280,17 @@ def process_STARS_product(
             num_workers=num_workers,
         )
 
+    for filename in [
+        posterior_NDVI_filename,
+        posterior_NDVI_UQ_filename,
+        posterior_NDVI_flag_filename,
+        posterior_NDVI_bias_filename,
+        posterior_NDVI_bias_UQ_filename,
+    ]:
+        if not exists(filename):
+            raise BlankOutput(f"Posterior NDVI raster file not found: {filename}")
+
     # Open the resulting NDVI rasters
     NDVI = Raster.open(posterior_NDVI_filename)
     NDVI_UQ = Raster.open(posterior_NDVI_UQ_filename)
@@ -365,6 +376,17 @@ def process_STARS_product(
             num_workers=num_workers,
         )
 
+    for filename in [
+        posterior_albedo_filename,
+        posterior_albedo_UQ_filename,
+        posterior_albedo_flag_filename,
+        posterior_albedo_bias_filename,
+        posterior_albedo_bias_UQ_filename,
+    ]:
+        if not exists(filename):
+            raise BlankOutput(f"Posterior albedo raster file not found: {filename}")
+
     # Open the resulting albedo rasters
     albedo = Raster.open(posterior_albedo_filename)
     albedo_UQ = Raster.open(posterior_albedo_UQ_filename)
```

---

## 4. Unit Test & Verification Plan

1. **Extend `tests/test_process_julia_data_fusion.py`:**
   - Update existing `subprocess.run` mocks to return a `CompletedProcess(..., returncode=0)`.
   - Add `test_raises_on_nonzero_julia_exit_code` asserting that `process_julia_data_fusion` raises `RuntimeError` when `subprocess.run` returns `returncode=1`.
2. **Add `tests/test_generate_STARS_inputs.py`:**
   - Stub `ECOv003_exit_codes` with real `Exception` subclasses for `AuxiliaryLatency` (`exit_code = 15`) and `DownloadFailed` (`exit_code = 16`).
   - Test that `VCD43NRT.exceptions.CMRServerUnreachable` propagates immediately without retrying remaining dates.
   - Test that `generate_STARS_inputs` raises `AuxiliaryLatency` (`15`) when all coarse dates fail within `VIIRS_GIVEUP_DAYS`.
   - Test that `generate_STARS_inputs` raises `DownloadFailed` (`16`) when all coarse dates fail outside `VIIRS_GIVEUP_DAYS` (zero coarse files available).
   - Test that `generate_STARS_inputs` succeeds when at least one coarse NDVI and one coarse albedo raster exist in the window.
3. **Add Posterior File Validation Test (`tests/test_process_STARS_product.py`):**
   - Stub `ECOv003_exit_codes.BlankOutput` (`exit_code = 17`) as a real `Exception` subclass.
   - Verify that missing posterior files raise `BlankOutput` before `Raster.open` is called for both NDVI and albedo.
4. **Run Test Suite:**
   ```bash
   PYTHONPATH=. pytest
   ECOv003-L2T-STARS test-python
   ```