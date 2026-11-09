# Plan: Integrate VCD43NRT and JPSS into ECOSTRESS Collection 3

## Objective

Replace Collection 3's local Julia-backed `VNP43NRT` VIIRS processor with the
standalone Python/Rust `VCD43NRT` package, while keeping the ECOSTRESS workflow
unchanged except that JPSS VIIRS observations can also supply its daily
moderate-resolution inputs.

The existing NRT science path remains the baseline: daily VIIRS surface
reflectance is processed through the same BRDF, NDVI, and albedo workflow and
fed into the same STARS time series. The package has already been tested by the
project owner to produce the same output as the old Julia implementation when
using SNPP. Treat that SNPP parity as established; retain it as an integration
regression check rather than reopening the algorithm as a migration scope.

JPSS should be added at the input/source-selection layer. Remove the local
VIIRS readers and both local NRT/precomputed product paths after replacing
them with VCD43NRT. Do not change HLS processing, time-series windows, STARS
fusion, product generation, or ECOSTRESS output contracts.

## Existing workflow and integration boundary

The main integration points are:

- [`ECOv003_L2T_STARS/L2T_STARS.py`](../ECOv003_L2T_STARS/L2T_STARS.py):
  creates the VIIRS connection through VCD43NRT. Remove the legacy
  `use_VNP43NRT` switch and the precomputed `VNP43IA4`/`VNP43MA3` branch.
- [`ECOv003_L2T_STARS/retrieve_STARS_sources.py`](../ECOv003_L2T_STARS/retrieve_STARS_sources.py):
  prefetches daily VIIRS input data. Continue retrieving the same date range
  and geometry, including the 16-day BRDF lookback needed before the first
  coarse STARS date.
- [`ECOv003_L2T_STARS/generate_STARS_inputs.py`](../ECOv003_L2T_STARS/generate_STARS_inputs.py),
  [`ECOv003_L2T_STARS/generate_NDVI_coarse_image.py`](../ECOv003_L2T_STARS/generate_NDVI_coarse_image.py),
  and [`ECOv003_L2T_STARS/generate_albedo_coarse_image.py`](../ECOv003_L2T_STARS/generate_albedo_coarse_image.py):
  consume date-and-geometry NDVI/albedo images and stage them for STARS.
  Preserve the 490 m NDVI and 980 m albedo grids, filenames, zero-to-NoData
  handling, mosaicking, and failure/latency behavior.
- [`ECOv003_L2T_STARS/constants.py`](../ECOv003_L2T_STARS/constants.py),
  [`ECOv003_L2T_STARS/main.py`](../ECOv003_L2T_STARS/main.py), and
  [`pyproject.toml`](../pyproject.toml): provide defaults, command-line
  configuration, and runtime dependencies.

The Julia runtime remains necessary for the existing STARS fusion process.
Removing the Julia NRT processor must not remove or alter Julia initialization
needed elsewhere in the pipeline.

## Intended mission policy

1. Keep SNPP as the first-choice source so existing inputs and results remain
   unchanged whenever SNPP data is available.
2. When configured for operational fallback, try JPSS-1 and then JPSS-2 for
   each tile and observation date where a preferred mission has no usable
   granule. A 16-day BRDF window may contain observations from more than one
   mission; do not lock the entire window to one mission.
3. Allow operations to pin a mission or provide an explicit priority list.
   The default policy must be explicit, logged, and testable; mission
   configuration should not require changing science or STARS parameters.
4. Fall back only for confirmed data unavailability. Authentication, CMR,
   network, corrupt-input, and processing failures must remain explicit errors,
   not be treated as evidence that another mission should silently be used.
5. Record the selected mission and source granule for each observation date.
   A generic “JPSS” label is insufficient for distinguishing JPSS-1 from
   JPSS-2 or explaining a mixed-mission BRDF fit.

## Implementation plan

### 1. Add and verify the package dependency

- Add a pinned, released `VCD43NRT` version to the ECOSTRESS runtime
  dependencies. Confirm its Python 3.11+ and compiled Rust-wheel requirements
  match every production image and target platform.
- Verify the installed extension imports and the package's Earthdata/CMR
  authentication works in unattended runs using the deployment's existing
  credential mechanism. Do not log credentials.
- Keep package-specific raw input, staging, and granule-product directories
  distinct from legacy caches during rollout. Do not assume old intermediate
  files prove the new mission selection or provenance.

### 2. Make mission discovery and fallback reliable

- Verify the package's end-to-end handling for SNPP, JPSS-1, and JPSS-2:
  CMR query/product identifiers, downloaded filename parsing, mission-specific
  HDF reader, cache naming, and processing. The configured mission and reader
  must agree with the downloaded granule.
- Resolve any package gaps before relying on fallback. In particular, test
  that JPSS-2 is discoverable without an undocumented external override and
  that its data are not routed through an SNPP reader.
- Verify mission-priority precedence when an explicit `mission`, custom
  `mission_priority`, and fallback setting are supplied. Validate invalid or
  empty settings at initialization.
- Exercise selection independently for every daily input in the BRDF window,
  including a window with SNPP, JPSS-1, and JPSS-2 observations. Ensure missing
  days, duplicate candidates, and selection order are deterministic.
- Preserve the existing recent-versus-older missing-data policy and ECOSTRESS
  exit/error behavior when no mission has usable observations.

### 3. Connect VCD43NRT without changing the ECOSTRESS-facing workflow

- Construct the package's `VCD43NRT` connection in `L2T_STARS.py`. Pass through the
  existing working, download, VNP09GA-input, mosaic, and GEOS5-FP locations
  using the package's supported constructor arguments; set mission policy
  explicitly.
- Keep the VIIRS downloader contract consumed by the pipeline:
  `NDVI(date_UTC, geometry, ...)`, `albedo(date_UTC, geometry, ...)`, and the
  prefetch operation over the required date range and geometry. The package's
  current `albedo` method does not expose the same `resampling` argument as
  the legacy downloader contract. Add compatible behavior in the package or a
  narrow adapter; do not silently ignore caller-selected resampling.
- Preserve target geometry, multiple-tile mosaic fill order, optional raster
  output behavior, and clear no-intersection errors for both NDVI and albedo.
- Keep the existing coarse-image generation, STARS input staging, date
  calculations, HLS handling, calibration option, and downstream product
  generation unchanged. Keep current ECOSTRESS product names, layers, grids,
  and metadata.
- Remove the `use_VNP43NRT` selection option and the precomputed-product
  selection path. Update command-line documentation to describe the
  package-backed processor and mission-priority option.

### 4. Make provenance and caches mission-safe

- Record effective mission policy and, for each daily input, the chosen
  mission and granule identity in logs and a durable granule/run manifest.
- Ensure output and cache validity accounts for source identity, mission
  policy, processing version, and relevant configuration. A cache produced
  under one fallback selection must not be mistaken for an equivalent result
  after source selection changes.
- Keep existing ECOSTRESS coarse STARS staging filenames and data layout.
  Isolate or invalidate old cached coarse images at cutover so a previously
  staged SNPP-only image cannot mask a JPSS-backed result. Define how source
  availability is rechecked for cached dates so newly available preferred
  SNPP data do not remain silently shadowed by stale fallback output.
- Reuse complete, compatible results; make incomplete or failed writes
  recoverable without destroying a previously valid output.

### 5. Integrate errors, logging, and operator controls

- Map package authentication, CMR, download, unavailable-data, and processing
  exceptions to existing ECOSTRESS exception/exit-code behavior without
  turning operational failures into apparent missing-data success.
- Log the requested mission policy and selected per-date missions without
  logging secrets.
- Expose mission-only and priority/fallback controls through the established
  configuration or CLI surface, with defaults that preserve SNPP preference.
  Keep runs reproducible by recording the effective settings in the run
  configuration or manifest.
- Update the relevant README/user documentation with package installation,
  Earthdata setup, mission policy, provenance, and failure behavior.

## Validation and release gates

### Automated integration tests

- Dependency import and extension loading in the supported runtime.
- Existing SNPP NRT integration against representative frozen inputs,
  asserting the established Julia-parity outputs remain unchanged.
- Mission-only runs for SNPP, JPSS-1, and JPSS-2; SNPP-to-JPSS-1 and
  SNPP-to-JPSS-2 fallback; custom priority; and mixed missions in one BRDF
  lookback window. Assert both values/coverage and selected source provenance.
- Per-date no-data, missing recent and older observations, duplicate CMR
  results, invalid mission configuration, authentication/network failures,
  corrupt inputs, and unavailable JPSS-2 configuration.
- Downloader API compatibility for positional and keyword calls, target
  geometry, resampling, mosaicking, cache reuse, and no-intersection errors.
- End-to-end STARS input regression: unchanged HLS retrieval, date windows,
  490 m/980 m coarse files, staged filenames, zero-to-NoData treatment, and
  unchanged downstream product generation. Verify all former precomputed
  VIIRS readers and call paths have been removed.

### Operational verification

- Run against representative real SNPP, JPSS-1, and JPSS-2 granules using the
  production Earthdata credentials and deployment images.
- Confirm each mission's granule schema, CMR availability, latency, and
  operational access on the actual deployment platforms.
- Run shadow comparisons before enabling fallback operationally. Monitor
  mission selection, input gaps, errors, cache behavior, coverage, runtime,
  and resource use.
- Keep the previous NRT implementation available for rollback through
  acceptance and an agreed monitoring period. Remove the old VIIRS retrieval,
  NRT, and precomputed-product code while preserving Julia STARS requirements.

## Completion criteria

- The package-backed NRT path preserves established SNPP results and the
  existing ECOSTRESS workflow and product contract.
- JPSS-1 and JPSS-2 can be selected and used correctly, with deterministic
  SNPP-first per-date fallback and provenance for mixed-mission windows.
- Existing no-data, latency, and error behavior remains compatible;
  mission/configuration and cache behavior are reproducible.
- Production installation, integration tests, operational checks, and
  rollback readiness pass before JPSS fallback is enabled for production.
