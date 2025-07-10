from os.path import join, abspath, dirname

# Template file for generating the L2T_STARS run configuration XML.
L2T_STARS_TEMPLATE = join(abspath(dirname(__file__)), "ECOv003_L2T_STARS.xml")

# Default directories and parameters for the L2T_STARS processing.
DEFAULT_WORKING_DIRECTORY = "."  # Current directory
DEFAULT_BUILD = "0700"  # Default build ID
PRIMARY_VARIABLE = "NDVI"  # Primary variable of interest
DEFAULT_OUTPUT_DIRECTORY = "L2T_STARS_output"
DEFAULT_STARS_SOURCES_DIRECTORY = "L2T_STARS_SOURCES"
DEFAULT_STARS_INDICES_DIRECTORY = "L2T_STARS_INDICES"
DEFAULT_STARS_MODEL_DIRECTORY = "L2T_STARS_MODEL"
DEFAULT_STARS_PRODUCTS_DIRECTORY = "STARS_products"
DEFAULT_HLS_DOWNLOAD_DIRECTORY = "HLS2_download"
DEFAULT_LANDSAT_DOWNLOAD_DIRECTORY = "HLS2_download"  # Redundant but kept for clarity
DEFAULT_HLS_PRODUCTS_DIRECTORY = "HLS2_products"
DEFAULT_VIIRS_DOWNLOAD_DIRECTORY = "VIIRS_download"
DEFAULT_VIIRS_PRODUCTS_DIRECTORY = "VIIRS_products"
DEFAUL_VIIRS_MOSAIC_DIRECTORY = "VIIRS_mosaic"
DEFAULT_GEOS5FP_DOWNLOAD_DIRECTORY = "GEOS5FP_download"
DEFAULT_GEOS5FP_PRODUCTS_DIRECTORY = "GEOS5FP_products"
DEFAULT_VNP09GA_PRODUCTS_DIRECTORY = "VNP09GA_products"
DEFAULT_VNP43NRT_PRODUCTS_DIRECTORY = "VNP43NRT_products"

# Processing parameters
VIIRS_GIVEUP_DAYS = 4  # Number of days to give up waiting for VIIRS data
DEFAULT_SPINUP_DAYS = 7  # Spin-up period for time-series analysis
DEFAULT_TARGET_RESOLUTION = 70  # Target output resolution in meters
DEFAULT_NDVI_RESOLUTION = 490  # NDVI coarse resolution in meters
DEFAULT_ALBEDO_RESOLUTION = 980  # Albedo coarse resolution in meters
DEFAULT_USE_SPATIAL = False  # Flag for using spatial interpolation (currently unused)
DEFAULT_USE_VNP43NRT = True  # Flag for using VNP43NRT VIIRS product
DEFAULT_CALIBRATE_FINE = False  # Flag for calibrating fine resolution data to coarse

# Product short and long names
L2T_STARS_SHORT_NAME = "ECO_L2T_STARS"
L2T_STARS_LONG_NAME = "ECOSTRESS Tiled Auxiliary NDVI and Albedo L2 Global 70 m"

REMOVE_PRIOR = False
REMOVE_POSTERIOR = False
