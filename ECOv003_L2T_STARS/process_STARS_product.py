import logging
import shutil
from datetime import datetime, date
from os import remove
from os.path import basename, exists
from typing import Union
import logging

import numpy as np

import colored_logging as cl
from rasters import Raster

from harmonized_landsat_sentinel import HLS2CMR

from ECOv003_granules import L2TSTARS, NDVI_COLORMAP, ALBEDO_COLORMAP
from ECOv003_exit_codes import BlankOutput

from .constants import *
from .VIIRS import VIIRSDownloaderNDVI, VIIRSDownloaderAlbedo
from .generate_NDVI_coarse_directory import generate_NDVI_coarse_directory
from .generate_NDVI_fine_directory import generate_NDVI_fine_directory
from .generate_albedo_coarse_directory import generate_albedo_coarse_directory
from .generate_albedo_fine_directory import generate_albedo_fine_directory
from .generate_model_state_tile_date_directory import generate_model_state_tile_date_directory
from .generate_STARS_inputs import generate_STARS_inputs
from .generate_filename import generate_filename
from .process_julia_data_fusion import process_julia_data_fusion

from .prior import Prior

logger = logging.getLogger(__name__)

def process_STARS_product(
    tile: str,
    date_UTC: date,
    time_UTC: datetime,
    build: str,
    product_counter: int,
    HLS_start_date: date,
    HLS_end_date: date,
    VIIRS_start_date: date,
    VIIRS_end_date: date,
    NDVI_resolution: int,
    albedo_resolution: int,
    target_resolution: int,
    working_directory: str,
    model_directory: str,
    input_staging_directory: str,
    L2T_STARS_granule_directory: str,
    L2T_STARS_zip_filename: str,
    L2T_STARS_browse_filename: str,
    metadata: dict,
    prior: Prior,
    HLS_connection: HLS2CMR,
    NDVI_VIIRS_connection: VIIRSDownloaderNDVI,
    albedo_VIIRS_connection: VIIRSDownloaderAlbedo,
    using_prior: bool = False,
    calibrate_fine: bool = False,
    remove_input_staging: bool = True,
    remove_prior: bool = REMOVE_PRIOR,
    remove_posterior: bool = REMOVE_POSTERIOR,
    threads: Union[int, str] = "auto",
    num_workers: int = 4,
):
    """
    Orchestrates the generation of the L2T_STARS product for a given tile and date.

    This function handles the staging of input data, execution of the Julia data
    fusion model for both NDVI and albedo, and the final assembly, metadata
    writing, and archiving of the L2T_STARS product. It also manages cleanup
    of intermediate and prior files.

    Args:
        tile (str): The HLS tile ID.
        date_UTC (date): The UTC date for the current L2T_STARS product.
        time_UTC (datetime): The UTC time for the current L2T_STARS product.
        build (str): The build ID of the PGE.
        product_counter (int): The product counter for the current run.
        HLS_start_date (date): The start date for HLS data used in fusion.
        HLS_end_date (date): The end date for HLS data used in fusion.
        VIIRS_start_date (date): The start date for VIIRS data used in fusion.
        VIIRS_end_date (date): The end date for VIIRS data used in fusion.
        NDVI_resolution (int): The resolution of the coarse NDVI data.
        albedo_resolution (int): The resolution of the coarse albedo data.
        target_resolution (int): The desired output resolution of the fused product.
        working_directory (str): The main working directory.
        model_directory (str): Directory for model state files (priors, posteriors).
        input_staging_directory (str): Directory for temporary input images for Julia.
        L2T_STARS_granule_directory (str): Temporary directory for the unzipped product.
        L2T_STARS_zip_filename (str): Final path for the zipped L2T_STARS product.
        L2T_STARS_browse_filename (str): Final path for the browse image.
        metadata (dict): Dictionary containing product metadata.
        prior (Prior): An object containing information about the prior product.
        HLS_connection (HLS2CMR): An initialized HLS data connection object.
        NDVI_VIIRS_connection (VIIRSDownloaderNDVI): An initialized VIIRS NDVI downloader.
        albedo_VIIRS_connection (VIIRSDownloaderAlbedo): An initialized VIIRS albedo downloader.
        using_prior (bool, optional): If True, use the prior product in fusion. Defaults to False.
        calibrate_fine (bool, optional): If True, calibrate fine images to coarse images.
                                         Defaults to False.
        remove_input_staging (bool, optional): If True, remove the input staging directory
                                                after processing. Defaults to True.
        remove_prior (bool, optional): If True, remove prior intermediate files after use.
                                       Defaults to True.
        remove_posterior (bool, optional): If True, remove posterior intermediate files after
                                           product generation. Defaults to True.
        threads (Union[int, str], optional): Number of Julia threads to use, or "auto".
                                            Defaults to "auto".
        num_workers (int, str): Number of Julia workers for distributed processing.
                                     Defaults to 4.

    Raises:
        BlankOutput: If any of the final fused output rasters (NDVI, albedo, UQ, flag) are empty.
    """
    # Get the target geometries for coarse NDVI and albedo based on the HLS grid
    NDVI_coarse_geometry = HLS_connection.grid(tile=tile, cell_size=NDVI_resolution)
    albedo_coarse_geometry = HLS_connection.grid(tile=tile, cell_size=albedo_resolution)

    logger.info(f"Processing the L2T_STARS product at tile {cl.place(tile)} for date {cl.time(date_UTC)}")

    # Define and create input staging directories for coarse and fine NDVI/albedo
    NDVI_coarse_directory = generate_NDVI_coarse_directory(
        input_staging_directory=input_staging_directory, tile=tile
    )
    logger.info(f"Staging coarse NDVI images: {cl.dir(NDVI_coarse_directory)}")

    NDVI_fine_directory = generate_NDVI_fine_directory(
        input_staging_directory=input_staging_directory, tile=tile
    )
    logger.info(f"Staging fine NDVI images: {cl.dir(NDVI_fine_directory)}")

    albedo_coarse_directory = generate_albedo_coarse_directory(
        input_staging_directory=input_staging_directory, tile=tile
    )
    logger.info(f"Staging coarse albedo images: {cl.dir(albedo_coarse_directory)}")

    albedo_fine_directory = generate_albedo_fine_directory(
        input_staging_directory=input_staging_directory, tile=tile
    )
    logger.info(f"Staging fine albedo images: {cl.dir(albedo_fine_directory)}")

    # Define and create the directory for storing posterior model state files
    posterior_tile_date_directory = generate_model_state_tile_date_directory(
        model_directory=model_directory, tile=tile, date_UTC=date_UTC
    )
    logger.info(f"Posterior directory: {cl.dir(posterior_tile_date_directory)}")

    # Generate the actual input raster files (coarse and fine images)
    generate_STARS_inputs(
        tile=tile,
        date_UTC=date_UTC,
        HLS_start_date=HLS_start_date,
        HLS_end_date=HLS_end_date,
        VIIRS_start_date=VIIRS_start_date,
        VIIRS_end_date=VIIRS_end_date,
        NDVI_resolution=NDVI_resolution,
        albedo_resolution=albedo_resolution,
        target_resolution=target_resolution,
        NDVI_coarse_geometry=NDVI_coarse_geometry,
        albedo_coarse_geometry=albedo_coarse_geometry,
        working_directory=working_directory,
        NDVI_coarse_directory=NDVI_coarse_directory,
        NDVI_fine_directory=NDVI_fine_directory,
        albedo_coarse_directory=albedo_coarse_directory,
        albedo_fine_directory=albedo_fine_directory,
        HLS_connection=HLS_connection,
        NDVI_VIIRS_connection=NDVI_VIIRS_connection,
        albedo_VIIRS_connection=albedo_VIIRS_connection,
        calibrate_fine=calibrate_fine,
    )

    # --- Process NDVI Data Fusion ---
    # Define output filenames for NDVI posterior products
    posterior_NDVI_filename = generate_filename(
        directory=posterior_tile_date_directory,
        variable="NDVI",
        date_UTC=date_UTC,
        tile=tile,
        cell_size=target_resolution,
    )
    logger.info(f"Posterior NDVI file: {cl.file(posterior_NDVI_filename)}")

    posterior_NDVI_UQ_filename = generate_filename(
        directory=posterior_tile_date_directory,
        variable="NDVI.UQ",
        date_UTC=date_UTC,
        tile=tile,
        cell_size=target_resolution,
    )
    logger.info(f"Posterior NDVI UQ file: {cl.file(posterior_NDVI_UQ_filename)}")

    posterior_NDVI_flag_filename = generate_filename(
        directory=posterior_tile_date_directory,
        variable="NDVI.flag",
        date_UTC=date_UTC,
        tile=tile,
        cell_size=target_resolution,
    )
    logger.info(f"Posterior NDVI flag file: {cl.file(posterior_NDVI_flag_filename)}")

    posterior_NDVI_bias_filename = generate_filename(
        directory=posterior_tile_date_directory,
        variable="NDVI.bias",
        date_UTC=date_UTC,
        tile=tile,
        cell_size=target_resolution,
    )
    logger.info(f"Posterior NDVI bias file: {cl.file(posterior_NDVI_bias_filename)}")

    posterior_NDVI_bias_UQ_filename = generate_filename(
        directory=posterior_tile_date_directory,
        variable="NDVI.bias.UQ",
        date_UTC=date_UTC,
        tile=tile,
        cell_size=target_resolution,
    )
    logger.info(f"Posterior NDVI bias UQ file: {cl.file(posterior_NDVI_bias_UQ_filename)}")

    # Run Julia data fusion for NDVI, conditionally including prior data
    if using_prior:
        logger.info("Running Julia data fusion for NDVI with prior data.")
        process_julia_data_fusion(
            tile=tile,
            coarse_cell_size=NDVI_resolution,
            fine_cell_size=target_resolution,
            VIIRS_start_date=VIIRS_start_date,
            VIIRS_end_date=VIIRS_end_date,
            HLS_start_date=HLS_start_date,
            HLS_end_date=HLS_end_date,
            coarse_directory=NDVI_coarse_directory,
            fine_directory=NDVI_fine_directory,
            posterior_filename=posterior_NDVI_filename,
            posterior_UQ_filename=posterior_NDVI_UQ_filename,
            posterior_flag_filename=posterior_NDVI_flag_filename,
            posterior_bias_filename=posterior_NDVI_bias_filename,
            posterior_bias_UQ_filename=posterior_NDVI_bias_UQ_filename,
            prior_filename=prior.prior_NDVI_filename,
            prior_UQ_filename=prior.prior_NDVI_UQ_filename,
            prior_bias_filename=prior.prior_NDVI_bias_filename,
            prior_bias_UQ_filename=prior.prior_NDVI_bias_UQ_filename,
            threads=threads,
            num_workers=num_workers,
        )
    else:
        logger.info("Running Julia data fusion for NDVI without prior data.")
        process_julia_data_fusion(
            tile=tile,
            coarse_cell_size=NDVI_resolution,
            fine_cell_size=target_resolution,
            VIIRS_start_date=VIIRS_start_date,
            VIIRS_end_date=VIIRS_end_date,
            HLS_start_date=HLS_start_date,
            HLS_end_date=HLS_end_date,
            coarse_directory=NDVI_coarse_directory,
            fine_directory=NDVI_fine_directory,
            posterior_filename=posterior_NDVI_filename,
            posterior_UQ_filename=posterior_NDVI_UQ_filename,
            posterior_flag_filename=posterior_NDVI_flag_filename,
            posterior_bias_filename=posterior_NDVI_bias_filename,
            posterior_bias_UQ_filename=posterior_NDVI_bias_UQ_filename,
            threads=threads,
            num_workers=num_workers,
        )

    # Open the resulting NDVI rasters
    NDVI = Raster.open(posterior_NDVI_filename)
    NDVI_UQ = Raster.open(posterior_NDVI_UQ_filename)
    NDVI_flag = Raster.open(posterior_NDVI_flag_filename)

    # --- Process Albedo Data Fusion ---
    # Define output filenames for albedo posterior products
    posterior_albedo_filename = generate_filename(
        directory=posterior_tile_date_directory,
        variable="albedo",
        date_UTC=date_UTC,
        tile=tile,
        cell_size=target_resolution,
    )
    logger.info(f"Posterior albedo file: {cl.file(posterior_albedo_filename)}")

    posterior_albedo_UQ_filename = generate_filename(
        directory=posterior_tile_date_directory,
        variable="albedo.UQ",
        date_UTC=date_UTC,
        tile=tile,
        cell_size=target_resolution,
    )
    logger.info(f"Posterior albedo UQ file: {cl.file(posterior_albedo_UQ_filename)}")

    posterior_albedo_flag_filename = generate_filename(
        directory=posterior_tile_date_directory,
        variable="albedo.flag",
        date_UTC=date_UTC,
        tile=tile,
        cell_size=target_resolution,
    )
    logger.info(f"Posterior albedo flag file: {cl.file(posterior_albedo_flag_filename)}")

    posterior_albedo_bias_filename = generate_filename(
        directory=posterior_tile_date_directory,
        variable="albedo.bias",
        date_UTC=date_UTC,
        tile=tile,
        cell_size=target_resolution,
    )
    logger.info(f"Posterior albedo bias file: {cl.file(posterior_albedo_bias_filename)}")

    posterior_albedo_bias_UQ_filename = generate_filename(
        directory=posterior_tile_date_directory,
        variable="albedo.bias.UQ",
        date_UTC=date_UTC,
        tile=tile,
        cell_size=target_resolution,
    )
    logger.info(f"Posterior albedo bias UQ file: {cl.file(posterior_albedo_bias_UQ_filename)}")

    # Run Julia data fusion for albedo, conditionally including prior data
    if using_prior:
        logger.info("Running Julia data fusion for albedo with prior data.")
        process_julia_data_fusion(
            tile=tile,
            coarse_cell_size=albedo_resolution,
            fine_cell_size=target_resolution,
            VIIRS_start_date=VIIRS_start_date,
            VIIRS_end_date=VIIRS_end_date,
            HLS_start_date=HLS_start_date,
            HLS_end_date=HLS_end_date,
            coarse_directory=albedo_coarse_directory,
            fine_directory=albedo_fine_directory,
            posterior_filename=posterior_albedo_filename,
            posterior_UQ_filename=posterior_albedo_UQ_filename,
            posterior_flag_filename=posterior_albedo_flag_filename,
            posterior_bias_filename=posterior_albedo_bias_filename,
            posterior_bias_UQ_filename=posterior_albedo_bias_UQ_filename,
            prior_filename=prior.prior_albedo_filename,
            prior_UQ_filename=prior.prior_albedo_UQ_filename,
            prior_bias_filename=prior.prior_albedo_bias_filename,
            prior_bias_UQ_filename=prior.prior_albedo_bias_UQ_filename,
            threads=threads,
            num_workers=num_workers,
        )
    else:
        logger.info("Running Julia data fusion for albedo without prior data.")
        process_julia_data_fusion(
            tile=tile,
            coarse_cell_size=albedo_resolution,
            fine_cell_size=target_resolution,
            VIIRS_start_date=VIIRS_start_date,
            VIIRS_end_date=VIIRS_end_date,
            HLS_start_date=HLS_start_date,
            HLS_end_date=HLS_end_date,
            coarse_directory=albedo_coarse_directory,
            fine_directory=albedo_fine_directory,
            posterior_filename=posterior_albedo_filename,
            posterior_UQ_filename=posterior_albedo_UQ_filename,
            posterior_flag_filename=posterior_albedo_flag_filename,
            posterior_bias_filename=posterior_albedo_bias_filename,
            posterior_bias_UQ_filename=posterior_albedo_bias_UQ_filename,
            threads=threads,
            num_workers=num_workers,
        )

    # Open the resulting albedo rasters
    albedo = Raster.open(posterior_albedo_filename)
    albedo_UQ = Raster.open(posterior_albedo_UQ_filename)
    albedo_flag = Raster.open(posterior_albedo_flag_filename)

    # --- Validate Output and Create Final Product ---
    # Check if the output rasters are valid (not None, indicating a problem during Julia processing)
    if NDVI is None:
        raise BlankOutput("Unable to generate STARS NDVI")
    if NDVI_UQ is None:
        raise BlankOutput("Unable to generate STARS NDVI UQ")
    if NDVI_flag is None:
        raise BlankOutput("Unable to generate STARS NDVI flag")
    if albedo is None:
        raise BlankOutput("Unable to generate STARS albedo")
    if albedo_UQ is None:
        raise BlankOutput("Unable to generate STARS albedo UQ")
    if albedo_flag is None:
        raise BlankOutput("Unable to generate STARS albedo flag")

    # Initialize the L2TSTARS granule object for the current product
    granule = L2TSTARS(
        product_location=L2T_STARS_granule_directory,
        tile=tile,
        time_UTC=time_UTC,
        build=build,
        process_count=product_counter,
    )

    # Add the generated layers to the granule object
    granule.add_layer("NDVI", NDVI, cmap=NDVI_COLORMAP)
    granule.add_layer("NDVI-UQ", NDVI_UQ, cmap="jet")
    granule.add_layer("NDVI-flag", NDVI_flag, cmap="jet")
    granule.add_layer("albedo", albedo, cmap=ALBEDO_COLORMAP)
    granule.add_layer("albedo-UQ", albedo_UQ, cmap="jet")
    granule.add_layer("albedo-flag", albedo_flag, cmap="jet")

    # Update metadata and write to the granule
    metadata["StandardMetadata"]["LocalGranuleID"] = basename(L2T_STARS_zip_filename)
    metadata["StandardMetadata"]["SISName"] = "Level 2 STARS Product Specification Document"
    granule.write_metadata(metadata)

    # Write the zipped product and browse image
    logger.info(f"Writing L2T STARS product zip: {cl.file(L2T_STARS_zip_filename)}")
    granule.write_zip(L2T_STARS_zip_filename)
    logger.info(f"Writing L2T STARS browse image: {cl.file(L2T_STARS_browse_filename)}")
    granule.write_browse_image(PNG_filename=L2T_STARS_browse_filename)
    logger.info(
        f"Removing L2T STARS tile granule directory: {cl.dir(L2T_STARS_granule_directory)}"
    )
    shutil.rmtree(L2T_STARS_granule_directory)

    # Re-check and regenerate browse image if it somehow didn't generate (e.g. if the granule dir was already deleted)
    if not exists(L2T_STARS_browse_filename):
        logger.info(
            f"Browse image not found after initial creation attempt. Regenerating: {cl.file(L2T_STARS_browse_filename)}"
        )
        # Re-load granule from zip to create browse image if necessary
        granule_for_browse = L2TSTARS(L2T_STARS_zip_filename)
        granule_for_browse.write_browse_image(PNG_filename=L2T_STARS_browse_filename)

    # Re-write posterior files (often done to ensure proper compression/color maps after processing)
    # This step might be redundant if Julia already writes them correctly, but ensures consistency.
    logger.info(f"Re-writing posterior NDVI: {posterior_NDVI_filename}")
    Raster.open(posterior_NDVI_filename, cmap=NDVI_COLORMAP).to_geotiff(
        posterior_NDVI_filename
    )
    logger.info(f"Re-writing posterior NDVI UQ: {posterior_NDVI_UQ_filename}")
    Raster.open(posterior_NDVI_UQ_filename, cmap="jet").to_geotiff(
        posterior_NDVI_UQ_filename
    )
    logger.info(f"Re-writing posterior NDVI flag: {posterior_NDVI_flag_filename}")
    Raster.open(posterior_NDVI_flag_filename, cmap="jet").to_geotiff(
        posterior_NDVI_flag_filename
    )
    logger.info(f"Re-writing posterior NDVI bias: {posterior_NDVI_bias_filename}")
    Raster.open(posterior_NDVI_bias_filename, cmap=NDVI_COLORMAP).to_geotiff(
        posterior_NDVI_bias_filename
    )
    logger.info(f"Re-writing posterior NDVI bias UQ: {posterior_NDVI_bias_UQ_filename}")
    Raster.open(posterior_NDVI_bias_UQ_filename, cmap=NDVI_COLORMAP).to_geotiff(
        posterior_NDVI_bias_UQ_filename
    )

    logger.info(f"Re-writing posterior albedo: {posterior_albedo_filename}")
    Raster.open(posterior_albedo_filename, cmap=ALBEDO_COLORMAP).to_geotiff(
        posterior_albedo_filename
    )
    logger.info(f"Re-writing posterior albedo UQ: {posterior_albedo_UQ_filename}")
    Raster.open(posterior_albedo_UQ_filename, cmap="jet").to_geotiff(
        posterior_albedo_UQ_filename
    )
    logger.info(f"Re-writing posterior albedo flag: {posterior_albedo_flag_filename}")
    Raster.open(posterior_albedo_flag_filename, cmap="jet").to_geotiff(
        posterior_albedo_flag_filename
    )
    logger.info(f"Re-writing posterior albedo bias: {posterior_albedo_bias_filename}")
    Raster.open(posterior_albedo_bias_filename, cmap=ALBEDO_COLORMAP).to_geotiff(
        posterior_albedo_bias_filename
    )
    logger.info(f"Re-writing posterior albedo bias UQ: {posterior_albedo_bias_UQ_filename}")
    Raster.open(posterior_albedo_bias_UQ_filename, cmap=ALBEDO_COLORMAP).to_geotiff(
        posterior_albedo_bias_UQ_filename
    )

    # --- Cleanup ---
    if remove_input_staging:
        if exists(input_staging_directory):
            logger.info(f"Removing input staging directory: {cl.dir(input_staging_directory)}")
            shutil.rmtree(input_staging_directory)

    if using_prior and remove_prior:
        # Remove prior intermediate files only if they exist
        prior_files = [
            prior.prior_NDVI_filename,
            prior.prior_NDVI_UQ_filename,
            prior.prior_NDVI_bias_filename,
            prior.prior_NDVI_bias_UQ_filename,
            prior.prior_albedo_filename,
            prior.prior_albedo_UQ_filename,
            prior.prior_albedo_bias_filename,
            prior.prior_albedo_bias_UQ_filename,
        ]
        for f in prior_files:
            if f is not None and exists(f):
                logger.info(f"Removing prior file: {cl.file(f)}")
                remove(f)

    if remove_posterior:
        # Remove posterior intermediate files only if they exist
        posterior_files = [
            posterior_NDVI_filename,
            posterior_NDVI_UQ_filename,
            posterior_NDVI_flag_filename,
            posterior_NDVI_bias_filename,
            posterior_NDVI_bias_UQ_filename,
            posterior_albedo_filename,
            posterior_albedo_UQ_filename,
            posterior_albedo_flag_filename,
            posterior_albedo_bias_filename,
            posterior_albedo_bias_UQ_filename,
        ]
        for f in posterior_files:
            if f is not None and exists(f):
                logger.info(f"Removing posterior file: {cl.file(f)}")
                remove(f)
