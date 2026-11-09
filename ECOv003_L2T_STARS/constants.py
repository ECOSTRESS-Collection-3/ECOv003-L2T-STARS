from os.path import join, abspath, dirname

# Template file for generating the L2T_STARS run configuration XML.
L2T_STARS_TEMPLATE = join(abspath(dirname(__file__)), "ECOv003_L2T_STARS.xml")

# Default directories and parameters for the L2T_STARS processing.
WORKING_DIRECTORY = "."  # Current directory
BUILD = "0700"  # Default build ID
PRIMARY_VARIABLE = "NDVI"  # Primary variable of interest
OUTPUT_DIRECTORY = "L2T_STARS_output"
STARS_SOURCES_DIRECTORY = "L2T_STARS_SOURCES"
STARS_INDICES_DIRECTORY = "L2T_STARS_INDICES"
STARS_MODEL_DIRECTORY = "L2T_STARS_MODEL"
STARS_PRODUCTS_DIRECTORY = "STARS_products"
HLS_DOWNLOAD_DIRECTORY = "HLS2_download"
LANDSAT_DOWNLOAD_DIRECTORY = "HLS2_download"  # Redundant but kept for clarity
HLS_PRODUCTS_DIRECTORY = "HLS2_products"
VCD43NRT_DOWNLOAD_DIRECTORY = "VCD43NRT_download"
VCD43NRT_INPUT_PRODUCTS_DIRECTORY = "VCD43NRT_inputs"
VCD43NRT_MOSAIC_DIRECTORY = "VCD43NRT_mosaics"
VCD43NRT_PRODUCTS_DIRECTORY = "VCD43NRT_products"
VCD43NRT_STAGING_DIRECTORY = "VCD43NRT_staging"
GEOS5FP_DOWNLOAD_DIRECTORY = "GEOS5FP_download"
GEOS5FP_PRODUCTS_DIRECTORY = "GEOS5FP_products"
STARS_DOWNSAMPLED_DIRECTORY = "VCD43NRT_DOWNSAMPLED_products"

# Processing parameters
VIIRS_GIVEUP_DAYS = 4  # Number of days to give up waiting for VIIRS data
SPINUP_DAYS = 7  # Spin-up period for time-series analysis
TARGET_RESOLUTION = 70  # Target output resolution in meters
NDVI_RESOLUTION = 490  # NDVI coarse resolution in meters
ALBEDO_RESOLUTION = 980  # Albedo coarse resolution in meters
USE_SPATIAL = False  # Flag for using spatial interpolation (currently unused)
VCD43NRT_MISSION_PRIORITY = ("SNPP", "JPSS1", "JPSS2")
CALIBRATE_FINE = False  # Flag for calibrating fine resolution data to coarse
THREADS = "auto"  # Number of threads to use, 'auto' for automatic detection
WORKERS = 4  # Number of worker processes for parallel processing
OVERWRITE = False  # Flag to overwrite existing files
SOURCES_ONLY = False  # Flag to only process sources without further analysis
REMOVE_INPUT_STAGING = True  # Flag to remove input staging files after processing

# Product short and long names
L2T_STARS_SHORT_NAME = "ECO_L2T_STARS"
L2T_STARS_LONG_NAME = "ECOSTRESS Tiled Auxiliary NDVI and Albedo L2 Global 70 m"

# prior and posterior model state behavior
REMOVE_PRIOR = True
REMOVE_POSTERIOR = True
