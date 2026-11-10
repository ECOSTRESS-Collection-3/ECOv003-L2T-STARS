import numpy as np
import logging
from os.path import join
from ECOv003_CMR import download_ECOSTRESS_granule
from ECOv003_L2T_STARS import generate_L2T_STARS_runconfig, L2T_STARS

# Disable logger output
logging.getLogger().handlers = []

# Set working directory
working_directory = join("~", "data", "ECOv003_testing")

# Retrieve LST LSTE granule from CMR API for target date
L2T_LSTE_granule = download_ECOSTRESS_granule(
    product="L2T_LSTE", 
    tile="11SPS", 
    aquisition_date="2024-10-10",
    parent_directory=working_directory
)

# Retrieve L2T STARS granule from CMR API as prior
L2T_STARS_granule = download_ECOSTRESS_granule(
    product="L2T_STARS", 
    tile="11SPS", 
    aquisition_date="2024-10-06",
    parent_directory=working_directory
)

# Generate XML run-config file for L2T STARS PGE run
runconfig_filename = generate_L2T_STARS_runconfig(
    L2T_LSTE_filename=L2T_LSTE_granule.product_filename,
    prior_L2T_STARS_filename=L2T_STARS_granule.product_filename,
    working_directory=working_directory
)

print("Runconfig generated:", runconfig_filename)

# Run L2T STARS PGE
exit_code = L2T_STARS(
    runconfig_filename=runconfig_filename,
    threads=1,
    num_workers=8,
    remove_input_staging=False,
    remove_prior=False,
    remove_posterior=False,
    overwrite=True
)

print("L2T STARS PGE exit code:", exit_code)