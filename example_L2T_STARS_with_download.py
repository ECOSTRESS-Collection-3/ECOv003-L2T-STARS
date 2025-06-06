# %% [markdown]
# Using `ECOv002-CMR` package to retrieve ECOSTRESS granules as inputs using the Common Metadata Repository (CMR) API. Using `ECOv002-L2T-STARS` package to run the product generating executable (PGE).

# %%
import numpy as np
from ECOv002_CMR import download_ECOSTRESS_granule
from ECOv003_L2T_STARS import generate_L2T_STARS_runconfig, L2T_STARS

# %% [markdown]
# Disable logger output in notebook

# %%
import logging

logging.getLogger().handlers = []

# %% [markdown]
# Set working directory

# %%
working_directory = "/Users/maggiej/data/ECOSTRESS_demo_C2"

# %% [markdown]
# Retrieve LST LSTE granule from CMR API for target date

# %%
# L2T_LSTE_granule = download_ECOSTRESS_granule(
#     product="L2T_LSTE", 
#     orbit=35800,
#     scene=3,
#     tile="11SPS", 
#     aquisition_date="2024-10-29",
#     parent_directory=working_directory
# )

L2T_LSTE_granule = download_ECOSTRESS_granule(
    product="L2T_LSTE", 
    orbit=35820,
    scene=12,
    tile="11SPS", 
    aquisition_date="2024-10-30",
    parent_directory=working_directory
)

# L2T_LSTE_granule = download_ECOSTRESS_granule(
#     product="L2T_LSTE", 
#     orbit=35861,
#     scene=6,
#     tile="11SPS", 
#     aquisition_date="2024-11-02",
#     parent_directory=working_directory
# )

L2T_LSTE_granule

# %% [markdown]
# Load and display preview of surface temperature

# %%
L2T_LSTE_granule.ST_C

# %% [markdown]
# Retrieve L2T STARS granule from CMR API as prior

# %%
# L2T_STARS_granule = download_ECOSTRESS_granule(
#     product="L2T_STARS", 
#     tile="11SPS", 
#     aquisition_date="2024-10-22",
#     parent_directory=working_directory
# )

L2T_STARS_granule = download_ECOSTRESS_granule(
    product="L2T_STARS", 
    tile="11SPS", 
    aquisition_date="2024-10-29",
    parent_directory=working_directory
)

# L2T_STARS_granule = download_ECOSTRESS_granule(
#     product="L2T_STARS", 
#     tile="11SPS", 
#     aquisition_date="2024-10-30",
#     parent_directory=working_directory
# )

L2T_STARS_granule

# %% [markdown]
# Load and display preview of vegetation index

# %%
L2T_STARS_granule.albedo

# %% [markdown]
# Generate XML run-config file for L2T STARS PGE run

# %%
runconfig_filename = generate_L2T_STARS_runconfig(
    L2T_LSTE_filename=L2T_LSTE_granule.product_filename,
    prior_L2T_STARS_filename=L2T_STARS_granule.product_filename,
    working_directory=working_directory
)

runconfig_filename

# %%
with open(runconfig_filename, "r") as f:
    print(f.read())

# %%
exit_code = L2T_STARS(runconfig_filename=runconfig_filename, use_VNP43NRT=True, threads=1, num_workers=8, remove_input_staging = False,remove_prior = False, remove_posterior = False)
exit_code

# %%



