# ECOSTRESS Collection 3 Level 2 STARS Vegetation Index & Albedo

This is the main repository for the ECOsystem Spaceborne Thermal Radiometer Experiment on Space Station (ECOSTRESS) collection 3 level 2 STARS NDVI and albedo data product. This product utilizes the [Spatial Timeseries for Automated high-Resolution multi-Sensor (STARS)](https://github.com/STARS-Data-Fusion) data fusion system to produce normalized difference vegetation index (NDVI) and albedo estimates corresponding to ECOSTRESS surface temperature measurements, to support the [evapotranspiration product](https://github.com/ECOSTRESS-Collection-3/ECOv003-L3T-L4T-JET).

The ECOSTRESS collection 3 level 2 vegetation index and albedo data product is the pre-cursor to the [Surface Biology and Geology (SBG) collection 1 level 2 vegetation index and albedo data product algorithm](https://github.com/sbg-tir/SBG-TIR-L2-STARS).

[Gregory H. Halverson](https://github.com/gregory-halverson-jpl) (they/them)<br>
[gregory.h.halverson@jpl.nasa.gov](mailto:gregory.h.halverson@jpl.nasa.gov)<br>
NASA Jet Propulsion Laboratory 329G

[Margaret C. Johnson](https://github.com/majohnso) (she/her)<br>
[maggie.johnson@jpl.nasa.gov](mailto:maggie.johnson@jpl.nasa.gov)<br>
NASA Jet Propulsion Laboratory 398L

[Evan Davis](https://github.com/evandjpl) (he/him)<br>
[evan.w.davis@jpl.nasa.gov](mailto:evan.w.davis@jpl.nasa.gov)<br>
NASA Jet Propulsion Laboratory 397K

[Kerry Cawse-Nicholson](https://github.com/kcawse) (she/her)<br>
[kerry-anne.cawse-nicholson@jpl.nasa.gov](mailto:kerry-anne.cawse-nicholson@jpl.nasa.gov)<br>
NASA Jet Propulsion Laboratory 329G

[Claire Villanueva-Weeks](https://github.com/clairesvw) (she/her)<br>
[claire.s.villanueva-weeks@jpl.nasa.gov](mailto:claire.s.villanueva-weeks@jpl.nasa.gov)<br>
NASA Jet Propulsion Laboratory 329G

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