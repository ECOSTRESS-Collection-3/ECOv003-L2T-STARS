"""
Using `ECOv002-CMR` package to retrieve ECOSTRESS granules as inputs using the 
Common Metadata Repository (CMR) API. Using `ECOv002-L2T-STARS` package to run 
the product generating executable (PGE).
"""

import numpy as np
from ECOv002_CMR import download_ECOSTRESS_granule
from ECOv002_L2T_STARS import generate_L2T_STARS_runconfig, L2T_STARS
import logging

# Disable logger output
logging.getLogger().handlers = []

# Set working directory
working_directory = "data"

# Retrieve LST LSTE granule from CMR API for target date
L2T_LSTE_granule = download_ECOSTRESS_granule(
    product="L2T_LSTE", 
    orbit=35800,
    scene=3,
    tile="11SPS", 
    aquisition_date="2024-10-29",
    parent_directory=working_directory
)

print(L2T_LSTE_granule)

# Load and display preview of surface temperature
print(L2T_LSTE_granule.ST_C)

# Retrieve L2T STARS granule from CMR API as prior
L2T_STARS_granule = download_ECOSTRESS_granule(
    product="L2T_STARS", 
    tile="11SPS", 
    aquisition_date="2024-10-22",
    parent_directory=working_directory
)

print(L2T_STARS_granule)

# Load and display preview of vegetation index
print(L2T_STARS_granule.NDVI)

# Generate XML run-config file for L2T STARS PGE run
runconfig_filename = generate_L2T_STARS_runconfig(
    L2T_LSTE_filename=L2T_LSTE_granule.product_filename,
    prior_L2T_STARS_filename=L2T_STARS_granule.product_filename,
    working_directory=working_directory
)

print(runconfig_filename)

# Display the contents of the run-config file
with open(runconfig_filename, "r") as f:
    print(f.read())

# Run the L2T STARS PGE
exit_code = L2T_STARS(runconfig_filename=runconfig_filename)
print(exit_code)