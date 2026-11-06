# ECOSTRESS Collection 3 Level 2 STARS Vegetation Index & Albedo

This is the main repository for the ECOsystem Spaceborne Thermal Radiometer Experiment on Space Station (ECOSTRESS) collection 3 level 2 STARS NDVI and albedo data product. This product will utilize the [Spatial Timeseries for Automated high-Resolution multi-Sensor (STARS)](https://github.com/STARS-Data-Fusion) data fusion system to produce normalized difference vegetation index (NDVI) and albedo estimates corresponding to ECOSTRESS surface temperature measurements, to support the [evapotranspiration product](https://github.com/ECOSTRESS-Collection-3/ECOv003-L3-JET).

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

The code for the ECOSTRESS level 2 STARS PGE will be developed using open-science practices based on the [ECOSTRESS collection 2 gridded and tiled product generation software](https://github.com/ECOSTRESS-Collection-2/ECOSTRESS-Collection-2).

This software will produce estimates of:
- Normalized Difference Vegetation Index (NDVI)
- albedo

NDVI and albedo are estimated at 70 m ECOSTRESS standard resolution for each daytime ECOSTRESS overpass by fusing temporally sparse but fine spatial resolution images from the Harmonized Landsat Sentinel (HLS) 2.0 product with daily, moderate spatial resolution images from the Suomi NPP Visible Infrared Imaging Radiometer Suite (VIIRS) VNP09GA product. The data fusion is performed using a variant of the Spatial Timeseries for Automated high-Resolution multi-Sensor data fusion (STARS) algorithm developed by Dr. Margaret Johnson and Gregory Halverson at the Jet Propulsion Laboratory. STARS is a Bayesian timeseries methodology that provides streaming data fusion and uncertainty quantification through efficient Kalman filtering.

Operationally, each L2T STARS tile run loads the means and covariances of the STARS model saved from the most recent tile run, then iteratively advances the means and covariances forward each day updating with fine imagery from HLS and/or moderate resolution imagery from VIIRS up to the day of the target SBG overpass. A pixelwise, lagged 16-day implementation of the VNP43 algorithm (Schaaf, 2017) is used for a near-real-time BRDF correction on the VNP09GA products to produce VIIRS NDVI and albedo.

## 1. Introduction to Data Products

The data format for the ECOSTRESS products is described in the [ECOSTRESS Collection 3 landing page](https://github.com/ECOSTRESS-Collection-3).

## 2. L2T STARS NDVI and Albedo Product

```mermaid
flowchart TB
    subgraph VNP43NRT[VNP43NRT.jl]
        VNP09GA_I[VNP09GA<br>I-Band<br>500m<br>Surface<br>Reflectance]
        VNP09GA_M[VNP09GA<br>M-Band<br>1000m<br>Surface<br>Reflectance]
        VIIRS_downscaling[VIIRS<br>Downscaling]
        VNP09GA_downscaled[Downscaled<br>500m<br>VIIRS<br>Surface<br>Reflectance]
        VNP43_BRDF[VNP43NRT.jl<br>BRDF<br>Correction]
        VIIRS_corrected[VIIRS<br>BRDF-Corrected<br>500m<br>Surface<br>Reflectance]
        VIIRS_NDVI[VIIRS<br>500m<br>NDVI]
        VIIRS_albedo[VIIRS<br>500m<br>Albedo]
    end

    subgraph HLS_aquisition[HLS.jl]
        direction TB
        Landsat_reflectance[HLS<br>Landsat<br>30m<br>Surface<br>Reflectance]
        Landsat_upsampled[Upsampled<br>Landsat<br>70m<br>Surface<br>Reflectance]
        Landsat_NDVI[Landsat<br>70m<br>NDVI]
        Sentinel_reflectance[HLS<br>Sentinel<br>30m<br>Surface<br>Reflectance]
        Sentinel_upsampled[Upsampled<br>Sentinel<br>70m<br>Surface<br>Reflectance]
        Sentinel_NDVI[Sentinel<br>70m<br>NDVI]
        Landsat_albedo[Landsat<br>70m<br>Albedo]
        Sentinel_albedo[Sentinel<br>70m<br>Albedo]
    end

    subgraph bayesian_state[Bayesian State]
        NDVI_covariance_prior[NDVI<br>Fine-Coarse<br>Covariance<br>Prior<br>from<br>Previous<br>Overpass]
        NDVI_covariance_posterior[NDVI<br>Fine-Coarse<br>Covariance<br>Posterior<br>for<br>Next<br>Overpass]
        albedo_covariance_prior[Albedo<br>Fine-Coarse<br>Covariance<br>Prior<br>from<br>Previous<br>Overpass]
        albedo_covariance_posterior[Albedo<br>Fine-Coarse<br>Covariance<br>Posterior<br>for<br>Next<br>Overpass]
    end

    fine_NDVI_input[NDVI<br>70m<br>Composite]
    NDVI_data_fusion[STARS.jl<br>NDVI<br>Data<br>Fusion]
    fine_NDVI_output[Fused<br>30m<br>NDVI]
    fine_NDVI_uncertainty[NDVI<br>Uncertainty]

    fine_albedo_input[Albedo<br>70m<br>Composite]
    albedo_data_fusion[STARS.jl<br>Albedo<br>Data<br>Fusion]
    fine_albedo_output[Fused<br>30m<br>Albedo]
    fine_albedo_uncertainty[Albedo<br>Uncertainty]

    SBG_L2T_STARS(ECOSTRESS<br>L2T<br>STARS<br>NDVI<br>&<br>Albedo<br>Product)

    VNP09GA_I --> VIIRS_downscaling
    VNP09GA_M --> VIIRS_downscaling
    VIIRS_downscaling --> VNP09GA_downscaled
    VNP09GA_downscaled --> VNP43_BRDF
    VNP43_BRDF --> VIIRS_corrected
    VIIRS_corrected --> VIIRS_NDVI
    VIIRS_corrected --> VIIRS_albedo

    Landsat_reflectance --> Landsat_upsampled
    Sentinel_reflectance --> Sentinel_upsampled

    Landsat_upsampled --> Landsat_NDVI
    Sentinel_upsampled --> Sentinel_NDVI

    Landsat_upsampled --> Landsat_albedo
    Sentinel_upsampled --> Sentinel_albedo

    Landsat_NDVI --> fine_NDVI_input
    Sentinel_NDVI --> fine_NDVI_input
    fine_NDVI_input --> NDVI_data_fusion
    VIIRS_NDVI --> NDVI_data_fusion
    NDVI_covariance_prior --> NDVI_data_fusion
    NDVI_data_fusion --> fine_NDVI_output
    NDVI_data_fusion --> fine_NDVI_uncertainty
    NDVI_data_fusion --> NDVI_covariance_posterior

    Landsat_albedo --> fine_albedo_input
    Sentinel_albedo --> fine_albedo_input
    fine_albedo_input --> albedo_data_fusion
    VIIRS_albedo --> albedo_data_fusion
    albedo_covariance_prior --> albedo_data_fusion
    albedo_data_fusion --> fine_albedo_output
    albedo_data_fusion --> fine_albedo_uncertainty
    albedo_data_fusion --> albedo_covariance_posterior

    fine_NDVI_output --> SBG_L2T_STARS
    fine_NDVI_uncertainty --> SBG_L2T_STARS
    fine_albedo_output --> SBG_L2T_STARS
    fine_albedo_uncertainty --> SBG_L2T_STARS

    click VNP43_BRDF "https://github.com/STARS-Data-Fusion/VNP43NRT.jl"
    click NDVI_data_fusion "https://github.com/STARS-Data-Fusion/STARS.jl"
    click albedo_data_fusion "https://github.com/STARS-Data-Fusion/STARS.jl"
```

*Figure 1. Flowchart of the ECOSTRESS Collection 3 L2T STARS processing workflow.*

NDVI and albedo are estimated at 70 m ECOSTRESS standard resolution with uncertainty for each UTC day in which there is an ECOSTRESS overpass by fusing temporally sparse but fine spatial resolution images from the Harmonized Landsat Sentinel (HLS) 2.0 product with daily, moderate spatial resolution images from the Suomi NPP Visible Infrared Imaging Radiometer Suite (VIIRS) VNP09GA product.

Landsat and Sentinel surface reflectances are collected using the [HLS.jl](https://github.com/STARS-Data-Fusion/HLS.jl) package.

VIIRS surface reflectance is downscaled and BRDF corrected using the [VNP43NRT.jl](https://github.com/STARS-Data-Fusion/VNP43NRT.jl) package. A pixelwise, lagged 16-day implementation of the VNP43 algorithm (Schaaf, 2017) is used for a near-real-time BRDF correction on the VNP09GA products to produce VIIRS NDVI and albedo.

The data fusion is performed with a variant of the Spatial Timeseries for Automated high-Resolution multi-Sensor data fusion (STARS) algorithm developed by Dr. Margaret Johnson and Gregory H. Halverson at the Jet Propulsion Laboratory using the [STARS.jl](https://github.com/STARS-Data-Fusion/STARS.jl) package. STARS is a Bayesian timeseries methodology that provides streaming data fusion and uncertainty quantification through efficient Kalman filtering. Operationally, each L2T STARS tile run loads the means and covariances of the STARS model saved from the most recent tile run, then iteratively advances the means and covariances forward each day updating with fine imagery from HLS and/or moderate resolution imagery from VIIRS up to the day of the target ECOSTRESS overpass. 

The layers of the L2T STARS product are listed in Table 2. All layers of this product are represented by 32-bit floating point arrays. The NDVI estimates and 1σ uncertainties (-UQ) are unitless from -1 to 1. The albedo estimates and 1σ uncertainties (-UQ) are proportions from 0 to 1. 

| **Name** | **Description** | **Type** | **Units** | **Fill Value** | **No Data Value** | **Valid Min** | **Valid Max** |**Scale Factor** | **Size** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | -- |
| NDVI | Normalized Difference Vegetation Index | float32 | Index | NaN | N/A | -1 | 1 | N/A | 13.4 mb |
| NDVI-UQ | Normalized Difference Vegetation Index Uncertainty | float32 | Index | NaN | N/A | -1 | 1 | N/A | 13.4 mb |
| albedo | Albedo | float32 | Ratio | NaN | N/A | 0 | 1 | N/A | 13.4 mb |
| albedo-UQ | Albedo Uncertainty | float32 | Ratio | NaN | N/A | 0 | 1 | N/A | 13.4 mb |

*Table 2. Listing of L2T STARS data layers.*

## Prerequisites

This is a Python package that calls Julia code. Julia must be installed in order to run this package.

## Authentication

This package requires an [EarthData](https://urs.earthdata.nasa.gov/) account and reads EarthData credentials from `~/.netrc` in the following format:

```
machine urs.earthdata.nasa.gov
login <USERNAME>
password <PASSWORD>
```

## Environment

On macOS, there are issues with installing `pykdtree` using pip, so it's better to use a mamba environment and install the `pykdtree` mamba package.

```
mamba create -y -n ECOv003-L2T-STARS -c conda-forge python=3.11 jupyter pykdtree 
mamba activate ECOv003-L2T-STARS
```

## Installation

Install this package from PyPi using the name `ECOv003-L2T-STARS` with dashes:

```
pip install ECOv003-L2T-STARS
```

You can also install development versions of this package directly from a clone of this repository:

```
pip install .
```

### Julia packages

pip cannot install Julia packages. After `pip install`, run this once to install the exact Julia package versions pinned in the package's `Manifest.toml` and check that every Julia import loads:

```
ECOv003-L2T-STARS-install-julia
```

To re-check an existing install (for example inside the Docker container) without installing anything, run `ECOv003-L2T-STARS-install-julia --verify-only`; it exits non-zero if the Julia version or any import is wrong.

This requires Julia 1.11 (the version the manifests were resolved with). The Dockerfile runs this step during the image build, and all Julia calls in this package run with `--project` pointing at that single pinned environment (data fusion and VNP43NRT share it).

## Usage

Import this package with the name `ECOv003_L2T_STARS` with underscores:

```
import ECOv003_L2T_STARS
```

### Command Line Usage

#### Command-Line Entry-Point for the `ECOv003-L2T-STARS` Product Generating Executable

```bash
ECOv003-L2T-STARS <runconfig> [--date YYYY-MM-DD] [--spinup-days DAYS] [--target-resolution METERS] [--ndvi-resolution METERS] [--albedo-resolution METERS] [--use-vnp43nrt | --no-vnp43nrt] [--calibrate-fine] [--sources-only] [--no-remove-input-staging] [--no-remove-prior] [--no-remove-posterior] [--threads COUNT] [--num-workers COUNT] [--version]
```

#### Command-Line Entry-Point for the `ECOv003-DL` Product Generating Executable

```
ECOv003_DL <runconfig_filename> [--tiles TILE_ID [TILE_ID ...]] [--version]
```

## References

Schaaf, C. B. et al. (2017). *Algorithm Theoretical Basis Document for MODIS Bidirectional Reflectance Distribution Function and Albedo (MOD43) Products*. NASA. [Link to source](https://lpdaac.usgs.gov/documents/110/MOD43_ATBD.pdf)
