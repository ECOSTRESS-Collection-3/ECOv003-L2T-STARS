# ECOSTRESS Collection 3 Level-2 STARS NDVI & Albedo Data Product User Guide

**ECOsystem Spaceborne Thermal Radiometer Experiment on Space Station (ECOSTRESS)**

**October 22, 2025**

## Authors

**Gregory H. Halverson**  
ECOSTRESS Science Team  
Jet Propulsion Laboratory  
California Institute of Technology

**Margaret Johnson**  
ECOSTRESS Science Team  
Jet Propulsion Laboratory  
California Institute of Technology

**Simon Hook**  
ECOSTRESS Science Team  
Jet Propulsion Laboratory  
California Institute of Technology

**Kerry Cawse-Nicholson**  
ECOSTRESS Science Team  
Jet Propulsion Laboratory  
California Institute of Technology

**Claire Villanueva-Weeks**  
ECOSTRESS Science Team  
Jet Propulsion Laboratory  
California Institute of Technology

---

*© 2025 California Institute of Technology. Government sponsorship acknowledged.*

**National Aeronautics and Space Administration**  
Jet Propulsion Laboratory  
4800 Oak Grove Drive  
Pasadena, California 91109-8099  
California Institute of Technology

This research was carried out at the Jet Propulsion Laboratory,
California Institute of Technology, under a contract with the National
Aeronautics and Space Administration.

Reference herein to any specific commercial product, process, or service
by trade name, trademark, manufacturer, or otherwise, does not
constitute or imply its endorsement by the United States Government or
the Jet Propulsion Laboratory, California Institute of Technology.

© 2025. California Institute of Technology. Government sponsorship
acknowledged.

---

This User Guide provides practical information for accessing, understanding, and using the ECOSTRESS Collection 3 Level-2 STARS NDVI & Albedo data products. It covers product specifications, data access procedures, file formats, quality assessment, and recommended processing workflows.

For detailed information on the scientific methodology, mathematical formulations, and algorithm implementation, please refer to the companion **ECOSTRESS Collection 3 Level-2 STARS NDVI & Albedo Algorithm Theoretical Basis Document (ATBD)**.

This guide is designed to be a living document that is updated as the products evolve and user feedback is incorporated.

**Contacts**

Readers seeking additional information about this product may contact
the following:

- Gregory Halverson\
  Jet Propulsion Laboratory\
  4800 Oak Grove Dr.\
  Pasadena, CA 91109\
  Email: <gregory.h.halverson@jpl.nasa.gov>\
  Office: (626) 660-6818

- Kerry Cawse-Nicholson\
  MS 183-601\
  Jet Propulsion Laboratory\
  4800 Oak Grove Dr.\
  Pasadena, CA 91109\
  Email: <kerry-anne.cawse-nicholson@jpl.nasa.gov>\
  Office: (818) 354-1594

- Margaret Johnson\
  Jet Propulsion Laboratory\
  4800 Oak Grove Dr.\
  Pasadena, CA 91109\
  Email: <maggie.johnson@jpl.nasa.gov>\
  Office: (818) 354-8885

- Simon Hook\
  MS 183-600\
  Jet Propulsion Laboratory\
  4800 Oak Grove Dr.\
  Pasadena, CA 91109\
  Email: <simon.j.hook@jpl.nasa.gov>\
  Office: (818) 354-0974



## Table of Contents

1. [Introduction](#introduction)
   - [Product Overview](#product-overview)
   - [Data Access and Availability](#data-access-and-availability)
   - [File Format and Structure](#file-format-and-structure)
2. [Product Specifications](#product-specifications)
   - [Data Layers](#data-layers)
   - [Quality Flags](#quality-flags)
   - [Spatial and Temporal Characteristics](#spatial-and-temporal-characteristics)
3. [Data Usage Guidelines](#data-usage-guidelines)
   - [Recommended Processing Workflow](#recommended-processing-workflow)
   - [Software Compatibility](#software-compatibility)
   - [Quality Assessment](#quality-assessment)
4. [Common Applications](#common-applications)
5. [Metadata](#metadata)
6. [Troubleshooting](#troubleshooting)
7. [Acknowledgements](#acknowledgements)
8. [References](#references)

### List of Tables

- Table 1: Listing of ECOSTRESS tiled products long names and short names
- Table 2: Listing of the L2T STARS data layers
- Table 3: StandardMetadata fields in L2T/L3T/L4T products
- Table 4: ProductMetadata fields in L2T/L3T/L4T products



# Introduction

## Product Overview

The ECOSTRESS Collection 3 Level-2 STARS NDVI & Albedo product (L2T_STARS) provides high-resolution (70 m) estimates of Normalized Difference Vegetation Index (NDVI) and broadband shortwave albedo that are temporally and spatially coincident with each ECOSTRESS Land Surface Temperature & Emissivity (L2T_LSTE) observation.

These products are generated using the **Spatial Timeseries for Automated high-Resolution multi-Sensor data fusion (STARS)** algorithm, which optimally combines:
- **High spatial resolution** data from Harmonized Landsat Sentinel (HLS) 2.0 products (30 m, 3-5 day revisit)
- **High temporal resolution** data from VIIRS VNP09GA products (500 m-1 km, daily coverage)

The result is gap-filled, analysis-ready NDVI and albedo data at ECOSTRESS resolution with quantified uncertainties, essential for evapotranspiration modeling and land surface analysis.

| **Product Long Name** | **Product Short Name** |
|---|---|
| STARS NDVI/Albedo | L2T STARS |
| Ecosystem Auxiliary Inputs | L3T ETAUX |
| Evapotranspiration Ensemble | L3T JET |
| DisALEXI-JPL Evapotranspiration | L3T ET ALEXI |
| Evaporative Stress Index | L4T ESI |
| DisALEXI-JPL Evaporative Stress Index | L4T ESI ALEXI |
| Water Use Efficiency | L4T WUE |

**Table 1.** Listing of ECOSTRESS tiled products long names and short names.

## File Format and Structure

### Cloud-Optimized GeoTIFF (COG) Format
All L2T_STARS products are distributed as Cloud-Optimized GeoTIFFs, providing:
- **Efficient streaming** and partial data access
- **Universal compatibility** with GIS software and programming libraries
- **Built-in pyramids** for multi-resolution visualization
- **Standardized georeferencing** with embedded spatial reference information

### Tiling System
- **Tiling scheme**: Modified Military Grid Reference System (MGRS) used by Sentinel-2
- **Tile size**: 109.8 km × 109.8 km
- **Pixel size**: 70 m × 70 m
- **Array dimensions**: 1,568 × 1,568 pixels per tile
- **Projection**: UTM zone-specific

### File Naming Convention
```
ECOSTRESS_L2T_STARS_[TileID]_[AcquisitionDateTime]_[ProductionDateTime]_[Version].tif
```

Example:
```
ECOSTRESS_L2T_STARS_T11SPS_20241008T183000_20241009T120000_02.tif
```

### File Components
Each L2T_STARS granule contains:
- **Data files**: Individual GeoTIFF files for each data layer
- **Browse images**: JPEG preview images for quick visualization
- **Metadata file**: JSON file with product and standard metadata
- **Quality layers**: Cloud and water masks

## Quality Flags

## Spatial and Temporal Characteristics

### Spatial Resolution
- **Native resolution**: 70 m × 70 m
- **Coordinate system**: UTM (zone-specific)
- **Resampling method**: Bilinear interpolation from input sources
- **Spatial extent**: Global land areas (±60° latitude)

### Temporal Resolution
- **Observation frequency**: Variable based on ISS orbit (typically 3-4 days)
- **Temporal coverage**: Daytime overpasses only
- **Data continuity**: Gap-filled using temporal fusion algorithm
- **Archive period**: 2018-present

## Quality Flags

### Standard Quality Masks
Two binary quality flags are provided as unsigned 8-bit integer layers:

- **cloud**: Cloud detection mask from L2 CLOUD product
  - 0 = Clear sky
  - 1 = Cloud detected

- **water**: Surface water body mask from SRTM DEM
  - 0 = Land surface
  - 1 = Open water surface

### Data Quality Indicators
- **Fill values**: NaN (Not-a-Number) for float32 data layers
- **Valid data range**: 
  - NDVI: -1.0 to 1.0
  - Albedo: 0.0 to 1.0
  - Uncertainties: 0.0 to maximum valid range

## Data Access and Availability

### Distribution and Access
The L2T_STARS products are distributed through:
- **NASA Earthdata**: https://earthdata.nasa.gov/
- **LP DAAC Data Pool**: https://e4ftl01.cr.usgs.gov/
- **NASA Worldview**: https://worldview.earthdata.nasa.gov/
- **AppEEARS**: https://appeears.earthdatacloud.nasa.gov/

### Data Latency
- **Near Real-Time**: Products are typically available within 1-3 days of ECOSTRESS observation
- **Reprocessing**: Historical data are reprocessed as algorithm improvements are implemented

### Spatial Coverage
- **Global land areas** excluding regions poleward of ±60° latitude
- **Tiled format** using modified MGRS tiling system
- **Individual tiles**: 109.8 km × 109.8 km at 70 m resolution

### Authentication Requirements
- NASA Earthdata Login account required for data access
- Free registration at: https://urs.earthdata.nasa.gov/

# Product Specifications

## Data Layers

The L2T_STARS product contains eight data layers providing NDVI and albedo estimates with associated uncertainties and bias corrections:

### Primary Data Products:
- **NDVI**: Normalized Difference Vegetation Index estimates
- **albedo**: Broadband shortwave albedo estimates

### Uncertainty Products:
- **NDVI-UQ**: One-sigma uncertainty of NDVI estimates
- **albedo-UQ**: One-sigma uncertainty of albedo estimates

### Bias Correction Products:
- **NDVI-bias**: Systematic bias correction applied to NDVI
- **albedo-bias**: Systematic bias correction applied to albedo
- **NDVI-bias-UQ**: Uncertainty in NDVI bias correction
- **albedo-bias-UQ**: Uncertainty in albedo bias correction

| **Layer Name** | **Description** | **Data Type** | **Units** | **Valid Range** | **Fill Value** | **File Size** |
|---|---|---|---|---|---|---|
| NDVI | Normalized Difference Vegetation Index | float32 | Dimensionless | -1.0 to 1.0 | NaN | 12.96 MB |
| NDVI-UQ | NDVI One-sigma Uncertainty | float32 | Dimensionless | 0.0 to 1.0 | NaN | 12.96 MB |
| NDVI-bias | NDVI Bias Correction | float32 | Dimensionless | Variable | NaN | 12.96 MB |
| NDVI-bias-UQ | NDVI Bias Uncertainty | float32 | Dimensionless | 0.0 to 1.0 | NaN | 12.96 MB |
| albedo | Broadband Shortwave Albedo | float32 | Dimensionless | 0.0 to 1.0 | NaN | 12.96 MB |
| albedo-UQ | Albedo One-sigma Uncertainty | float32 | Dimensionless | 0.0 to 1.0 | NaN | 12.96 MB |
| albedo-bias | Albedo Bias Correction | float32 | Dimensionless | Variable | NaN | 12.96 MB |
| albedo-bias-UQ | Albedo Bias Uncertainty | float32 | Dimensionless | 0.0 to 1.0 | NaN | 12.96 MB |

**Table 2.** L2T_STARS data layer specifications.

---

# Data Usage Guidelines

## Software Compatibility

### Python Libraries
- **rioxarray**: Recommended for xarray-based analysis
- **GDAL/rasterio**: Low-level raster operations
- **xarray**: Multi-dimensional data analysis
- **matplotlib/cartopy**: Visualization and mapping

### R Packages
- **terra**: Modern raster data handling
- **raster**: Traditional raster operations
- **stars**: Spatiotemporal data cubes
- **sf**: Spatial data manipulation

### Desktop GIS Software
- **QGIS**: Free, open-source GIS
- **ArcGIS**: Commercial GIS software
- **ENVI**: Specialized remote sensing software

### Command Line Tools
- **GDAL utilities**: gdalinfo, gdal_translate, gdalwarp
- **NCO operators**: For netCDF-like operations

## Quality Assessment

### Uncertainty Interpretation
The uncertainty values represent one-sigma (standard deviation) estimates from the STARS Kalman filtering algorithm. These values quantify the expected error in NDVI and albedo estimates due to:
- **Measurement noise** from input sensors
- **Temporal interpolation** when direct observations are unavailable  
- **Spatial downscaling** from coarse to fine resolution

**Relative uncertainty assessment:**
- **Lower uncertainty values** indicate more reliable estimates with recent, high-quality input observations
- **Higher uncertainty values** indicate greater reliance on temporal gap-filling or limited input data
- **Context-dependent interpretation**: Acceptable uncertainty levels vary by application and study requirements

**Recommended approach:**
- Examine uncertainty distributions for your specific study area and time period
- Compare uncertainty values with your application's accuracy requirements
- Use uncertainty values for weighted analysis or to identify pixels requiring field validation

### Recommended Quality Filters
1. **Remove cloudy pixels**: Use cloud mask
2. **Consider water pixels**: Apply water mask if studying land only
3. **Check uncertainty values**: Filter based on application requirements
4. **Validate against field data**: When available for your study area

### Common Quality Issues
- **High uncertainty near cloud edges**
- **Potential artifacts in mountainous terrain**
- **Reduced accuracy in very dense canopies**
- **Seasonal bias in high-latitude regions**

---

# Common Applications

## Scientific Research
- **Evapotranspiration modeling**: Primary input for ET algorithms
- **Vegetation monitoring**: Phenology and health assessment
- **Land surface energy balance**: Albedo for radiation modeling
- **Climate studies**: Surface property characterization

## Agricultural Applications
- **Crop health monitoring**: NDVI time series analysis
- **Irrigation management**: Water stress detection
- **Yield prediction**: Vegetation vigor assessment
- **Precision agriculture**: Field-scale variability mapping

## Environmental Monitoring
- **Drought assessment**: Vegetation stress indicators
- **Ecosystem health**: Biodiversity and conservation
- **Land cover change**: Deforestation and urbanization
- **Fire risk assessment**: Vegetation moisture content

## Operational Uses
- **Water resource management**: ET-based water budgets
- **Natural resource inventory**: Forest and rangeland assessment
- **Disaster response**: Rapid vegetation assessment
- **Policy support**: Environmental compliance monitoring

---

# Troubleshooting

## Common Issues and Solutions

### Data Access Problems
**Issue**: Cannot download data from LP DAAC
**Solution**: 
- Verify Earthdata Login credentials
- Check network connectivity
- Ensure proper authentication in download scripts

**Issue**: Files appear corrupted or incomplete
**Solution**:
- Re-download the file
- Verify file size matches expected size
- Check MD5 checksums if provided

### Data Processing Issues
**Issue**: Cannot open GeoTIFF files
**Solution**:
- Update GDAL to version 3.0 or higher
- Verify file integrity with `gdalinfo`
- Check for proper file extension (.tif)

**Issue**: Unexpected NaN values
**Solution**:
- Check cloud and water masks
- Verify data is within valid range
- Consider seasonal data availability

### Quality Assessment Problems
**Issue**: High uncertainty values everywhere
**Solution**:
- Check input data availability for that time period
- Verify geographic location (polar regions excluded)
- Consider atmospheric conditions (heavy aerosols, persistent clouds)

**Issue**: NDVI values seem unrealistic
**Solution**:
- Verify units (should be -1 to 1)
- Check for scaling issues in your software
- Compare with concurrent Landsat/Sentinel-2 data

### Performance Issues
**Issue**: Slow data loading
**Solution**:
- Use COG-aware libraries (rioxarray, GDAL 3.x)
- Implement spatial/temporal subsetting
- Consider using lower resolution overviews for exploration

## Getting Help

### Support Resources
- **LP DAAC User Services**: https://lpdaac.usgs.gov/contact-us/
- **ECOSTRESS Documentation**: https://ecostress.jpl.nasa.gov/
- **Earthdata Forum**: https://forum.earthdata.nasa.gov/

### Reporting Issues
When reporting data quality issues, please provide:
- Product name and version
- Specific tile ID and date
- Geographic coordinates of the issue
- Screenshots or data examples
- Description of expected vs. observed behavior

---

# Metadata

Each ECOSTRESS product bundle contains two sets of product metadata:

- ProductMetadata

- StandardMetadata

Each product contains a custom set of ProductMetadata attributes, as
listed in Table 4. The StandardMetadata attributes are consistent across
products at each orbit/scene, as listed in Table 3.

| Name | Type |
|---|---|
| AncillaryInputPointer | string |
| AutomaticQualityFlag | string |
| AutomaticQualityFlagExplanation | string |
| BuildID | string |
| CRS | string |
| CampaignShortName | string |
| CollectionLabel | string |
| DataFormatType | string |
| DayNightFlag | string |
| EastBoundingCoordinate | float |
| FieldOfViewObstruction | string |
| ImageLines | float |
| ImageLineSpacing | integer |
| ImagePixels | float |
| ImagePixelSpacing | integer |
| InputPointer | string |
| InstrumentShortName | string |
| LocalGranuleID | string |
| LongName | string |
| NorthBoundingCoordinate | float |
| PGEName | string |
| PGEVersion | string |
| PlatformLongName | string |
| PlatformShortName | string |
| PlatformType | string |
| ProcessingEnvironment | string |
| ProcessingLevelDescription | string |
| ProcessingLevelID | string |
| ProducerAgency | string |
| ProducerInstitution | string |
| ProductionDateTime | string |
| ProductionLocation | string |
| RangeBeginningDate | string |
| RangeBeginningTime | string |
| RangeEndingDate | string |
| RangeEndingTime | string |
| RegionID | string |
| SISName | string |
| SISVersion | string |
| SceneBoundaryLatLonWKT | string |
| SceneID | string |
| ShortName | string |
| SouthBoundingCoordinate | float |
| StartOrbitNumber | string |
| StopOrbitNumber | string |
| WestBoundingCoordinate | float |

**Table 3.** Name and type of metadata fields contained in the common StandardMetadata group in each L2T/L3T/L4T product.

| **Name** | **Type** |
|---|---|
| BandSpecification | float |
| NumberOfBands | integer |
| OrbitCorrectionPerformed | string |
| QAPercentCloudCover | float |
| QAPercentGoodQuality | float |
| AuxiliaryNWP | string |

**Table 4.** Name and type of metadata fields contained in the common ProductMetadata group in each L2T/L3T/L4T product.

# Acknowledgements

We would like to thank Joshua Fisher as the initial science lead of the
ECOSTRESS mission and PI of the ROSES project to re-design the ECOSTRESS products.

We would like to thank the HLS and VIIRS teams for providing the input data products that make STARS data fusion possible.

We would like to thank the entire ECOSTRESS Science Team for their contributions to algorithm development and product validation.

# References

## Primary Algorithm Reference
Johnson, M. C., G. Halverson, J. Susiluoto, K. Cawse-Nicholson, G. Hulley, and J. B. Fisher (2022), STARS: Spatial Timeseries for Automated high-Resolution multi-Sensor data fusion [Presentation], ECOSTRESS Science and Applications Team Meeting, Nov 2022, Ventura, CA.

## Related Documentation
- **ECOSTRESS L2T_STARS ATBD**: Algorithm Theoretical Basis Document for detailed methodology
- **HLS User Guide**: https://lpdaac.usgs.gov/documents/1698/HLS_User_Guide_V2.pdf
- **VIIRS Surface Reflectance Guide**: https://viirsland.gsfc.nasa.gov/PDF/VIIRS_Surf_Refl_UserGuide_v1.3.pdf

## Supporting References
Schaaf, C. (2017), MCD43A1 MODIS/Terra+Aqua BRDF/Albedo Model Parameters Daily L3 Global - 500m V006 [Data set], NASA EOSDIS Land Processes DAAC.

Liang, S. (2001), Narrowband to broadband conversions of land surface albedo I: Algorithms, *Remote Sensing of Environment*, *76*(2), 213-238.
