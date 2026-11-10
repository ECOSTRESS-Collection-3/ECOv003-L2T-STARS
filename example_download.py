import numpy as np
import logging
from os.path import join
from ECOv003_CMR import download_ECOSTRESS_granule

# Disable logger output
logging.getLogger().handlers = []

# Set working directory
working_directory = join("~", "data", "ECOv003_testing")

# Retrieve LST LSTE granule from CMR API for target date
L2T_LSTE_granule = download_ECOSTRESS_granule(
    product="L2T_LSTE", 
    orbit=47080,
    scene=14,
    tile="11SPS", 
    aquisition_date="2026-10-24",
    parent_directory=working_directory
)

# Retrieve L2T STARS granule from CMR API as prior
L2T_STARS_granule = download_ECOSTRESS_granule(
    product="L2T_STARS", 
    tile="11SPS", 
    aquisition_date="2026-10-20",
    parent_directory=working_directory
)
