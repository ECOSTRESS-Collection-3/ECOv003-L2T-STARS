from os.path import exists
import logging

import colored_logging as cl

from ECOv003_granules import L2TSTARS

from .prior import Prior
from .generate_filename import generate_filename
from .generate_model_state_tile_date_directory import generate_model_state_tile_date_directory

logger = logging.getLogger(__name__)

def load_prior(
        tile: str, 
        target_resolution: int, 
        model_directory: str, 
        L2T_STARS_prior_filename: str) -> Prior:
    """
    Loads a prior L2T_STARS product if available and extracts its components.

    This function attempts to load a previously generated L2T_STARS product
    to use its NDVI and albedo mean, uncertainty, and bias as prior information
    for the current data fusion run.

    Args:
        tile (str): The HLS tile ID.
        target_resolution (int): The target resolution of the L2T_STARS product.
        model_directory (str): The base directory for model state files.
        L2T_STARS_prior_filename (str): The filename of the prior L2T_STARS product (zip file).

    Returns:
        Prior: A Prior object containing paths to the prior data components
               and a flag indicating if a valid prior was loaded.
    """
    using_prior = False
    prior_date_UTC = None
    prior_NDVI_filename = None
    prior_NDVI_UQ_filename = None
    prior_NDVI_flag_filename = None
    prior_NDVI_bias_filename = None
    prior_NDVI_bias_UQ_filename = None
    prior_albedo_filename = None
    prior_albedo_UQ_filename = None
    prior_albedo_flag_filename = None
    prior_albedo_bias_filename = None
    prior_albedo_bias_UQ_filename = None

    if not L2T_STARS_prior_filename:
        logger.info("No prior L2T STARS product specified. Prior will not be used.")
        return Prior(using_prior=False)

    # Check if a prior L2T_STARS product exists
    if exists(L2T_STARS_prior_filename):
        logger.info(f"Loading prior L2T STARS product: {L2T_STARS_prior_filename}")
        try:
            # Initialize L2TSTARS object from the prior product
            L2T_STARS_prior_granule = L2TSTARS(L2T_STARS_prior_filename)
            prior_date_UTC = L2T_STARS_prior_granule.date_UTC
            logger.info(f"Prior date: {cl.time(prior_date_UTC)}")

            # Extract NDVI and albedo mean and uncertainty rasters
            NDVI_prior_mean = L2T_STARS_prior_granule.NDVI
            NDVI_prior_UQ = L2T_STARS_prior_granule.NDVI_UQ
            albedo_prior_mean = L2T_STARS_prior_granule.albedo
            albedo_prior_UQ = L2T_STARS_prior_granule.albedo_UQ

            # Define the directory for storing prior model state files
            prior_tile_date_directory = generate_model_state_tile_date_directory(
                model_directory=model_directory, tile=tile, date_UTC=prior_date_UTC
            )

            # Generate and save filenames for all prior components
            prior_NDVI_filename = generate_filename(
                directory=prior_tile_date_directory,
                variable="NDVI",
                date_UTC=prior_date_UTC,
                tile=tile,
                cell_size=target_resolution,
            )
            NDVI_prior_mean.to_geotiff(prior_NDVI_filename)

            prior_NDVI_UQ_filename = generate_filename(
                directory=prior_tile_date_directory,
                variable="NDVI.UQ",
                date_UTC=prior_date_UTC,
                tile=tile,
                cell_size=target_resolution,
            )
            NDVI_prior_UQ.to_geotiff(prior_NDVI_UQ_filename)

            # Note: Prior bias files might not always exist in older products.
            # Assuming they could be extracted from L2T_STARS_prior_granule if present.
            # For simplicity, these are placeholders and would need proper extraction logic
            # from the L2TSTARS granule if they are actual components.
            # For now, we set them based on `generate_filename` only if a bias layer is retrieved.
            # If the bias layers are not explicitly part of `L2TSTARS` object, these will be None
            # unless written explicitly during prior creation.
            prior_NDVI_bias_filename = generate_filename(
                directory=prior_tile_date_directory,
                variable="NDVI.bias",
                date_UTC=prior_date_UTC,
                tile=tile,
                cell_size=target_resolution,
            )
            # Assuming L2T_STARS_prior_granule has a .NDVI_bias attribute
            if L2T_STARS_prior_granule.NDVI_bias is not None:
                L2T_STARS_prior_granule.NDVI_bias.to_geotiff(prior_NDVI_bias_filename)
            else:
                prior_NDVI_bias_filename = None # Set to None if not available

            prior_NDVI_bias_UQ_filename = generate_filename(
                directory=prior_tile_date_directory,
                variable="NDVI.bias.UQ",
                date_UTC=prior_date_UTC,
                tile=tile,
                cell_size=target_resolution,
            )
            # Assuming L2T_STARS_prior_granule has a .NDVI_bias_UQ attribute
            if L2T_STARS_prior_granule.NDVI_bias_UQ is not None:
                L2T_STARS_prior_granule.NDVI_bias_UQ.to_geotiff(prior_NDVI_bias_UQ_filename)
            else:
                prior_NDVI_bias_UQ_filename = None # Set to None if not available


            prior_albedo_filename = generate_filename(
                directory=prior_tile_date_directory,
                variable="albedo",
                date_UTC=prior_date_UTC,
                tile=tile,
                cell_size=target_resolution,
            )
            albedo_prior_mean.to_geotiff(prior_albedo_filename)

            prior_albedo_UQ_filename = generate_filename(
                directory=prior_tile_date_directory,
                variable="albedo.UQ",
                date_UTC=prior_date_UTC,
                tile=tile,
                cell_size=target_resolution,
            )
            albedo_prior_UQ.to_geotiff(prior_albedo_UQ_filename)

            prior_albedo_bias_filename = generate_filename(
                directory=prior_tile_date_directory,
                variable="albedo.bias",
                date_UTC=prior_date_UTC,
                tile=tile,
                cell_size=target_resolution,
            )
            # Assuming L2T_STARS_prior_granule has a .albedo_bias attribute
            if L2T_STARS_prior_granule.albedo_bias is not None:
                L2T_STARS_prior_granule.albedo_bias.to_geotiff(prior_albedo_bias_filename)
            else:
                prior_albedo_bias_filename = None # Set to None if not available

            prior_albedo_bias_UQ_filename = generate_filename(
                directory=prior_tile_date_directory,
                variable="albedo.bias.UQ",
                date_UTC=prior_date_UTC,
                tile=tile,
                cell_size=target_resolution,
            )
            # Assuming L2T_STARS_prior_granule has a .albedo_bias_UQ attribute
            if L2T_STARS_prior_granule.albedo_bias_UQ is not None:
                L2T_STARS_prior_granule.albedo_bias_UQ.to_geotiff(prior_albedo_bias_UQ_filename)
            else:
                prior_albedo_bias_UQ_filename = None # Set to None if not available

            # HACK: Define prior_NDVI_flag_filename and prior_albedo_flag_filename using the Apache
            #  Zip VFS syntax, to allow for reading directly from the zip file in the rare case that
            #  it's necessary

            prior_NDVI_flag_filename = L2T_STARS_prior_granule.layer_URI("NDVI-flag")
            prior_albedo_flag_filename = L2T_STARS_prior_granule.layer_URI("albedo-flag")

            using_prior = True # Mark that a prior was successfully loaded
        except Exception as e:
            logger.warning(f"Could not load prior L2T STARS product: {L2T_STARS_prior_filename}. Reason: {e}")
            using_prior = False # Ensure using_prior is False if loading fails

    # Verify that all expected prior files exist, otherwise disable using_prior
    # This ensures a partial prior (e.g., only NDVI but not albedo) isn't used
    if prior_NDVI_filename is not None and exists(prior_NDVI_filename):
        logger.info(f"Prior NDVI ready: {prior_NDVI_filename}")
    else:
        logger.info(f"Prior NDVI not found: {prior_NDVI_filename}")
        using_prior = False

    if prior_NDVI_UQ_filename is not None and exists(prior_NDVI_UQ_filename):
        logger.info(f"Prior NDVI UQ ready: {prior_NDVI_UQ_filename}")
    else:
        logger.info(f"Prior NDVI UQ not found: {prior_NDVI_UQ_filename}")
        using_prior = False

    if prior_NDVI_bias_filename is not None and exists(prior_NDVI_bias_filename):
        logger.info(f"Prior NDVI bias ready: {prior_NDVI_bias_filename}")
    else:
        logger.info(f"Prior NDVI bias not found: {prior_NDVI_bias_filename}")
        using_prior = False

    if prior_NDVI_bias_UQ_filename is not None and exists(prior_NDVI_bias_UQ_filename):
        logger.info(f"Prior NDVI bias UQ ready: {prior_NDVI_bias_UQ_filename}")
    else:
        logger.info(f"Prior NDVI bias UQ not found: {prior_NDVI_bias_UQ_filename}")
        using_prior = False

    if prior_albedo_filename is not None and exists(prior_albedo_filename):
        logger.info(f"Prior albedo ready: {prior_albedo_filename}")
    else:
        logger.info(f"Prior albedo not found: {prior_albedo_filename}")
        using_prior = False

    if prior_albedo_UQ_filename is not None and exists(prior_albedo_UQ_filename):
        logger.info(f"Prior albedo UQ ready: {prior_albedo_UQ_filename}")
    else:
        logger.info(f"Prior albedo UQ not found: {prior_albedo_UQ_filename}")
        using_prior = False

    if prior_albedo_bias_filename is not None and exists(prior_albedo_bias_filename):
        logger.info(f"Prior albedo bias ready: {prior_albedo_bias_filename}")
    else:
        logger.info(f"Prior albedo bias not found: {prior_albedo_bias_filename}")
        using_prior = False

    if prior_albedo_bias_UQ_filename is not None and exists(
        prior_albedo_bias_UQ_filename
    ):
        logger.info(f"Prior albedo bias UQ ready: {prior_albedo_bias_UQ_filename}")
    else:
        logger.info(f"Prior albedo bias UQ not found: {prior_albedo_bias_UQ_filename}")
        using_prior = False
    
    # Final check: if any of the critical prior files are missing, do not use prior
    if not all([prior_NDVI_filename, prior_NDVI_UQ_filename, prior_albedo_filename, prior_albedo_UQ_filename]):
        logger.warning("One or more required prior (mean/UQ) files are missing. Prior will not be used.")
        using_prior = False
        prior_NDVI_filename = None
        prior_NDVI_UQ_filename = None
        prior_albedo_filename = None
        prior_albedo_UQ_filename = None

    # Create and return the Prior object
    prior = Prior(
        using_prior=using_prior,
        prior_date_UTC=prior_date_UTC,
        L2T_STARS_prior_filename=L2T_STARS_prior_filename,
        prior_NDVI_filename=prior_NDVI_filename,
        prior_NDVI_UQ_filename=prior_NDVI_UQ_filename,
        prior_NDVI_flag_filename=prior_NDVI_flag_filename,
        prior_NDVI_bias_filename=prior_NDVI_bias_filename,
        prior_NDVI_bias_UQ_filename=prior_NDVI_bias_UQ_filename,
        prior_albedo_filename=prior_albedo_filename,
        prior_albedo_UQ_filename=prior_albedo_UQ_filename,
        prior_albedo_flag_filename=prior_albedo_flag_filename,
        prior_albedo_bias_filename=prior_albedo_bias_filename,
        prior_albedo_bias_UQ_filename=prior_albedo_bias_UQ_filename,
    )

    return prior
