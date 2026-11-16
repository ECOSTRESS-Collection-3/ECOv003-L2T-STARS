# Exception Handling Coordination Strategy: `VCD43NRT` & `ECOv003-L2T-STARS`

**Date:** 2026-11-16  
**Affected Repositories:**
- `VCD43NRT` (`1.4.0`) — General-purpose VIIRS NRT BRDF/albedo/NDVI library
- `ECOv003-L2T-STARS` (`1.16.0`) — ECOSTRESS Collection 3 L2T STARS PGE
- `ECOv003-exit-codes` (`1.2.0`) — Locked Collection 3 operational exit-code contract (`0`–`18`)

**Related Issue:** [ECOv003-L2T-STARS#90](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/90)

---

## 1. Architectural Boundary & Core Principles

1. **Strict Dependency Direction (`ECOv003-L2T-STARS` $\rightarrow$ `VCD43NRT`):**
   - `VCD43NRT` is a mission-agnostic VIIRS NRT BRDF and surface reflectance utility reusable across ECOSTRESS, SBG, and standalone scientific workflows. It must **never** import `ECOv003_exit_codes` or hardcode ECOSTRESS scheduling rules (such as `VIIRS_GIVEUP_DAYS`).
   - `ECOv003-L2T-STARS` owns all ECOSTRESS operational policy and acts as the **sole adapter boundary** translating `VCD43NRT` domain exceptions into the locked `ECOv003-exit-codes` (`0`–`18`) contract.

2. **Preserve Root Causes at the Source:**
   - `VCD43NRT` must distinguish why an operation failed—network/CMR outage, missing granule in CMR, failed file transfer, missing GEOS-5 FP ancillary data, or insufficient valid observations for BRDF inversion—rather than collapsing failures into generic exceptions or returning silent all-`NaN` rasters.

3. **Two-Tier Evaluation in `ECOv003-L2T-STARS`:**
   - **Per-date tolerance (`generate_STARS_inputs.py`):** Single-day cloud/orbital gaps or transient per-day failures are logged and recorded rather than aborting immediately, allowing the 7-day spin-up window to succeed whenever at least one coarse NDVI and one coarse albedo raster are produced.
   - **Window-level classification (`generate_STARS_inputs.py` + `L2T_STARS.py`):** Once the lookback window finishes, `ECOv003-L2T-STARS` classifies complete window failures into retryable latency (`15`), hard download failure (`16`), or blank output (`17`).

---

## 2. `VCD43NRT` Exception Hierarchy (Provider Contract)

Currently, `VCD43NRT` defines domain exceptions across three modules (`VCD43NRT/exceptions.py`, `VCD43NRT/VIIRS.py`, and `VCD43NRT/VCD43NRT.py`). Consolidating all exceptions into `VCD43NRT/exceptions.py` and re-exporting them from `VCD43NRT/__init__.py`, `VCD43NRT/VIIRS.py`, and `VCD43NRT/VCD43NRT.py` maintains 100% backwards compatibility while giving downstream callers a single, clean hierarchy:

```python
# VCD43NRT/exceptions.py

class VCD43NRTError(Exception):
    """Base exception for all VCD43NRT domain errors."""


class CMRServerUnreachable(VCD43NRTError):
    """Remote NASA CMR or Earthdata authentication service cannot be reached."""


class DownloadFailed(VCD43NRTError, ConnectionError):
    """Granule or ancillary transfer failed after retries, or downloaded file is unreadable."""


class AuxiliaryDownloadFailed(DownloadFailed):
    """Required ancillary meteorological/aerosol input (e.g., GEOS-5 FP AOT) failed to download."""


class VIIRSUnavailableError(VCD43NRTError):
    """CMR query succeeded, but no VIIRS granule exists for the requested tile, date, and mission(s)."""


class BRDFRetrievalFailed(VCD43NRTError, RuntimeError):
    """BRDF kernel inversion could not be completed (e.g., <7 valid observations or singular fit)."""
```

### Behavioral Rules Inside `VCD43NRT`

| Module | Failure Condition | Exception Raised |
| :--- | :--- | :--- |
| `VCD43NRT/login.py` | Earthdata login / URS authentication fails | `CMRServerUnreachable` |
| `VCD43NRT/VIIRS_query.py` | `earthaccess.granule_query().get()` raises a network/CMR error | `CMRServerUnreachable` |
| `VCD43NRT/VIIRS.py` | CMR search returns 0 granules across `active_missions` | `VIIRSUnavailableError` |
| `VCD43NRT/VIIRS.py` | `earthaccess.download()` fails after `RETRIES` attempts | `DownloadFailed` |
| `VCD43NRT/VCD43NRT.py` (`AOT`) | `GEOS5FP.AOT()` raises `FailedGEOS5FPDownload` | `AuxiliaryDownloadFailed` *(subclass of `DownloadFailed`)* |
| `VCD43NRT/VCD43NRT.py` (`BRDF_parameters`) | Recent lookback date (`<= 4` days) has no VIIRS granule | `VIIRSUnavailableError` |
| `VCD43NRT/VCD43NRT.py` (`BRDF_parameters`) | Zero valid observation dates across the 16-day kernel window, or singular fit in `_brdf_rust.nrt_brdf_all` | `BRDFRetrievalFailed` |
| `VCD43NRT/VCD43NRT.py` (`NDVI`, `albedo`) | Mosaicked output contains zero valid observations / all `NaN` | `BRDFRetrievalFailed` |

---

## 3. `ECOv003-L2T-STARS` Translation Matrix (Consumer Policy)

`ECOv003-L2T-STARS` maps `VCD43NRT` exceptions and downstream processing failures into the locked `ECOv003-exit-codes` (`0`–`18`) across three execution stages:

| `VCD43NRT` / Processing Exception | Stage 1: Per-Date Loop (`generate_STARS_inputs.py`) | Stage 2: Post-Window Check (`generate_STARS_inputs.py`) | Stage 3: Top-Level PGE (`L2T_STARS.py`) | Locked Exit Code |
| :--- | :--- | :--- | :--- | :---: |
| `VCD43NRT.exceptions.CMRServerUnreachable` | **Re-raise immediately** (abort loop; do not burn remaining days on an unreachable server) | — | Caught $\rightarrow$ `AUXILIARY_SERVER_UNREACHABLE` | **`14`** |
| `VCD43NRT.exceptions.VIIRSUnavailableError` | Catch, log `WARNING`, record `processing_date` in `missing_coarse_dates`, continue | If any missing date $\le$ `VIIRS_GIVEUP_DAYS` (4d) $\rightarrow$ `AuxiliaryLatency` (`15`); else if `available_count == 0` $\rightarrow$ `DownloadFailed` (`16`) | Caught $\rightarrow$ `AUXILIARY_LATENCY` (if raised directly) or `DOWNLOAD_FAILED` | **`15`** or **`16`** |
| `VCD43NRT.exceptions.DownloadFailed` *(incl. `AuxiliaryDownloadFailed`)* | Catch, log `ERROR`, record `processing_date` in `missing_coarse_dates`, continue | If any missing date $\le$ `VIIRS_GIVEUP_DAYS` $\rightarrow$ `AuxiliaryLatency` (`15`); else if `available_count == 0` $\rightarrow$ `DownloadFailed` (`16`) | Caught $\rightarrow$ `DOWNLOAD_FAILED` | **`16`** *(or **`15`** if recent)* |
| `VCD43NRT.exceptions.BRDFRetrievalFailed` | Catch, log `WARNING` (e.g., persistent cloud cover), record `processing_date` in `missing_coarse_dates`, continue | If any missing date $\le$ `VIIRS_GIVEUP_DAYS` $\rightarrow$ `AuxiliaryLatency` (`15`); else if `available_count == 0` $\rightarrow$ `DownloadFailed` (`16`) | Caught via `DownloadFailed` $\rightarrow$ `DOWNLOAD_FAILED` | **`16`** *(or **`15`** if recent)* |
| Julia Fusion Non-Zero Exit (`process_julia_data_fusion.py`) | — | — | Raises `RuntimeError` $\rightarrow$ `UNCLASSIFIED_FAILURE_EXIT_CODE` | **`1`** |
| Missing Posterior GeoTIFF (`process_STARS_product.py`) | — | — | Raises `BlankOutput` before `Raster.open()` $\rightarrow$ `BLANK_OUTPUT` | **`17`** |

---

## 4. Reference Implementation Pattern

### 4.1 Per-Date Handling & Window Validation in `ECOv003_L2T_STARS/generate_STARS_inputs.py`

```python
from datetime import datetime, timezone
from ECOv003_exit_codes import AuxiliaryLatency, DownloadFailed
from VCD43NRT.exceptions import (
    BRDFRetrievalFailed as VCD43NRTBRDFRetrievalFailed,
    CMRServerUnreachable as VCD43NRTCMRServerUnreachable,
    DownloadFailed as VCD43NRTDownloadFailed,
    VIIRSUnavailableError as VCD43NRTVIIRSUnavailableError,
)
```

Inside the daily `[VIIRS_start_date, VIIRS_end_date]` loop:

```python
try:
    NDVI_coarse_exists = exists(NDVI_coarse_filename)
    if not NDVI_coarse_exists:
        NDVI_coarse_image = generate_NDVI_coarse_image(
            date_UTC=processing_date,
            VCD43NRT_connection=NDVI_VCD43NRT_connection,
            geometry=NDVI_coarse_geometry,
        )
        NDVI_coarse_image.to_geotiff(NDVI_coarse_filename)

    if exists(NDVI_coarse_filename):
        available_NDVI_coarse_count += 1
except VCD43NRTCMRServerUnreachable:
    # Network/CMR outage: fail immediately -> exit code 14 in L2T_STARS.py
    raise
except (
    VCD43NRTVIIRSUnavailableError,
    VCD43NRTDownloadFailed,
    VCD43NRTBRDFRetrievalFailed,
) as e:
    logger.warning(f"Unable to produce coarse NDVI for date {processing_date}: {e}")
    missing_coarse_dates.add(processing_date)
```

*(Apply the identical pattern for coarse albedo.)*

After the daily loop completes:

```python
now_date_UTC = datetime.now(timezone.utc).date()
coarse_latency_dates = [
    d for d in missing_coarse_dates if (now_date_UTC - d).days <= VIIRS_GIVEUP_DAYS
]

if len(coarse_latency_dates) > 0:
    raise AuxiliaryLatency(
        f"Missing coarse dates within {VIIRS_GIVEUP_DAYS}-day window: "
        f"{', '.join(str(d) for d in sorted(coarse_latency_dates))}"
    )

if available_NDVI_coarse_count == 0:
    raise DownloadFailed(
        f"No coarse NDVI images available for tile {tile} from {VIIRS_start_date} to {VIIRS_end_date}"
    )

if available_albedo_coarse_count == 0:
    raise DownloadFailed(
        f"No coarse albedo images available for tile {tile} from {VIIRS_start_date} to {VIIRS_end_date}"
    )
```

### 4.2 Top-Level Mapping in `ECOv003_L2T_STARS/L2T_STARS.py`

Import the consolidated exceptions from `VCD43NRT.exceptions` and map them cleanly to `ECOv003_exit_codes`:

```python
from VCD43NRT.exceptions import (
    CMRServerUnreachable as VCD43NRTCMRServerUnreachable,
    DownloadFailed as VCD43NRTDownloadFailed,
    VIIRSUnavailableError as VCD43NRTVIIRSUnavailableError,
)
```

In the top-level `try ... except` block of `L2T_STARS()`:

```python
except VCD43NRTDownloadFailed as exception:
    logger.exception(exception)
    exit_code = DOWNLOAD_FAILED
except (
    ConnectionError,
    urllib.error.HTTPError,
    CMRServerUnreachable,
    VCD43NRTCMRServerUnreachable,
) as exception:
    logger.exception(exception)
    exit_code = AUXILIARY_SERVER_UNREACHABLE
except DownloadFailed as exception:
    logger.exception(exception)
    exit_code = DOWNLOAD_FAILED
except (HLSSentinelMissing, HLSLandsatMissing, VCD43NRTVIIRSUnavailableError) as exception:
    logger.exception(exception)
    exit_code = AUXILIARY_LATENCY
```

---

## 5. Coordinated Implementation Roadmap

### Phase 1: `VCD43NRT` (Non-Breaking Exception Consolidation)
1. **Centralize exceptions in `VCD43NRT/exceptions.py`:** Define `VCD43NRTError`, `CMRServerUnreachable`, `DownloadFailed`, `AuxiliaryDownloadFailed`, `VIIRSUnavailableError`, and `BRDFRetrievalFailed`.
2. **Maintain backwards-compatible imports:** Re-export all exception classes from `VCD43NRT/__init__.py`, `VCD43NRT/VIIRS.py`, and `VCD43NRT/VCD43NRT.py`.
3. **Normalize solver errors:** Convert singular-fit `ValueError` from `_brdf_rust.nrt_brdf_all` into `BRDFRetrievalFailed` in `VCD43NRT.BRDF_parameters()`.
4. **Verify:** Add `tests/test_exceptions.py` confirming exception inheritance and import compatibility.

### Phase 2: `ECOv003-L2T-STARS` (Issue #90 Resolution)
1. **`ECOv003_L2T_STARS/generate_STARS_inputs.py`:** Re-raise `CMRServerUnreachable` immediately, catch `VCD43NRT` data/transfer failures per date, enforce the `VIIRS_GIVEUP_DAYS` `AuxiliaryLatency` (`15`) check, and raise `DownloadFailed` (`16`) if zero coarse NDVI or zero coarse albedo rasters exist across `[VIIRS_start_date, VIIRS_end_date]`.
2. **`ECOv003_L2T_STARS/L2T_STARS.py` & `retrieve_STARS_sources.py`:** Map `VCD43NRTVIIRSUnavailableError` $\rightarrow$ `AUXILIARY_LATENCY` (`15`), import `VCD43NRTDownloadFailed` from `VCD43NRT.exceptions`, and replace the undefined `AuxiliaryDownloadFailed` reference in `retrieve_STARS_sources.py` with `DownloadFailed` (`16`).
3. **`ECOv003_L2T_STARS/process_julia_data_fusion.py`:** Inspect `result.returncode != 0` after `subprocess.run(...)` and raise `RuntimeError`.
4. **`ECOv003_L2T_STARS/process_STARS_product.py`:** Verify all 5 expected posterior GeoTIFFs (`mean`, `UQ`, `flag`, `bias`, `bias.UQ`) exist on disk before calling `Raster.open(...)` for NDVI and albedo, raising `BlankOutput` (`17`) if any file is missing.
5. **Verify:** Run `PYTHONPATH=. pytest` and `ECOv003-L2T-STARS test-python`.