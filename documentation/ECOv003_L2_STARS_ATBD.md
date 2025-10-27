# ECOSTRESS Collection 3 Level-2 STARS NDVI & Albedo Algorithm Theoretical Basis Document

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

**Document Number:** ECOSTRESS Science Document no. D-1001465

---

**Contacts**

Readers seeking additional information about this product may contact
the following:

- Kerry Cawse-Nicholson\
  MS 183-601\
  Jet Propulsion Laboratory\
  4800 Oak Grove Dr.\
  Pasadena, CA 91109\
  Email: <kerry-anne.cawse-nicholson@jpl.nasa.gov>\
  Office: (818) 354-1594

- Gregory Halverson\
  Jet Propulsion Laboratory\
  4800 Oak Grove Dr.\
  Pasadena, CA 91109\
  Email: <gregory.h.halverson@jpl.nasa.gov>\
  Office: (626) 660-6818

- Simon Hook\
  MS 183-600\
  Jet Propulsion Laboratory\
  4800 Oak Grove Dr.\
  Pasadena, CA 91109\
  Email: <simon.j.hook@jpl.nasa.gov>\
  Office: (818) 354-0974

## Table of Contents

1. [Introduction](#introduction)
   - [Purpose](#purpose)
   - [Scope and Objectives](#scope-and-objectives)
2. [Parameter Description and Requirements](#parameter-description-and-requirements)
3. [STARS NDVI and Albedo Algorithm](#stars-ndvi-and-albedo-algorithm)
   - [Data Sources](#data-sources)
   - [BRDF Correction](#brdf-correction)
   - [Data Fusion Methodology](#data-fusion-methodology)
   - [Statistical Model](#statistical-model)
   - [Implementation](#implementation)
4. [Mask/Flag Derivation](#maskflag-derivation)
5. [Metadata](#metadata)
6. [Acknowledgements](#acknowledgements)
7. [References](#references)

---

## Introduction

### Purpose

The ECOSTRESS Collection 3 Level-2 STARS (Spatial Timeseries for Automated high-Resolution multi-Sensor data fusion) product provides coincident, gap-filled NDVI and albedo estimates at 70 m ECOSTRESS standard resolution for each daytime ECOSTRESS overpass. These products are essential auxiliary data inputs for evapotranspiration (ET) algorithms and other land surface modeling applications.

NDVI and albedo are critical biophysical parameters that capture vegetation health, phenology, and surface energy balance characteristics. The STARS algorithm addresses the challenge of providing high spatial resolution (70 m), temporally complete NDVI and albedo data by fusing observations from multiple satellite instruments with complementary spatial and temporal characteristics.

### Scope and Objectives

This Algorithm Theoretical Basis Document (ATBD) provides the scientific and technical foundation for the STARS algorithm. It includes:

1. A description of the NDVI and albedo parameter characteristics and requirements.
2. An overview of the STARS data fusion methodology and its theoretical foundation.
3. Mathematical formulations and statistical models.
4. Implementation details for near-real-time processing.
5. Quality assessment and uncertainty quantification approaches.

For practical information on data access, file formats, processing workflows, and applications, please refer to the companion **ECOSTRESS Collection 3 Level-2 STARS NDVI & Albedo Data Product User Guide**.

---

## Parameter Description and Requirements

### Attributes of STARS NDVI and Albedo Data

- **Spatial resolution:** 70 m x 70 m
- **Temporal resolution:** Diurnally varying to match ISS overpass characteristics
- **Latency:** Near real-time, as required by the ECOSTRESS Science Data System (SDS)
- **Spatial extent:** All land globally, excluding poleward ±60°

### Parameter Specifications

| Parameter | Description | Units | Range | Source Instruments |
|-----------|-------------|-------|-------|-------------------|
| NDVI | Normalized Difference Vegetation Index | Dimensionless | -1.0 to 1.0 | HLS 2.0, VIIRS VNP09GA |
| Albedo (α) | Broadband shortwave albedo | Dimensionless | 0.0 to 1.0 | HLS 2.0, VIIRS VNP09GA |

### Auxiliary Data Requirements

The STARS algorithm requires high-quality surface reflectance data from multiple satellite instruments to achieve both high spatial resolution and temporal continuity:

**Primary Data Sources:**
- **Harmonized Landsat Sentinel (HLS) 2.0**: 30 m spatial resolution, 3-5 day revisit
- **VIIRS VNP09GA**: 500 m spatial resolution for NDVI, 1 km for albedo, daily coverage

**Ancillary Data:**
- **GEOS-5 FP tavg3_2d_aer_Nx**: Aerosol optical depth for BRDF correction
- **Solar geometry**: Solar zenith angle for BRDF modeling

---

## STARS NDVI and Albedo Algorithm

The STARS algorithm produces coincident, gap-filled NDVI and albedo estimates at 70 m ECOSTRESS standard resolution through multi-instrument data fusion. This approach combines observations from high spatial resolution instruments (Sentinel-2A/B, Landsat-8/9) with moderate spatial but high temporal resolution instruments (VIIRS) to achieve both the spatial detail and temporal coverage required for ECOSTRESS applications.

### Data Sources

The STARS algorithm utilizes complementary satellite data sources that provide different spatial-temporal trade-offs:

| Resolution Category | NDVI Source | Albedo Source | Characteristics |
|---------------------|-------------|---------------|-----------------|
| **High Spatial (<100 m)** | HLS 2.0 (30 m) | HLS 2.0 (30 m) | 3-5 day revisit, high spatial detail |
| **High Temporal (daily)** | VIIRS VNP09GA (500 m) | VIIRS VNP09GA (1 km) | Daily coverage, moderate resolution |

### BRDF Correction

Prior to data fusion, a pixelwise, lagged 16-day implementation of the VNP43 algorithm (Schaaf, 2017) is used for near-real-time bi-directional reflectance function (BRDF) correction on the VNP09GA reflectance products. This produces VIIRS nadir BRDF-adjusted red and near-infrared reflectance at 500 m resolution for NDVI calculation, and 1 km estimates of black-sky albedo ($a_{black}$) and white-sky albedo ($a_{white}$) for VIIRS M-bands 1, 2, 3, 4, 5, 7, 8, 10, and 11.

Blue-sky albedo ($a_{blue}$) for each band is calculated as:

$$a_{blue} = SKYL \cdot a_{white} + (1 - SKYL) \cdot a_{black}$$

where $SKYL$ is the fraction of diffuse skylight determined from a look-up table based on solar zenith angle and aerosol optical depth (AOD) retrieved from GEOS-5 FP tavg3_2d_aer_Nx.

The broadband blue-sky albedo is calculated using a weighted sum of the VIIRS M-band blue-sky albedo estimates with near-to-broadband (NTB) coefficients:

**VIIRS M-band Near-to-Broadband Coefficients:**

| VIIRS M-Band | NTB Coefficient |
|--------------|-----------------|
| 1 | 0.2418 |
| 2 | -0.201 |
| 3 | 0.2093 |
| 4 | 0.1146 |
| 5 | 0.1146 |
| 7 | 0.1348 |
| 8 | 0.2251 |
| 10 | 0.1123 |
| 11 | 0.0860 |
| **Offset** | **-0.0131** |

Near-to-broadband albedo is estimated from the Harmonized Landsat Sentinel (HLS) products using sensor-specific coefficients. The 30 m albedo estimates from HLS are up-sampled to the 70 m ECOSTRESS standard resolution prior to data fusion.

**Sentinel-2A/B Near-to-Broadband Coefficients:**

| Band | NTB Coefficient |
|------|-----------------|
| 2 | 0.1324 |
| 3 | 0.1269 |
| 4 | 0.1051 |
| 5 | 0.0971 |
| 6 | 0.0890 |
| 7 | 0.0818 |
| 8 | 0.0722 |
| 11 | 0.0167 |
| **Offset** | **0.0002** |

**Landsat-8 Near-to-Broadband Coefficients:**

| Band | NTB Coefficient |
|------|-----------------|
| 2 | 0.356 |
| 3 | 0.13 |
| 4 | 0.373 |
| 5 | 0.085 |
| 6 | 0.072 |
| **Offset** | **-0.018** |

### Data Fusion Methodology

The data fusion is performed using the Spatial Timeseries for Automated high-Resolution multi-Sensor data fusion (STARS) methodology (Johnson et al., 2022). STARS is a statistical, state-space timeseries methodology that provides streaming data fusion and uncertainty quantification through efficient Kalman filtering.

### Statistical Model

For ECOSTRESS, the STARS method is implemented separately for NDVI and albedo. Let $x_{i,t}$ represent NDVI/albedo to be estimated in the $i^{th}$ 70 m ECOSTRESS resolution pixel on day $t$. Let $Y_{i,t}^{f}$ represent measurements from high spatial resolution instruments at the $i^{th}$ 70 m pixel (note that $Y_{i,t}^{f}$ is missing if there are no high spatial resolution overpasses on day $t$). Let $Y_{j,t}^{c}$ represent the coarse spatial resolution VIIRS measurement at the $j^{th}$ cell in the VIIRS resolution grid (~500 m for NDVI, ~1 km for albedo), and let $A_j$ be the set of all 70 m pixels overlapped by the VIIRS pixel.

The statistical model for ECOSTRESS STARS has the following form:

**Observation Equations:**

$$Y_{j,t}^{c} = \frac{1}{|A_j|}\sum_{i \in A_j} x_{i,t} + \epsilon_{j,t}^{c} \quad \text{where} \quad \epsilon_{j,t}^{c} \sim \text{Normal}(0,\sigma_c^2) \quad (1a)$$

$$Y_{i,t}^{f} = x_{i,t} + \epsilon_{i,t}^{f} \quad \text{where} \quad \epsilon_{i,t}^{f} \sim \text{Normal}(0,\sigma_f^2) \quad (1b)$$

**State Evolution Equation:**

$$x_{i,t} = x_{i,t-1} + \omega_{i,t} \quad \text{where} \quad \omega_{i,t} \sim \text{GP}(0, \tau^2, K(\cdot)) \quad (2)$$

where:

- Equations (1a,b) describe the instrument measurements as noisy observations of the target high-resolution image values $x_{i,t}$
- VIIRS measurements (1a) represent spatial aggregates over the coarse resolution grid
- Measurement errors are mean-zero and normally distributed with standard deviations $\sigma_c, \sigma_f$ for coarse and fine instruments, respectively
- Equation (2) describes day-to-day temporal dependence in NDVI/albedo through a first-order Markov chain
- Pixel-level changes between days ($\omega_{i,t}$) follow a Gaussian process (GP) with covariance function $K(\cdot)$, modeling spatial correlation of day-to-day changes between pixels
- The standard deviation parameter $\tau$ constrains the expected magnitude of change

To achieve scalability, STARS is implemented using a block-wise, moving window approach where blocks are defined by the coarse resolution grid plus a spatial buffer region.

### Implementation

For $x_t = (\ldots, x_{i,t}, \ldots)$ the vector of the $n$ target image pixels within a block on day $t$, and $y_t$ the stacked vector of available coarse and fine measurements, the timeseries model above induces the full state space model:

**State Space Formulation:**

$$y_t = F_t x_t + \epsilon_t \quad \text{where} \quad \epsilon_t \sim \text{MultivariateNormal}(0, V) \quad (3)$$

$$x_t = x_{t-1} + \omega_t \quad \text{where} \quad \omega_t \sim \text{MultivariateNormal}(0, W) \quad (4)$$

where:
- $V$ is a diagonal matrix with elements $\sigma_f^2, \sigma_c^2$
- $F_t$ is the aggregation matrix linking coarse and fine measurements to the target resolution grid (equations 1a,b)

The estimation of the target 70 m NDVI/albedo images on day $t$ is inferred through the posterior distribution of $x_t$ given all past and current measurements up to day $t$. This distribution is Gaussian with mean $m_t$ and covariance $C_t$. The mean provides the estimated imagery, while the covariance provides quantified uncertainties characterizing uncertainty due to spatial and temporal downscaling.

**Kalman Filtering:**

Estimates of $m_t$ and $C_t$ are obtained recursively through Kalman filtering equations (Kalman, 1960). Given estimates of $m_t$, $C_t$, and new observations on day $t+1$ ($y_{t+1}$), the updated estimates are calculated as:

$$m_{t+1} = m_t + K_{t+1}(y_{t+1} - F_{t+1}m_t) \quad (5)$$

$$C_{t+1} = (I - K_{t+1}F_{t+1})(C_t + W) \quad (6)$$

where the Kalman gain matrix is:

$$K_{t+1} = (C_t + W)F_{t+1}^T[F_{t+1}(C_t + W)F_{t+1}^T + V]^{-1}$$

If no new measurements are available on day $t+1$, the mean estimate is propagated forward ($m_{t+1} = m_t$) but the covariance is increased ($C_{t+1} = C_t + W$), quantifying increased uncertainty in fused estimates due to lack of available data.

**Key Advantages of STARS:**

1. **Automated spatial and temporal gap-filling**: Provides complete coverage even when individual sensors have data gaps
2. **Uncertainty quantification**: Pixel-wise uncertainties are calculated and distributed as data layers
3. **Near-real-time capability**: Efficient streaming processing for operational applications
4. **Multi-scale integration**: Optimally combines data from different spatial and temporal scales

**Near-Real-Time Processing:**

STARS NDVI/albedo products corresponding to each daytime L2T LSTE product are produced by:

1. Loading the means and covariances from the previous L2T LSTE product day
2. Downloading available measurements (VIIRS, HLS, etc.) between overpasses
3. Kalman filtering forward the NDVI/albedo estimates to the current target day

The latency of this operation depends on the availability of input products. The coincident STARS NDVI and albedo products, along with their pixel-wise uncertainties, are recorded in the L2T STARS product.

---

## Quality Assessment and Uncertainty Quantification

The STARS algorithm incorporates quality assessment at the input processing stage and provides uncertainty quantification in the final products:

**Input Data Quality Processing:**
- **VIIRS quality assessment**: VNP09GA and VNP43 products include quality flags that are used during BRDF processing
- **Cloud masking**: Applied during VIIRS data processing to exclude contaminated observations
- **BRDF model quality**: Assessment of BRDF model fit quality affects the reliability of VIIRS inputs

**STARS Product Uncertainty Quantification:**
The STARS algorithm provides pixel-wise uncertainty estimates through the Kalman filtering framework:
- **NDVI uncertainty**: Standard deviation of the posterior NDVI estimate
- **Albedo uncertainty**: Standard deviation of the posterior albedo estimate
- **Uncertainty sources**: Quantifies uncertainty from measurement noise, temporal interpolation, and spatial downscaling

**Data Availability Indicator:**
The algorithm generates a binary flag indicating whether high-resolution HLS observations were available within a 7-day window of the target date. This flag helps users assess the degree to which estimates rely on temporal gap-filling versus direct observations.

---

## Metadata

### NDVI Specifications
- **Unit of measurement:** Dimensionless
- **Range of measurement:** -1.0 to 1.0
- **Data type:** Float32
- **No data value:** -9999
- **Valid range:** -1.0 to 1.0

### Albedo Specifications  
- **Unit of measurement:** Dimensionless
- **Range of measurement:** 0.0 to 1.0
- **Data type:** Float32
- **No data value:** -9999
- **Valid range:** 0.0 to 1.0

### Common Attributes
- **Projection:** ECOSTRESS swath (L2T_LSTE grid)
- **Spatial resolution:** 70 m x 70 m
- **Temporal resolution:** Dynamically varying with precessing ISS overpass
- **Spatial extent:** All land globally, excluding poleward ±60°
- **Processing level:** Level-2 (L2T)
- **Latency:** Near real-time
- **Data availability flag:** Binary indicator of HLS observation recency

### Uncertainty Layers
- **NDVI uncertainty:** Standard deviation of NDVI estimate
- **Albedo uncertainty:** Standard deviation of albedo estimate
- **Data type:** Float32
- **Units:** Same as corresponding parameter

---

## Acknowledgements

We thank Gregory Halverson, Laura Jewell, Gregory Moore, Caroline Famiglietti, Munish Sikka, Manish Verma, Kevin Tu, Alexandre Guillaume, Kaniska Mallick, Youngryel Ryu, and Hideki Kobayashi for their contributions to the algorithm development described in this ATBD.

---

## References

Iqbal, M. (2012), *An Introduction to Solar Radiation*, Academic Press.

Iwabuchi, H. (2006), Efficient Monte Carlo methods for radiative transfer modeling, *Journal of the Atmospheric Sciences*, *63*(9), 2324-2339. doi: [https://doi.org/10.1175/JAS3755.1](https://doi.org/10.1175/JAS3755.1)

Johnson, M. C., G. Halverson, J. Susiluoto, K. Cawse-Nicholson, G. Hulley, and J. B. Fisher (2022), STARS: Spatial Timeseries for Automated high-Resolution multi-Sensor data fusion [Presentation], ECOSTRESS Science and Applications Team Meeting, Nov 2022, Ventura, CA. [https://ecostress.jpl.nasa.gov/downloads/science_team_meetings/2022/nov2022/](https://ecostress.jpl.nasa.gov/downloads/science_team_meetings/2022/nov2022/)

Kalman, R. E. (1960), A new approach to linear filtering and prediction problems, *Transactions of the ASME–Journal of Basic Engineering*, *82*(Series D), 35-45. doi: [https://doi.org/10.1115/1.3662552](https://doi.org/10.1115/1.3662552)

Kobayashi, H., and H. Iwabuchi (2008), A coupled 1-D atmosphere and 3-D canopy radiative transfer model for canopy reflectance, light environment, and photosynthesis simulation in a heterogeneous landscape, *Remote Sensing of Environment*, *112*(1), 173-185. doi: [https://doi.org/10.1016/j.rse.2007.04.010](https://doi.org/10.1016/j.rse.2007.04.010)

Liang, S. (2001), Narrowband to broadband conversions of land surface albedo I: Algorithms, *Remote Sensing of Environment*, *76*(2), 213-238. doi: [https://doi.org/10.1016/S0034-4257(00)00205-4](https://doi.org/10.1016/S0034-4257(00)00205-4)

Roesch, A., C. Schaaf, and F. Gao (2004), Use of Moderate-Resolution Imaging Spectroradiometer bidirectional reflectance distribution function products to enhance simulated surface albedos, *Journal of Geophysical Research*, *109*(D12), D12105. doi: [https://doi.org/10.1029/2004JD004552](https://doi.org/10.1029/2004JD004552)

Schaaf, C. (2017), MCD43A1 MODIS/Terra+Aqua BRDF/Albedo Model Parameters Daily L3 Global - 500m V006 [Data set], NASA EOSDIS Land Processes DAAC. doi: [https://doi.org/10.5067/MODIS/MCD43A1.006](https://doi.org/10.5067/MODIS/MCD43A1.006)

Vanino, S., A. Nino, C. De Michele, G. Falanga Bolognesi, G. D'Urso, T. Di Bene, G. Pennelli, G. Vuolo, F. Farina, A. Puglisi, and L. Puccionia (2018), Capability of Sentinel-2 data for estimating maximum evapotranspiration and irrigation requirements for tomato crop in Central Italy, *Remote Sensing of Environment*, *215*, 452-470. doi: [https://doi.org/10.1016/j.rse.2018.06.035](https://doi.org/10.1016/j.rse.2018.06.035)

Baldocchi, D. (2008), \'Breathing\' of the terrestrial biosphere:
lessons learned from a global network of carbon dioxide flux measurement
systems, *Australian Journal of Botany*, *56*, 1-26. doi:
https://doi.org/10.1071/BT07151

Baldocchi, D., E. Falge, L. H. Gu, R. J. Olson, D. Hollinger, S. W.
Running, P. M. Anthoni, C. Bernhofer, K. Davis, R. Evans, J. Fuentes, A.
Goldstein, G. Katul, B. E. Law, X. H. Lee, Y. Malhi, T. Meyers, W.
Munger, W. Oechel, K. T. P. U, K. Pilegaard, H. P. Schmid, R. Valentini,
S. Verma, T. Vesala, K. Wilson, and S. C. Wofsy (2001), FLUXNET: A new
tool to study the temporal and spatial variability of ecosystem-scale
carbon dioxide, water vapor, and energy flux densities, *Bulletin of the
American Meteorological Society*, *82*(11), 2415-2434. doi:
https://doi.org/10.1175/1520-0477(2001)082\<2415:FANTTS\>2.3.CO;2

Bi, L., P. Yang, G. W. Kattawar, Y.-X. Hu, and B. A. Baum (2011),
Diffraction and external reflection by dielectric faceted particles, *J.
Quant. Spectrosc. Radiant. Transfer*, *112*, 163-173. doi:
https://doi.org/10.1016/j.jqsrt.2010.02.007

Bisht, G., V. Venturini, S. Islam, and L. Jiang (2005), Estimation of
the net radiation using MODIS (Moderate Resolution Imaging
Spectroradiometer), *Remote Sensing of Environment*, *97*, 52-67.doi:
https://doi.org/10.1016/j.rse.2005.03.014

Bouchet, R. J. (1963), Evapotranspiration re´elle evapotranspiration
potentielle, signification climatique*Rep. Publ. 62*, 134-142 pp, Int.
Assoc. Sci. Hydrol., Berkeley, California. doi:

Chen, X., H. Wei, P. Yang, and B. A. Baum (2011), An efficient method
for computing atmospheric radiances in clear-sky and cloudy conditions,
*J. Quant. Spectrosc. Radiant. Transfer*, *112*, 109-118. doi:
https://doi.org/10.1016/j.jqsrt.2010.08.013

Chen, Y., J. Xia, S. Liang, J. Feng, J. B. Fisher, X. Li, X. Li, S. Liu,
Z. Ma, and A. Miyata (2014), Comparison of satellite-based
evapotranspiration models over terrestrial ecosystems in China, *Remote
Sensing of Environment*, *140*, 279-293. doi:
https://doi.org/10.1016/j.rse.2013.08.045

Coll, C., Z. Wan, and J. M. Galve (2009), Temperature-based and
radiance-based validations of the V5 MODIS land surface temperature
product, *Journal of Geophysical Research*, *114*(D20102), doi:
https://doi.org/10.1029/2009JD012038.

Ershadi, A., M. F. McCabe, J. P. Evans, N. W. Chaney, and E. F. Wood
(2014), Multi-site evaluation of terrestrial evaporation models using
FLUXNET data, *Agricultural and Forest Meteorology*, *187*, 46-61. doi:
https://doi.org/10.1016/j.agrformet.2013.11.008

Famiglietti, C. A., J. B. Fisher, G. Halverson, and E. E. Borbas (2018),
Global validation of MODIS near-surface air and dew point temperatures,
*Geophysical Research Letters*, *45*, 1-9. doi:
https://doi.org/10.1029/2018GL077813

Fisher, J. B., K. Tu, and D. D. Baldocchi (2008), Global estimates of
the land-atmosphere water flux based on monthly AVHRR and ISLSCP-II
data, validated at 16 FLUXNET sites, *Remote Sensing of Environment*,
*112*(3), 901-919. doi: https://doi.org/10.1016/j.rse.2007.06.025

Fisher, J. B., R. H. Whittaker, and Y. Malhi (2011), ET Come Home: A
critical evaluation of the use of evapotranspiration in geographical
ecology, *Global Ecology and Biogeography*, *20*, 1-18. doi:
https://doi.org/10.1111/j.1466-8238.2010.00578.

Fisher, J. B., D. D. Baldocchi, L. Misson, T. E. Dawson, and A. H.
Goldstein (2007), What the towers don\'t see at night: Nocturnal sap
flow in trees and shrubs at two AmeriFlux sites in California, *Tree
Physiology*, *27*(4), 597-610. doi:
https://doi.org/10.1093/treephys/27.4.597

Fisher, J. B., S. Hook, R. Allen, M. Anderson, A. French, C. Hain, G.
Hulley, and E. Wood (2014), The ECOsystem Spaceborne Thermal Radiometer
Experiment on Space Station (ECOSTRESS): science motivation, paper
presented at American Geophysical Union Fall Meeting, San Francisco.

Fisher, J. B., F. Melton, E. Middleton, C. Hain, M. Anderson, R. Allen,
M. F. McCabe, S. Hook, D. Baldocchi, P. A. Townsend, A. Kilic, K. Tu, D.
D. Miralles, J. Perret, J.-P. Lagouarde, D. Waliser, A. J. Purdy, A.
French, D. Schimel, J. S. Famiglietti, G. Stephens, and E. F. Wood
(2017), The future of evapotranspiration: Global requirements for
ecosystem functioning, carbon and climate feedbacks, agricultural
management, and water resources, *Water Resources Research*, *53*,
2618-2626. doi: https://doi.org/10.1002/2016WR020175

Fisher, J. B., Y. Malhi, A. C. de Araújo, D. Bonal, M. Gamo, M. L.
Goulden, T. Hirano, A. Huete, H. Kondo, T. Kumagai, H. W. Loescher, S.
Miller, A. D. Nobre, Y. Nouvellon, S. F. Oberbauer, S. Panuthai, C. von
Randow, H. R. da Rocha, O. Roupsard, S. Saleska, K. Tanaka, N. Tanaka,
and K. P. Tu (2009), The land-atmosphere water flux in the tropics,
*Global Change Biology*, *15*, 2694-2714. doi:
https://doi.org/10.1111/j.1365-2486.2008.01813.x

García, M., I. Sandholt, P. Ceccato, M. Ridler, E. Mougin, L. Kergoat,
L. Morillas, F. Timouk, R. Fensholt, and F. Domingo (2013), Actual
evapotranspiration in drylands derived from in-situ and satellite data:
Assessing biophysical constraints, *Remote Sensing of Environment*,
*131*, 103-118. doi: https://doi.org/10.1016/j.rse.2012.12.016

Goulden, M. L., J. W. Munger, S. M. Fan, B. C. Daube, and S. C. Wofsy
(1996), Measurements of carbon sequestration by long-term eddy
covariance: methods and a critical evaluation of accuracy, *Global
Change Biology*, *2*, 169-182. doi:
https://doi.org/10.1111/j.1365-2486.1996.tb00070.x

Halverson, G., M. Barker, S. Cooley, and S. Pestana (2016), Costa Rica
agriculture: applying ECOSTRESS diurnal cycle land surface temperature
and evapotranspiration to agricultural soil and water management*Rep.*

Iqbal, M. (2012), *An introduction to solar radiation*, Elsevier.

Iwabuchi, H. (2006), Efficient Monte Carlo Methods for Radiative
Transfer Modeling, *Journal of the Atmospheric Sciences*, *63*(9),
2324-2339. doi: https://doi.org/10.1175/JAS3755.1

Johnson, M. C., G. Halverson, J. Susiluoto, K. Cawse-Nicholson, G.
Hulley, and J. B. Fisher, (2022) STARS: Spatial Timeseries for Automated
high-Resolution multi-Sensor data fusion \[Presentation\], ECOSTRESS
Science and Applications Team Meeting, Nov 2022, Ventura, CA.
https://ecostress.jpl.nasa.gov/downloads/science_team_meetings/2022/nov2022/

June, T., J. R. Evans, and G. D. Farquhar (2004), A simple new equation
for the reversible temperature dependence of photosynthetic electron
transport: a study on soybean leaf, *Functional Plant Biology*, *31*(3),
275-283. doi: https://doi.org/10.1071/FP03250

Jung, M., M. Reichstein, and A. Bondeau (2009), Towards global empirical
upscaling of FLUXNET eddy covariance observations: validation of a model
tree ensemble approach using a biosphere model, *Biogeosciences*, *6*,
2001-2013. doi: https://doi.org/10.5194/bg-6-2001-2009

Kirtman, B. P., Min, D., Infanti, J. M., Kinter, J. L., III, Paolino, D.
A., Zhang, Q., van den Dool, H., Saha, S., Mendez, M. P., Becker, E.,
Peng, P., Tripp, P., Huang, J., DeWitt, D. G., Tippett, M. K., Barnston,
A. G., Li, S., Rosati, A., Schubert, S. D., Rienecker, M., Suarez, M.,
Li, Z. E., Marshak, J., Lim, Y., Tribbia, J., Pegion, K., Merryfield, W.
J., Denis, B., & Wood, E. F. (2014). The North American Multimodel
Ensemble: Phase-1 Seasonal-to-Interannual Prediction; Phase-2 toward
Developing Intraseasonal Prediction, *Bulletin of the American
Meteorological Society*, *95*(4), 585-601. doi:
https://doi.org/10.1175/BAMS-D-12-00050.1

Kobayashi, H., and H. Iwabuchi (2008), A coupled 1-D atmosphere and 3-D
canopy radiative transfer model for canopy reflectance, light
environment, and photosynthesis simulation in a heterogeneous landscape,
*Remote Sensing of Environment*, *112*(1), 173-185. doi:
10.1016/j.rse.2007.04.010

Lagouarde, J., and Y. Brunet (1993), A simple model for estimating the
daily upward longwave surface radiation flux from NOAA-AVHRR data,
*International Journal of Remote Sensing*, *14*(5), 907-925. doi:
https://doi.org/10.1080/01431169308904386

Liang, X., D. P. Lettenmaier, E. Wood, and S. J. Burges (1994), A simple
hydrologically based model of land surface water and energy fluxes for
general circulation models, *Journal of Geophysical Research*, *99*(D7),
14415-14428. doi: https://doi.org/10.1029/94JD00483

Mallick, K., A. Jarvis, J. B. Fisher, K. P. Tu, E. Boegh, and D. Niyogi
(2013), Latent heat flux and canopy conductance based on
Penman-Monteith, Priestley-Taylor equation, and Bouchet's complementary
hypothesis, *Journal of Hydrometeorology*, *14*, 419-442. doi:
https://doi.org/10.1175/JHM-D-12-0117.1

Mallick, K., A. J. Jarvis, E. Boegh, J. B. Fisher, D. T. Drewry, K. P.
Tu, S. J. Hook, G. Hulley, J. Ardö, and J. Beringer (2014), A Surface
Temperature Initiated Closure (STIC) for surface energy balance fluxes,
*Remote Sensing of Environment*, *141*, 243-261. doi:
https://doi.org/10.1016/j.rse.2013.10.022

Mallick, K., Boegh, E., Trebs, I., Alfieri, J. G., Kustas, W. P.,
Prueger, J. H., \... & Jarvis, A. J. (2015). Reintroducing radiometric
surface temperature into the P enman‐M onteith formulation. *Water
Resources Research*, *51*(8), 6214-6243. doi:
https://doi.org/10.1002/2014WR016106

Mallick, K., Toivonen, E., Trebs, I., Boegh, E., Cleverly, J., Eamus,
D., \... & Garcia, M. (2018). Bridging Thermal Infrared Sensing and
Physically‐Based Evapotranspiration Modeling: From Theoretical
Implementation to Validation Across an Aridity Gradient in Australian
Ecosystems. *Water Resources Research*, *54*(5), 3409-3435. doi:
https://doi.org/10.1029/2017WR021357

Mallick, K., Baldocchi, D., Jarvis, A., Hu, T., Trebs, I., Sulis, M.,
\... & Kustas, W. P. (2022). Insights Into the Aerodynamic Versus
Radiometric Surface Temperature Debate in Thermal‐Based Evaporation
Modeling. *Geophysical Research Letters*, *49*(15), e2021GL097568. doi:
https://doi.org/10.1029/2021GL097568

McCabe, M. F., A. Ershadi, C. Jimenez, D. G. Miralles, D. Michel, and E.
F. Wood (2016), The GEWEX LandFlux project: evaluation of model
evaporation using tower-based and globally gridded forcing data,
*Geosci. Model Dev.*, *9*(1), 283-305. doi:
https://doi.org/10.5194/gmd-9-283-2016

Michel, D., C. Jiménez, D. Miralles, M. Jung, M. Hirschi, A. Ershadi, B.
Martens, M. McCabe, J. Fisher, and Q. Mu (2016), TheWACMOS-ET
project--Part 1: Tower-scale evaluation of four remote-sensing-based
evapotranspiration algorithms, *Hydrology and Earth System Sciences*,
*20*(2), 803-822. doi: https://doi.org/10.3929/ethz-a-010611421

Miralles, D., C. Jiménez, M. Jung, D. Michel, A. Ershadi, M. McCabe, M.
Hirschi, B. Martens, A. Dolman, and J. Fisher (2016), The WACMOS-ET
project, part 2: evaluation of global terrestrial evaporation data sets,
*Hydrology and Earth System Sciences*, *20*(2), 823-842. doi:
https://doi.org/10.5194/hess-20-823-2016

Miralles, D. G., T. R. H. Holmes, R. A. M. De Jeu, J. H. Gash, A. G. C.
A. Meesters, and A. J. Dolman (2011), Global land-surface evaporation
estimated from satellite-based observations, *Hydrol. Earth Syst. Sci.*,
*15*(2), 453-469. doi: https://doi.org/10.5194/hess-15-453-2011

Monteith, J. L. (1965), Evaporation and the environment, *Symposium of
the Society of Exploratory Biology*, *19*, 205-234.

Mu, Q., M. Zhao, and S. W. Running (2011), Improvements to a MODIS
global terrestrial evapotranspiration algorithm, *Remote Sensing of
Environment*, *111*, 519-536. doi:
https://doi.org/10.1016/j.rse.2011.02.01

Papale, D., and A. Valentini (2003), A new assessment of European
forests carbon exchange by eddy fluxes and artificial neural network
spatialization, *Global Change Biology*, *9*, 525-535. doi:
https://doi.org/10.1046/j.1365-2486.2003.00609.x

Papale, D., Reichstein, M., Aubinet, M., Canfora, E., Bernhofer, C.,
Kutsch, W., Longdoz, B., Rambal, S., Valentini, R., Vesala, T., and
Yakir, D.: Towards a standardized processing of Net Ecosystem Exchange
measured with eddy covariance technique: algorithms and uncertainty
estimation, Biogeosciences, 3, 571--583. doi:
https://doi.org/10.5194/bg-3-571-2006

Pastorello, G., Trotta, C., Canfora, E. *et al.* The FLUXNET2015 dataset
and the ONEFlux processing pipeline for eddy covariance data. *Sci
Data* **7**, 225 (2020). doi: https://doi.org/10.1038/s41597-020-0534-3

Penman, H. L. (1948), Natural evaporation from open water, bare soil and
grass, *Proceedings of the Royal Society of London Series A*, *193*,
120-146. doi: https://doi.org/10.1098/rspa.1948.0037

Potter, C. S., J. T. Randerson, C. B. Field, P. A. Matson, P. M.
Vitousek, H. A. Mooney, and S. A. Klooster (1993), Terrestrial ecosystem
production: a process based model based on global satellite and surface
data, *Global Biogeochemical Cycles*, *7*(4), 811-841. doi:
https://doi.org/10.1029/93gb02725

Prata, A. J. (1996), A new long-wave formula for estimating downward
clear-sky radiation at the surface, *Quarterly Journal of the Royal
Meteorological Society*, *122*(533), 1127-1151. doi:
https://doi.org/10.1002/qj.49712253306

Price, J. C. (1977), Thermal inertia mapping: a new view of the earth,
*Journal of Geophysical Research*, *82*(18), 2582-2590. doi:
https://doi.org/10.1029/JC082i018p02582

Priestley, C. H. B., and R. J. Taylor (1972), On the assessment of
surface heat flux and evaporation using large scale parameters, *Monthly
Weather Review*, *100*, 81-92. doi:
https://doi.org/10.1175/1520-0493(1972)100\<0081:OTAOSH\>2.3.CO;2

Roesch, A., C. Schaaf, and F. Gao (2004), Use of Moderate-Resolution
Imaging Spectroradiometer bidirectional reflectance distribution
function products to enhance simulated surface albedos, *Journal of
Geophysical Research*, *109*(D12), doi: 10.1029/2004JD004552.

Ryu, Y., D. D. Baldocchi, H. Kobayashi, C. van Ingen, J. Li, T. A.
Black, J. Beringer, E. van Gorsel, A. Knohl, B. E. Law, and O. Roupsard
(2011), Integration of MODIS land and atmosphere products with a
coupled-process model to estimate gross primary productivity and
evapotranspiration from 1 km to global scales, *Global Biogeochem.
Cycles*, *25*(4), GB4017. doi: https://doi.org/10.1029/2011GB004053

Ryu, Y., D. D. Baldocchi, T. A. Black, M. Detto, B. E. Law, R. Leuning,
A. Miyata, M. Reichstein, R. Vargas, C. Ammann, J. Beringer, L. B.
Flanagan, L. Gu, L. B. Hutley, J. Kim, H. McCaughey, E. J. Moors, S.
Rambal, and T. Vesala (2012), On the temporal upscaling of
evapotranspiration from instantaneous remote sensing measurements to
8-day mean daily-sums, *Agricultural and Forest Meteorology*, *152*(0),
212-222. doi: 10.1016/j.agrformet.2011.09.010

Santanello Jr, J. A., & Friedl, M. A. (2003). Diurnal covariation in
soil heat flux and net radiation. *Journal of Applied
Meteorology*, *42*(6), 851-862. doi:
https://doi.org/10.1175/1520-0450(2003)042\<0851:DCISHF\>2.0.CO;2

Shuttleworth, W. J., & Wallace, J. (1985). Evaporation from sparse
crops-an energy combination theory. *Quarterly Journal of the Royal
Meteorological Society*, **111**, 839--855. doi:
https://doi.org/10.1002/qj.49711146910

Stone, P. H., S. Chow, and W. J. Quirr (1977), July climate and a
comparison of January and July climates simulated by GISS general
circulation model, *Monthly Weather Review*, *105*(2), 170-194. doi:
https://doi.org/10.1175/1520-0493(1977)105\<0170:TJCAAC\>2.0.CO;2

Su, Z. (2002), The Surface Energy Balance System (SEBS) for estimation
of turbulent heat fluxes, *Hydrology and Earth System Sciences*, *6*,
85-99. doi: https://doi.org/10.5194/hess-6-85-2002

Vinukollu, R. K., E. F. Wood, C. R. Ferguson, and J. B. Fisher (2011),
Global estimates of evapotranspiration for climate studies using
multi-sensor remote sensing data: Evaluation of three process-based
approaches, *Remote Sensing of Environment*, *115*, 801-823. doi:
https://doi.org/10.1016/j.rse.2010.11.006

Wang, K., P. Wang, Z. Li, M. Cribb, and M. Sparrow (2007), A simple
method to estimate actual evapotranspiration from a combination of net
radiation, vegetation index, and temperature, *Journal of Geophysical
Research*, *112*(D15107), doi:10.1029/2006JD008351. doi: Wang, K., P.
Wang, Z. Li, M. Cribb, and M. Sparrow (2007), A simple method to
estimate actual evapotranspiration from a combination of net radiation,
vegetation index, and temperature, Journal of Geophysical Research,
112(D15107), doi:10.1029/2006JD008351.

Wind, G., S. Platnick, M. D. King, P. A. Hubanks, M. J. Pavolonis, A. K.
Heidinger, P. Yang, and B. A. Baum (2010), Multilayer cloud detection
with the MODIS near-infrared water vapor absorption band, *Journal of
Applied Meteorology and Climatology*, *49*, 2315-2333. doi:
https://doi.org/10.1175/2010JAMC2364.1

Yang, F., M. A. White, A. R. Michaelis, K. Ichii, H. Hashimoto, P.
Votava, A.-X. Zhu, and R. R. Nemani (2006), Prediction of
continental-scale evapotranspiration by combining MODIS and AmeriFlux
data through support vector machine, *Geoscience and Remote Sensing,
IEEE Transactions on*, *44*(11), 3452-3461. doi:
https://doi.org/10.1109/TGRS.2006.876297

Zhang, L., B. Wylie, T. Loveland, E. Fosnight, L. L. Tieszen, L. Ji, and
T. Gilmanov (2007), Evaluation and comparison of gross primary
production estimates for the Northern Great Plains grasslands, *Remote
Sensing of Environment*, *106*(2), 173-189. doi:
https://doi.org/10.1016/j.rse.2006.08.012

Zhang, Q., X. Xiao, B. H. Braswell, E. Linder, J. Aber, and B. Moore
(2005), Estimating seasonal dynamics of biophysical and biochemical
parameters in a deciduous forest using MODIS data and a radiative
transfer model, *Remote Sensing of Environment*, *99*, 357-371. doi:
https://doi.org/10.1016/j.rse.2005.09.009
