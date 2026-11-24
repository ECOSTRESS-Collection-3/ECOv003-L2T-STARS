# ECOSTRESS Collection 3 Level 2 STARS Vegetation Index & Albedo

This is the main repository for the ECOsystem Spaceborne Thermal Radiometer Experiment on Space Station (ECOSTRESS) collection 3 level 2 STARS NDVI and albedo data product. This product utilizes the [Spatial Timeseries for Automated high-Resolution multi-Sensor (STARS)](https://github.com/STARS-Data-Fusion) data fusion system to produce normalized difference vegetation index (NDVI) and albedo estimates corresponding to ECOSTRESS surface temperature measurements, to support the [evapotranspiration product](https://github.com/ECOSTRESS-Collection-3/ECOv003-L3T-L4T-JET).

The ECOSTRESS collection 3 level 2 vegetation index and albedo data product is the pre-cursor to the [Surface Biology and Geology (SBG) collection 1 level 2 vegetation index and albedo data product algorithm](https://github.com/sbg-tir/SBG-TIR-L2-STARS).

[Gregory H. Halverson](https://github.com/gregory-halverson-jpl) (they/them)<br>
[gregory.h.halverson@jpl.nasa.gov](mailto:gregory.h.halverson@jpl.nasa.gov)<br>
NASA Jet Propulsion Laboratory 321H

[Margaret C. Johnson](https://github.com/majohnso) (she/her)<br>
[maggie.johnson@jpl.nasa.gov](mailto:maggie.johnson@jpl.nasa.gov)<br>
NASA Jet Propulsion Laboratory 341G

[Kerry Cawse-Nicholson](https://github.com/kcawse) (she/her)<br>
[kerry-anne.cawse-nicholson@jpl.nasa.gov](mailto:kerry-anne.cawse-nicholson@jpl.nasa.gov)<br>
NASA Jet Propulsion Laboratory 321H

## Citing This Package

If you use `ECOv003-L2T-STARS` in your research or software, please cite it using the following BibTeX entry:

```bibtex
@software{halverson_2026_ecov003_l2t_stars,
  author       = {Halverson, Gregory H. and Johnson, Margaret C. and Cawse-Nicholson, Kerry},
  title        = {ECOv003-L2T-STARS: ECOSTRESS Collection 3 Level 2 STARS Vegetation Index and Albedo},
  year         = {2026},
  version      = {1.19.0},
  publisher    = {NASA Jet Propulsion Laboratory},
  url          = {[https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS)}
}
```

The code for the ECOSTRESS level 2 STARS PGE has been developed using open-science practices based on the [ECOSTRESS collection 2 gridded and tiled product generation software](https://github.com/ECOSTRESS-Collection-2/ECOSTRESS-Collection-2).

This software produces estimates of:
- Normalized Difference Vegetation Index (NDVI)
- Albedo

NDVI and albedo are estimated at 70 m ECOSTRESS standard resolution for each daytime ECOSTRESS overpass by fusing temporally sparse but fine spatial resolution images from the Harmonized Landsat Sentinel (HLS) 2.0 product with daily, moderate spatial resolution images from VIIRS. The `VCD43NRT` package uses Suomi NPP first, with JPSS-1 and JPSS-2 available as mission fallbacks (`mission_priority = ("SNPP", "JPSS1", "JPSS2")`), to provide those VIIRS inputs. The data fusion is performed using a variant of the Spatial Timeseries for Automated high-Resolution multi-Sensor data fusion (STARS) algorithm developed by Dr. Margaret Johnson and Gregory Halverson at the Jet Propulsion Laboratory. STARS is a Bayesian timeseries methodology that provides streaming data fusion and uncertainty quantification through efficient Kalman filtering, implemented in a compiled Rust/PyO3 extension (`_stars_rust`, default) with an optional legacy Julia backend (`STARSDataFusion.jl`).

Operationally, each L2T STARS tile run loads the means and covariances of the STARS model saved from the most recent tile run, then iteratively advances the means and covariances forward each day updating with fine imagery from HLS and/or moderate resolution imagery from VIIRS up to the day of the target ECOSTRESS overpass. `VCD43NRT` applies the near-real-time BRDF workflow to daily VIIRS observations to produce the coarse NDVI and albedo inputs.

## 1. Introduction to Data Products

The data format for the ECOSTRESS products is described in the [ECOSTRESS Collection 3 landing page](https://github.com/ECOSTRESS-Collection-3).

## 2. L2T STARS NDVI and Albedo Product

NDVI and albedo are estimated at 70 m ECOSTRESS standard resolution with uncertainty for each UTC day in which there is an ECOSTRESS overpass by fusing temporally sparse but fine spatial resolution images from the Harmonized Landsat Sentinel (HLS) 2.0 product with daily, moderate spatial resolution VIIRS observations. Suomi NPP is preferred; JPSS-1 and JPSS-2 can fill dates without a preferred-mission observation.

The layers of the L2T STARS product are listed in Table 1. Data and uncertainty layers are represented by 32-bit floating point arrays (`float32`), and flag layers by 32-bit integer arrays (`int32`).

| **Name** | **Description** | **Type** | **Units** | **Fill Value** | **No Data Value** | **Valid Min** | **Valid Max** | **Scale Factor** | **Size** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NDVI | Normalized Difference Vegetation Index | float32 | Index | NaN | N/A | -1 | 1 | N/A | 9.83 MB |
| NDVI-UQ | Normalized Difference Vegetation Index Uncertainty | float32 | Index | NaN | N/A | 0 | 1 | N/A | 9.83 MB |
| NDVI-bias | Coarse-to-Fine NDVI Sensor Bias | float32 | Index | NaN | N/A | -1 | 1 | N/A | 0.20 MB |
| NDVI-bias-UQ | Coarse-to-Fine NDVI Sensor Bias Uncertainty | float32 | Index | NaN | N/A | 0 | 1 | N/A | 0.20 MB |
| NDVI-flag | 7-Day HLS NDVI Availability Flag | int32 | Mask | -9999 | N/A | 0 | 1 | N/A | 9.83 MB |
| albedo | Albedo | float32 | Ratio | NaN | N/A | 0 | 1 | N/A | 9.83 MB |
| albedo-UQ | Albedo Uncertainty | float32 | Ratio | NaN | N/A | 0 | 1 | N/A | 9.83 MB |
| albedo-bias | Coarse-to-Fine Albedo Sensor Bias | float32 | Ratio | NaN | N/A | -1 | 1 | N/A | 0.05 MB |
| albedo-bias-UQ | Coarse-to-Fine Albedo Sensor Bias Uncertainty | float32 | Ratio | NaN | N/A | 0 | 1 | N/A | 0.05 MB |
| albedo-flag | 7-Day HLS Albedo Availability Flag | int32 | Mask | -9999 | N/A | 0 | 1 | N/A | 9.83 MB |

*Table 1. Listing of L2T STARS data layers.*

## 3. Prerequisites & Authentication

### System Requirements
- Python `>=3.12` (`3.12` recommended for production containers; tested on `3.12` and `3.13`)
- A Rust toolchain (`rustc` / `cargo` + `maturin`) when building from source (not required when installing pre-built wheels)
- GDAL with NetCDF4 and HDF5 plugins (`libgdal-netcdf`, `libgdal-hdf5`) for reading GEOS-5 FP `.nc4` meteorological/aerosol files
- Optional: Julia `1.11.6` if running the legacy `--backend julia` data fusion engine

### Authentication
This package requires an [EarthData](https://urs.earthdata.nasa.gov/) account and reads EarthData credentials from `~/.netrc` (or `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` environment variables):

```text
machine urs.earthdata.nasa.gov
login <USERNAME>
password <PASSWORD>
```

## 4. Environment & Installation

```bash
mamba create -y -n ECOv003-L2T-STARS -c conda-forge python=3.12 libgdal-netcdf libgdal-hdf5 rasterio
mamba activate ECOv003-L2T-STARS
pip install ECOv003-L2T-STARS
ECOv003-L2T-STARS test
```

To build from a local source checkout:

```bash
make install
make test
```

## 5. Command Line Usage

### L2T STARS PGE
```bash
ECOv003-L2T-STARS <runconfig> [--date YYYY-MM-DD] [--spinup-days DAYS] [--target-resolution METERS] [--ndvi-resolution METERS] [--albedo-resolution METERS] [--viirs-mission-priority SNPP,JPSS1,JPSS2] [--calibrate-fine] [--sources-only] [--no-remove-input-staging] [--no-remove-prior] [--no-remove-posterior] [--backend {rust,julia}] [--initialize-julia] [--threads COUNT] [--num-workers COUNT] [--overwrite] [--version]
```

### Collection 3 Downloader PGE (`ECOv003-DL`)
```bash
ECOv003-DL <runconfig> [--tiles TILE1 TILE2 ...] [--version]
```

### Smoke Tests & Optional Julia Setup
```bash
ECOv003-L2T-STARS test          # Run Python and compiled Rust extension smoke tests
ECOv003-L2T-STARS test-rust     # Run compiled Rust extension smoke tests only
ECOv003-L2T-STARS test-python   # Run Python module, GDAL plugin, and upstream API contract checks
ECOv003-L2T-STARS install-julia # Optional: install pinned Julia 1.11.6 runtime and packages
```

## 6. Repository Structure

- `ECOv003_L2T_STARS/` — Python PGE package, run-config templates, Rust type stubs (`_stars_rust.pyi`), and legacy Julia fusion script (`process_ECOSTRESS_data_fusion_distributed_bias.jl`)
- `src/` — Compiled Rust/PyO3 STARS data-fusion kernel (`lib.rs`, `kalman.rs`, `covariance.rs`, `sobol.rs`, `spatial.rs`)
- `tests/` — Pytest unit and integration test suite
- `test_bundle/` — Offline MGRS tile `11SPS` verification inputs, priors, and reference outputs
- `scripts/` — Maintainer utilities (`set_julia_version.py`, `test_rust_output.py`, `test_julia_output.py`)
- `examples/` — Example scripts and Jupyter notebooks demonstrating granule downloads and PGE execution
- `documentation/` — Algorithm Theoretical Basis Document (ATBD) and User Guide sources/PDFs
- `notes/` — Consolidated development history, architecture, and I&T triage documentation

## 7. Known Issues & Operational Troubleshooting

| Severity | Tracking Issue | Log Signature | Root Cause | Resolution / Operational Guidance |
| :--- | :--- | :--- | :--- | :--- |
| **Bug (`ERROR`)** | [ECOv003-L2T-STARS#94](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/94) | `OSError: raster file not found: .../L2T_STARS_MODEL/<TILE>/<DATE>/STARS_NDVI_<DATE>_<TILE>_70m.tif` | Concurrent workers processing different scenes on the same `(tile, date_UTC)` raced on `REMOVE_POSTERIOR = True` in shared `model_directory/<tile>/<date_UTC>`. | **Fixed in `v1.19.0`:** Intermediate posterior rasters are isolated per `granule_ID`. |
| **Logging (`ERROR`)** | [ECOv003-L2T-STARS#95](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/95) | `RuntimeError: Julia data fusion failed for NDVI at tile <TILE> with exit code 1` | Legacy `--backend julia` subprocess output was not captured into the Python PGE `.log` file. | **Fixed in `v1.19.0`:** `process_julia_data_fusion.py` captures and logs `stdout`/`stderr` on failure; default `--backend rust` is recommended. |
| **Operations (`WARNING` / `ERROR`)** | [ECOv003-L2T-STARS#96](https://github.com/ECOSTRESS-Collection-3/ECOv003-L2T-STARS/issues/96) | `validation error: Unable to open file as NetCDF: '...GEOS.fp.asm.tavg3_2d_aer_Nx.*.nc4'` & `FileNotFoundError: ...NBAR_I1.temp.tif` | Pre-`v1.18.0` containers collided in `VCD43NRT_products/` and cached truncated `.nc4` files from `portal.nccs.nasa.gov` dropouts. | **Ops Action:** Deploy `ECOv003-L2T-STARS >=1.19.0`, purge truncated `.nc4` files in `GEOS5FP_download/`, and re-queue failed DAG tasks. |
| **Resolved (`INFO`)** | `v1.18.0` | `Sentinel tile <TILE> is not on land. Skipping processing.` | `LandFilter` exceptions on ocean/water tiles were previously logged at `[ERROR]` level. | **Fixed in `v1.18.0`:** Logged at `[INFO]` level while returning exit code `11` (`LAND_FILTER`). |

## 8. Release History & Operational Context

`ECOv003-L2T-STARS` evolved from a monolithic Collection 2 port in November 2024 (`v1.0.1`) into a modular, multi-mission JPSS Product Generating Executable (PGE) backed by a compiled Rust data-fusion core (`v1.18.0`–`v1.19.0`) within the NASA JPL ECOSTRESS Science Data System (`ecostress-level-2-3-4`):

| Operational Epoch | Dates | `ECOv003-L2T-STARS` | Data Fusion Engine | Coarse VIIRS Source | Sister PGE (`ECOv003-L3T-L4T-JET`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Epoch 1: Initial C3 Port & Modularization** | Nov 2024 – Sep 2025 | `v1.0.1` – `v1.10.0` | Julia (`STARSDataFusion.jl`) | Suomi NPP (`VNP43NRT` / `VNP43IA4` / `VNP43MA3`) | `v1.0.1` – `v1.9.0` |
| **Epoch 1: C3 Forward-Processing Baseline** | Dec 2025 – Nov 2, 2026 | `v1.11.0` – `v1.12.1` | Julia `1.11.6` (isolated `GDAL_jll`) | Suomi NPP (`VNP43NRT`) | `v1.13.0` – `v1.18.0` |
| **Epoch 2: JPSS Cutover & Dependency Alignment** | Nov 11 – Nov 17, 2026 | `v1.13.0` – `v1.17.0` | Julia `1.11.6` | JPSS Multi-Mission (`VCD43NRT`) | `v1.19.0` – `v1.20.3` |
| **Epoch 2: Rust Fusion Core & I&T Hardening** | Nov 18 – Nov 23, 2026 | `v1.18.0` – `v1.19.0` | **Rust (`_stars_rust` default)** / Julia fallback | JPSS Multi-Mission (`VCD43NRT` + staging isolation) | `v1.21.0` – `v1.22.1` |

### Phase 1: Collection 2 Port & Hybrid Python/Julia Prototype (`v1.0.1` – `v1.1.0`, Nov 2024 – Jun 2025)
* **`v1.0.1` (2024-11-12):** Initial Collection 3 port duplicated from `ECOv002-L2T-STARS` as a hybrid Python/Julia package, housing the pipeline in a 1,777-line `L2T_STARS.py` module alongside inline `BRDF/`, `LPDAAC/`, `VIIRS/`, `VNP43NRT/`, `daterange/`, `timer/`, and `exit_codes.py` modules, and unifying `PGEVersion` with package version metadata.
* **`v1.1.0` (2025-06-24):** Replaced inline exit codes and granule writers with shared `ECOv003-exit-codes` and `ECOv003-granules`; integrated `STARSDataFusion.jl` (`process_ECOSTRESS_data_fusion_distributed_bias.jl`) adding `NDVI-flag`, `albedo-flag`, `*.bias`, and `*.bias-UQ` layers plus `threads=1` memory controls; decomposed `L2T_STARS.py` into single-responsibility modules (`L2TSTARSConfig.py`, `generate_L2T_STARS_runconfig.py`, `generate_STARS_inputs.py`, `retrieve_STARS_sources.py`, `load_prior.py`, `prior.py`, `process_STARS_product.py`, `process_julia_data_fusion.py`); and added the `ECOv003-DL` Collection 3 Downloader PGE.

### Phase 2: XML Run-Config, Authentication & Upstream Extraction (`v1.2.0` – `v1.10.0`, Jul – Sep 2025)
* **`v1.2.0` (2025-07-03):** Added `--overwrite` CLI support, fixed `generate_L2T_STARS_runconfig` return values, and standardized XML run-config parsing on `StaticAncillaryFileGroup`.
* **`v1.3.0` (2025-07-09):** Replaced `pycksum` with a pure-Python POSIX `cksum` module for Python 3.12+ compatibility, added Earthdata `.netrc` / environment authentication (`login.py`), and wired `ECOv003-L2T-STARS` CLI entry points.
* **`v1.4.0` – `v1.6.1` (Jul 15–22, 2025):** Backported `DOWNSAMPLED_products` directory structure, defaulted `initialize_julia=False`, resolved `VNP09GA` search warnings, upgraded to `harmonized-landsat-sentinel v2.0.0` (`HLS2Connection`), standardized layer names to `NDVI-bias-UQ` / `albedo-bias-UQ`, and fixed the `ECOv003-DL` script entry point.
* **`v1.7.0` – `v1.10.0` (Jul 29 – Sep 25, 2025):** Stripped Conda `GDAL_DATA` / `GDAL_DRIVER_PATH` from Julia subprocesses, switched input loading to `ECOv003_granules.L2TLSTE`, adopted `L2TSTARS.generate_granule_name(...)` for Collection 3 granule IDs, populated `StandardMetadata.BuildID`, fixed `job_ID` timestamps, and added same-day prior copying (`copy_prior_to_posterior`).

### Phase 3: Collection 3 Forward-Processing Baseline (`v1.11.0` – `v1.12.1`, Dec 2025 – Oct 2026)
* **`v1.11.0` (2025-12-02):** Hardened `os.environ.copy()` isolation for Julia subprocesses and implemented direct `ArchGDAL.create` GeoTIFF writing (`safe_write_geotiff`) to eliminate `RastersArchGDALExt` driver failures across the ~11-month Suomi NPP forward-processing baseline.
* **`v1.12.0` – `v1.12.1` (Oct 12–19, 2026):** Added dual `ECOv003` / `ECOv002` `L2T_LSTE` input support, populated `StandardMetadata.InputPointer`, and introduced `julia_environment.py`, `julia_smoke_test.jl`, and `ECOv003-L2T-STARS-install-julia` pinned to Julia `1.11.6`.

### Phase 4: November 2, 2026 Suomi NPP Decommissioning, JPSS Cutover & Rust Core (`v1.13.0` – `v1.19.0`, Nov 2026)
* **`v1.13.0` (2026-11-11):** Following the November 2, 2026 decommissioning of Suomi NPP VIIRS (`VNP43NRT`), migrated coarse VIIRS retrieval to multi-mission JPSS `VCD43NRT` (`mission_priority = ("SNPP", "JPSS1", "JPSS2")`, `fallback_mode=True`) and removed ~3,500 lines of legacy inline `BRDF/`, `LPDAAC/`, `VIIRS/`, `VNP43NRT/`, `daterange/`, and `timer/` modules.
* **`v1.14.0` – `v1.16.0` (Nov 11–12, 2026):** Synchronized Python `3.12` dependencies (`GEOS5FP~=2.24.0`, `numpy~=2.5.4`, `pandas~=3.1.1`, `rasterio~=1.5.2`) with `ECOv003-L3T-L4T-JET`, introduced `smoke_test.py`, and added automatic `juliaup` bootstrapping (`install_julia.py`) pinned to Julia `1.11.6`.
* **`v1.17.0` (2026-11-17):** Added coarse outage latency resilience (`VIIRS_GIVEUP_DAYS = 4`, mapping outages deterministically to exit codes `14`–`17`) and offline verification (`test_bundle/` and `scripts/test_julia_output.py`).
* **`v1.18.0` (2026-11-18):** Replaced the Julia data-fusion core with the compiled Rust/PyO3 extension (`_stars_rust` built with `maturin`, `faer`, and `rayon`—`40.4%` faster with bitwise `float32` parity across all 10 layers), added `VCD43NRT_staging_directory` isolation, and downgraded `LandFilter` logs to `[INFO]`.
* **`v1.19.0` (2026-11-23):** Isolated intermediate posterior directories per `granule_ID` (`#94`), captured Julia subprocess `stderr`/`stdout` on failure (`#95`), added `StandardMetadata.PGEVersion`, standardized CLI/Docker/smoke-test structure with `ECOv003-L3T-L4T-JET`, aligned CI test matrices to Python `3.12`–`3.13`, and consolidated repository scripts, examples, and development notes.

## 9. Acknowledgements

We thank [Evan Davis](https://github.com/evandjpl) (he/him, NASA Jet Propulsion Laboratory) for assistance with code maintenance and deployment, and [Claire Villanueva-Weeks](https://github.com/clairesvw) (she/her) for assistance with open-source preparation.

## 10. References

Schaaf, C. B. et al. (2017). *Algorithm Theoretical Basis Document for MODIS Bidirectional Reflectance Distribution Function and Albedo (MOD43) Products*. NASA. [Link to source](https://lpdaac.usgs.gov/documents/110/MOD43_ATBD.pdf)