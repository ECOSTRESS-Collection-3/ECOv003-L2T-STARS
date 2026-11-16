# `ECOv003-L2T-STARS` Error-Handling Diagnosis & Development Plan

**Date:** 2026-11-16  
**Affected Package:** `ECOv003-L2T-STARS` (`1.16.0`)  
**Tracked Issue:** [ECOv003-L2T-STARS#90](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/90)

---

## 1. Incident Summary & Failure Chain

During a production run for tile `07KCA` on target date `2026-08-26`, `L2T_STARS` exited with unclassified failure exit code `1` (`OSError: raster file not found: <model_directory>/07KCA/2026-08-26/STARS_NDVI_2026-08-26_07KCA_70m.tif`).

Tracing the execution path through `ECOv003_L2T_STARS` identified three compounding error-handling gaps that masked an upstream auxiliary input failure behind a late-stage `OSError`:

1. **Silent Continuation When Zero Coarse Inputs Succeed (`ECOv003_L2T_STARS/generate_STARS_inputs.py`, lines 122–233):**
   - During the `[VIIRS_start_date, VIIRS_end_date]` lookback window (`2026-08-19` to `2026-08-26`), `generate_NDVI_coarse_image` and `generate_albedo_coarse_image` failed for every date due to upstream `VCD43NRT` / `GEOS5FP` input failures.
   - `generate_STARS_inputs` caught each exception, logged `WARNING: Unable to produce coarse NDVI/albedo`, and recorded the dates in `missing_coarse_dates`.
   - At lines 222–233, `generate_STARS_inputs` only raises `AuxiliaryLatency` if missing dates fall within `VIIRS_GIVEUP_DAYS` (`4` days) of the current UTC date. Because `2026-08-26` was older than 4 days, `coarse_latency_dates` was empty and `generate_STARS_inputs` returned normally with **zero** coarse GeoTIFFs written to `<downsampled_directory>`.

2. **All-`NaN` Coarse Arrays in Julia Data Fusion (`ECOv003_L2T_STARS/process_ECOSTRESS_data_fusion_distributed_bias.jl`, lines 165–176 & 283–286):**
   - With `length(coarse_images) == 0`, `covariance_images` is initialized as an all-`NaN` array (`fill(NaN, x_coarse_size, y_coarse_size, 1)`).
   - `fast_var_est` and `coarse_fine_scene_fusion_cbias_pmap` abort on all-`NaN` covariance parameters, causing the Julia worker script to exit non-zero before reaching `safe_write_geotiff` (line 369).

3. **Unchecked Subprocess Exit Code & Missing Posterior File Guard (`process_julia_data_fusion.py:129`, `process_STARS_product.py:284`):**
   - `process_julia_data_fusion` runs `subprocess.run(command, check=False, env=julia_env)` without inspecting `result.returncode`.
   - Control returns to `process_STARS_product`, which immediately calls `Raster.open(posterior_NDVI_filename)` at line 284 without checking whether the posterior files exist on disk, converting an upstream download/fusion failure into an unclassified `OSError` (`exit_code = 1`).

---

## 2. Development Plan

### Step 1: Fail Fast When Zero Coarse Inputs Exist (`ECOv003_L2T_STARS/generate_STARS_inputs.py`)
After the `VIIRS_GIVEUP_DAYS` latency check completes, verify that at least one coarse NDVI raster and one coarse albedo raster exist on disk for the `[VIIRS_start_date, VIIRS_end_date]` window. If either count is zero, raise `AuxiliaryDownloadFailed` (mapped to `DOWNLOAD_FAILED` in `L2T_STARS.py`) before entering Julia data fusion.

```diff
--- a/ECOv003_L2T_STARS/generate_STARS_inputs.py
+++ b/ECOv003_L2T_STARS/generate_STARS_inputs.py
@@ -8,7 +8,7 @@ from rasters import Raster, RasterGeometry
 from harmonized_landsat_sentinel import HLS2Connection
 from VCD43NRT import VCD43NRT
 
-from ECOv003_exit_codes import AuxiliaryLatency
+from ECOv003_exit_codes import AuxiliaryLatency, AuxiliaryDownloadFailed
 
 from .constants import VIIRS_GIVEUP_DAYS
 from .generate_filename import generate_filename
@@ -74,8 +74,11 @@ def generate_STARS_inputs(
 
     Raises:
         AuxiliaryLatency: If coarse VIIRS data is missing within the VIIRS_GIVEUP_DAYS window.
+        AuxiliaryDownloadFailed: If zero coarse NDVI or albedo images are available across the window.
     """
     missing_coarse_dates = set()  # Track dates where coarse data could not be generated
+    available_NDVI_coarse_count = 0
+    available_albedo_coarse_count = 0
 
     logger.info(f"preparing coarse and fine images for STARS at {cl.place(tile)}")
 
@@ -128,6 +131,9 @@ def generate_STARS_inputs(
                     f"saving coarse image for STARS NDVI at {cl.place(tile)} on {cl.time(processing_date)}: {NDVI_coarse_filename}")
                 NDVI_coarse_image.to_geotiff(NDVI_coarse_filename)
 
+            if exists(NDVI_coarse_filename):
+                available_NDVI_coarse_count += 1
+
             if processing_date >= HLS_start_date:
                 try:
                     if not exists(NDVI_fine_filename):
@@ -177,6 +183,9 @@ def generate_STARS_inputs(
                     f"saving coarse image for STARS albedo at {cl.place(tile)} on {cl.time(processing_date)}: {albedo_coarse_filename}")
                 albedo_coarse_image.to_geotiff(albedo_coarse_filename)
 
+            if exists(albedo_coarse_filename):
+                available_albedo_coarse_count += 1
+
             if processing_date >= HLS_start_date:
                 try:
                     if not exists(albedo_fine_filename):
@@ -228,3 +237,13 @@ def generate_STARS_inputs(
             f"Missing coarse dates within {VIIRS_GIVEUP_DAYS}-day window: "
             f"{', '.join([str(d) for d in sorted(list(coarse_latency_dates))])}"
         )
+
+    if available_NDVI_coarse_count == 0:
+        raise AuxiliaryDownloadFailed(
+            f"No coarse NDVI images available for tile {tile} from {VIIRS_start_date} to {VIIRS_end_date}"
+        )
+
+    if available_albedo_coarse_count == 0:
+        raise AuxiliaryDownloadFailed(
+            f"No coarse albedo images available for tile {tile} from {VIIRS_start_date} to {VIIRS_end_date}"
+        )
```

---

### Step 2: Check Julia Subprocess Return Code (`ECOv003_L2T_STARS/process_julia_data_fusion.py`)
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

### Step 3: Validate Posterior Outputs Before Opening (`ECOv003_L2T_STARS/process_STARS_product.py`)
Verify that all 5 expected posterior GeoTIFFs (`mean`, `UQ`, `flag`, `bias`, `bias.UQ`) exist on disk before calling `Raster.open(...)` for both NDVI and albedo, raising `BlankOutput` if any expected file is missing.

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

## 3. Unit Test & Verification Plan

1. **Extend `tests/test_process_julia_data_fusion.py`:**
   - Update existing `subprocess.run` mocks to return a `CompletedProcess(..., returncode=0)`.
   - Add `test_raises_on_nonzero_julia_exit_code` asserting that `process_julia_data_fusion` raises `RuntimeError` when `subprocess.run` returns `returncode=1`.
2. **Add `tests/test_generate_STARS_inputs.py`:**
   - Test that `generate_STARS_inputs` raises `AuxiliaryLatency` when all coarse dates fail within `VIIRS_GIVEUP_DAYS`.
   - Test that `generate_STARS_inputs` raises `AuxiliaryDownloadFailed` when all coarse dates fail outside `VIIRS_GIVEUP_DAYS` (zero coarse files available).
   - Test that `generate_STARS_inputs` succeeds when at least one coarse NDVI and one coarse albedo raster exist in the window.
3. **Add Posterior File Validation Test (`tests/test_process_STARS_product.py`):**
   - Verify that missing posterior files raise `BlankOutput` before `Raster.open` is called.
4. **Run Test Suite:**
   ```bash
   PYTHONPATH=. pytest
   ECOv003-L2T-STARS test-python
   ```

---

## 4. Upstream / Downstream Considerations

- **Runtime Environment (`GDAL` NetCDF/HDF5 Drivers):** Ensure the deployment environment provides GDAL `netCDF` and `HDF5` plugins (`GDAL_DRIVER_PATH`) so `VCD43NRT` / `GEOS5FP` can validate `.nc4` files cleanly while `process_julia_data_fusion.py` continues stripping `GDAL_DATA` and `GDAL_DRIVER_PATH` from the Julia subprocess environment.
- **Shared Storage Concurrency (`VCD43NRT` / `rasters`):** Parallel tile runs sharing a single `<sources_directory>` can collide when writing `.temp.tif` files in `Raster.to_COG()` or regenerating stale `VCD43NRT` granule directories; scoping temp files by PID/UUID and staging granule outputs atomically in upstream packages will prevent multi-worker race conditions.