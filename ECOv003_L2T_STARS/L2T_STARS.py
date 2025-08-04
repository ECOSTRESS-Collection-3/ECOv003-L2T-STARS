import argparse
import logging
import sys
from datetime import date, timedelta
from os import makedirs
from os.path import join, exists
from typing import Union
import logging
import colored_logging as cl
import pandas as pd
from dateutil import parser

from sentinel_tiles import sentinel_tiles

# Custom modules for Harmonized Landsat Sentinel (HLS) and ECOSTRESS data
from harmonized_landsat_sentinel import (
    CMRServerUnreachable,
    HLS2Connection,
    HLSTileNotAvailable,
    HLSSentinelMissing,
    HLSLandsatMissing,
    HLSNotAvailable,
    HLSBandNotAcquired,
    CMR_SEARCH_URL
)

from .LPDAAC.LPDAACDataPool import LPDAACServerUnreachable

from ECOv003_exit_codes import *

from ECOv002_granules import L2TLSTE
import urllib

from .version import __version__
from .constants import *
from .VIIRS.VNP43IA4 import VNP43IA4
from .VIIRS.VNP43MA3 import VNP43MA3
from .VNP43NRT import VNP43NRT
from .runconfig import ECOSTRESSRunConfig
from .L2TSTARSConfig import L2TSTARSConfig
from .load_prior import load_prior
from .generate_STARS_inputs import generate_STARS_inputs
from .process_STARS_product import process_STARS_product
from .retrieve_STARS_sources import retrieve_STARS_sources

logger = logging.getLogger(__name__)

def L2T_STARS(
    runconfig_filename: str,
    date_UTC: Union[date, str] = None,
    spinup_days: int = SPINUP_DAYS,
    target_resolution: int = TARGET_RESOLUTION,
    NDVI_resolution: int = NDVI_RESOLUTION,
    albedo_resolution: int = ALBEDO_RESOLUTION,
    use_VNP43NRT: bool = USE_VNP43NRT,
    calibrate_fine: bool = CALIBRATE_FINE,
    sources_only: bool = SOURCES_ONLY,
    remove_input_staging: bool = REMOVE_INPUT_STAGING,
    remove_prior: bool = REMOVE_PRIOR,
    remove_posterior: bool = REMOVE_POSTERIOR,
    initialize_julia: bool = INITIALIZE_JULIA,
    threads: Union[int, str] = THREADS,
    num_workers: int = WORKERS,
    overwrite: bool = OVERWRITE, # New parameter for overwriting existing files
) -> int:
    """
    ECOSTRESS Collection 3 L2T_STARS PGE (Product Generation Executive).

    This function serves as the main entry point for the L2T_STARS processing.
    It orchestrates the entire workflow, including reading the run-config,
    connecting to data servers, retrieving source data, performing data fusion
    (via Julia subprocess), generating the final product, and handling cleanup.

    Args:
        runconfig_filename (str): Path to the XML run-configuration file.
        date_UTC (Union[date, str], optional): The target UTC date for product generation.
                                              If None, it's derived from the input L2T LSTE granule.
        spinup_days (int, optional): Number of days for the VIIRS time-series spin-up.
                                     Defaults to DEFAULT_SPINUP_DAYS (7).
        target_resolution (int, optional): The desired output resolution in meters.
                                           Defaults to DEFAULT_TARGET_RESOLUTION (70).
        NDVI_resolution (int, optional): The resolution of the coarse NDVI data.
                                         Defaults to DEFAULT_NDVI_RESOLUTION (490).
        albedo_resolution (int, optional): The resolution of the coarse albedo data.
                                           Defaults to DEFAULT_ALBEDO_RESOLUTION (980).
        use_VNP43NRT (bool, optional): If True, use VNP43NRT for VIIRS products.
                                       If False, use VNP43IA4 (NDVI) and VNP43MA3 (Albedo).
                                       Defaults to DEFAULT_USE_VNP43NRT (True).
        calibrate_fine (bool, optional): If True, calibrate fine resolution HLS data to
                                         coarse resolution VIIRS data. Defaults to DEFAULT_CALIBRATE_FINE (False).
        sources_only (bool, optional): If True, only retrieve source data and exit,
                                       without performing data fusion. Defaults to False.
        remove_input_staging (bool, optional): If True, remove the input staging directory
                                                after processing. Defaults to True.
        remove_prior (bool, optional): If True, remove prior intermediate files after use.
                                       Defaults to True.
        remove_posterior (bool, optional): If True, remove posterior intermediate files after
                                           product generation. Defaults to True.
        threads (Union[int, str], optional): Number of Julia threads to use, or "auto".
                                            Defaults to "auto".
        num_workers (int, optional): Number of Julia workers for distributed processing.
                                     Defaults to 4.
        overwrite (bool, optional): If True, existing output files will be overwritten.
                                    Defaults to False.

    Returns:
        int: An exit code indicating the success or failure of the PGE execution.
             (e.g., SUCCESS_EXIT_CODE, AUXILIARY_SERVER_UNREACHABLE, DOWNLOAD_FAILED, etc.)
    """
    exit_code = SUCCESS_EXIT_CODE  # Initialize exit code to success

    try:
        # Load and parse the run-configuration file
        runconfig = L2TSTARSConfig(runconfig_filename)

        # Configure logging with the specified log filename from runconfig
        working_directory = runconfig.working_directory
        granule_ID = runconfig.granule_ID
        log_filename = join(working_directory, "log", f"{granule_ID}.log")
        cl.configure(filename=log_filename)  # Reconfigure logger with the specific log file

        logger.info(f"L2T_STARS PGE ({cl.val(__version__)})")
        logger.info(f"L2T_STARS run-config: {cl.file(runconfig_filename)}")
        logger.info(f"Granule ID: {cl.val(granule_ID)}")

        # Extract paths from the run-config
        L2T_STARS_granule_directory = runconfig.L2T_STARS_granule_directory
        logger.info(f"Granule directory: {cl.dir(L2T_STARS_granule_directory)}")
        L2T_STARS_zip_filename = runconfig.L2T_STARS_zip_filename
        logger.info(f"Zip filename: {cl.file(L2T_STARS_zip_filename)}")
        L2T_STARS_browse_filename = runconfig.L2T_STARS_browse_filename
        logger.info(f"Browse filename: " + cl.file(L2T_STARS_browse_filename))

        # Check if the final product already exists and 'overwrite' is not enabled
        if not overwrite and exists(L2T_STARS_zip_filename) and exists(L2T_STARS_browse_filename):
            logger.info(f"Found existing L2T STARS file: {L2T_STARS_zip_filename}")
            logger.info(f"Found existing L2T STARS preview: {L2T_STARS_browse_filename}")
            logger.info("Overwrite option is not enabled, skipping reprocessing.")
            return SUCCESS_EXIT_CODE
        elif overwrite and exists(L2T_STARS_zip_filename) and exists(L2T_STARS_browse_filename):
            logger.info(f"Found existing L2T STARS file: {L2T_STARS_zip_filename}")
            logger.info(f"Found existing L2T STARS preview: {L2T_STARS_browse_filename}")
            logger.info("Overwrite option is enabled, proceeding with reprocessing.")


        logger.info(f"Working directory: {cl.dir(working_directory)}")
        logger.info(f"Log file: {cl.file(log_filename)}")

        input_staging_directory = join(working_directory, "input_staging")
        logger.info(f"Input staging directory: {cl.dir(input_staging_directory)}")

        sources_directory = runconfig.sources_directory
        logger.info(f"Source directory: {cl.dir(sources_directory)}")
        indices_directory = runconfig.indices_directory
        logger.info(f"Indices directory: {cl.dir(indices_directory)}")
        model_directory = runconfig.model_directory
        logger.info(f"Model directory: {cl.dir(model_directory)}")
        output_directory = runconfig.output_directory
        logger.info(f"Output directory: {cl.dir(output_directory)}")
        tile = runconfig.tile
        logger.info(f"Tile: {cl.val(tile)}")
        build = runconfig.build
        logger.info(f"Build: {cl.val(build)}")
        product_counter = runconfig.product_counter
        logger.info(f"Product counter: {cl.val(product_counter)}")
        L2T_LSTE_filename = runconfig.L2T_LSTE_filename
        logger.info(f"Input L2T LSTE file: {cl.file(L2T_LSTE_filename)}")

        # Validate existence of input L2T LSTE file
        if not exists(L2T_LSTE_filename):
            raise InputFilesInaccessible(
                f"L2T LSTE file does not exist: {L2T_LSTE_filename}"
            )

        # Load the L2T_LSTE granule to get geometry and base metadata
        l2t_granule = L2TLSTE(L2T_LSTE_filename)
        geometry = l2t_granule.geometry
        metadata = l2t_granule.metadata_dict
        metadata["StandardMetadata"]["PGEName"] = "L2T_STARS"

        # Update product names in metadata
        short_name = L2T_STARS_SHORT_NAME
        logger.info(f"L2T STARS short name: {cl.val(short_name)}")
        metadata["StandardMetadata"]["ShortName"] = short_name

        long_name = L2T_STARS_LONG_NAME
        logger.info(f"L2T STARS long name: {cl.val(long_name)}")
        metadata["StandardMetadata"]["LongName"] = long_name

        # Update auxiliary input pointers in metadata and remove irrelevant sections
        metadata["StandardMetadata"]["AuxiliaryInputPointer"] = "HLS,VIIRS"
        if "ProductMetadata" in metadata:
            metadata["ProductMetadata"].pop("AuxiliaryNWP", None)  # Safe removal
            metadata["ProductMetadata"].pop("NWPSource", None)

        # Determine the target date for processing
        time_UTC = l2t_granule.time_UTC
        logger.info(f"ECOSTRESS overpass time: {cl.time(f'{time_UTC:%Y-%m-%d %H:%M:%S} UTC')}")

        if date_UTC is None:
            # Use date from L2T granule if not provided via command line
            date_UTC = l2t_granule.date_UTC
            logger.info(f"ECOSTRESS overpass date: {cl.time(f'{date_UTC:%Y-%m-%d} UTC')}")
        else:
            logger.warning(f"Over-riding target date from command line to: {date_UTC}")
            if isinstance(date_UTC, str):
                date_UTC = parser.parse(date_UTC).date()

        # TODO: Add a check if the L2T LSTE granule is day-time and halt L2T STARS run if it's not.
        # This is a critical step to ensure valid scientific output.

        # Load prior data if specified in the run-config
        L2T_STARS_prior_filename = runconfig.L2T_STARS_prior_filename
        prior = load_prior(
            tile=tile,
            target_resolution=target_resolution,
            model_directory=model_directory,
            L2T_STARS_prior_filename=L2T_STARS_prior_filename,
        )
        using_prior = prior.using_prior
        prior_date_UTC = prior.prior_date_UTC

        # Define various product and download directories
        products_directory = join(working_directory, STARS_PRODUCTS_DIRECTORY)
        logger.info(f"STARS products directory: {cl.dir(products_directory)}")
        HLS_download_directory = join(sources_directory, HLS_DOWNLOAD_DIRECTORY)
        logger.info(f"HLS download directory: {cl.dir(HLS_download_directory)}")
        HLS_products_directory = join(sources_directory, HLS_PRODUCTS_DIRECTORY)
        logger.info(f"HLS products directory: {cl.dir(HLS_products_directory)}")
        VIIRS_download_directory = join(sources_directory, VIIRS_DOWNLOAD_DIRECTORY)
        logger.info(f"VIIRS download directory: {cl.dir(VIIRS_download_directory)}")
        VIIRS_products_directory = join(sources_directory, VIIRS_PRODUCTS_DIRECTORY)
        logger.info(f"VIIRS products directory: {cl.dir(VIIRS_products_directory)}")
        VIIRS_mosaic_directory = join(sources_directory, VIIRS_MOSAIC_DIRECTORY)
        logger.info(f"VIIRS mosaic directory: {cl.dir(VIIRS_mosaic_directory)}")
        GEOS5FP_download_directory = join(sources_directory, GEOS5FP_DOWNLOAD_DIRECTORY)
        logger.info(f"GEOS-5 FP download directory: {cl.dir(GEOS5FP_download_directory)}")
        GEOS5FP_products_directory = join(sources_directory, GEOS5FP_PRODUCTS_DIRECTORY)
        logger.info(f"GEOS-5 FP products directory: {cl.dir(GEOS5FP_products_directory)}")
        VNP09GA_products_directory = join(sources_directory, VNP09GA_PRODUCTS_DIRECTORY)
        logger.info(f"VNP09GA products directory: {cl.dir(VNP09GA_products_directory)}")
        VNP43NRT_products_directory = join(sources_directory, VNP43NRT_PRODUCTS_DIRECTORY)
        logger.info(f"VNP43NRT products directory: {cl.dir(VNP43NRT_products_directory)}")
        DOWNSAMPLED_products_directory = join(sources_directory, STARS_DOWNSAMPLED_DIRECTORY)
        logger.info(f"DOWNSAMPLED products directory: {cl.dir(DOWNSAMPLED_products_directory)}")

        # Re-check for existing product (double-check in case another process created it) with overwrite option
        if not overwrite and exists(L2T_STARS_zip_filename):
            logger.info(
                f"Found L2T STARS product zip: {cl.file(L2T_STARS_zip_filename)}. Overwrite is False, returning."
            )
            return exit_code
        elif overwrite and exists(L2T_STARS_zip_filename):
            logger.info(
                f"Found L2T STARS product zip: {cl.file(L2T_STARS_zip_filename)}. Overwrite is True, proceeding."
            )


        # Initialize HLS data connection
        logger.info(f"Connecting to CMR Search server: {CMR_SEARCH_URL}")
        try:
            HLS_connection = HLS2Connection(
                working_directory=working_directory,
                download_directory=HLS_download_directory,
                # products_directory=HLS_products_directory,
                target_resolution=target_resolution,
            )
        except CMRServerUnreachable as e:
            logger.exception(e)
            raise AuxiliaryServerUnreachable(
                f"Unable to connect to CMR Search server: {CMR_SEARCH_URL}"
            )

        # Check if the tile is on land (HLS tiles cover land and ocean, STARS is for land)
        if not sentinel_tiles.land(tile=tile):
            raise LandFilter(f"Sentinel tile {tile} is not on land. Skipping processing.")

        # Initialize VIIRS data connections based on 'use_VNP43NRT' flag
        if use_VNP43NRT:
            try:
                NDVI_VIIRS_connection = VNP43NRT(
                    working_directory=working_directory,
                    download_directory=VIIRS_download_directory,
                    mosaic_directory=VIIRS_mosaic_directory,
                    GEOS5FP_download=GEOS5FP_download_directory,
                    GEOS5FP_products=GEOS5FP_products_directory,
                    VNP09GA_directory=VNP09GA_products_directory,
                    VNP43NRT_directory=VNP43NRT_products_directory,
                    initialize_julia=initialize_julia,
                )

                albedo_VIIRS_connection = VNP43NRT(
                    working_directory=working_directory,
                    download_directory=VIIRS_download_directory,
                    mosaic_directory=VIIRS_mosaic_directory,
                    GEOS5FP_download=GEOS5FP_download_directory,
                    GEOS5FP_products=GEOS5FP_products_directory,
                    VNP09GA_directory=VNP09GA_products_directory,
                    VNP43NRT_directory=VNP43NRT_products_directory,
                    initialize_julia=initialize_julia,
                )
            except CMRServerUnreachable as e:
                logger.exception(e)
                raise AuxiliaryServerUnreachable(f"Unable to connect to CMR search server for VNP43NRT.")
        else:
            try:
                NDVI_VIIRS_connection = VNP43IA4(
                    working_directory=working_directory,
                    download_directory=VIIRS_download_directory,
                    products_directory=VIIRS_products_directory,
                    mosaic_directory=VIIRS_mosaic_directory,
                )

                albedo_VIIRS_connection = VNP43MA3(
                    working_directory=working_directory,
                    download_directory=VIIRS_download_directory,
                    products_directory=VIIRS_products_directory,
                    mosaic_directory=VIIRS_mosaic_directory,
                )
            except LPDAACServerUnreachable as e:
                logger.exception(e)
                raise AuxiliaryServerUnreachable(f"Unable to connect to VIIRS LPDAAC server.")

        # Define date ranges for data retrieval and fusion
        end_date = date_UTC
        # The start date of the BRDF-corrected VIIRS coarse time-series is 'spinup_days' before the target date
        VIIRS_start_date = end_date - timedelta(days=spinup_days)
        # To produce that first BRDF-corrected image, VNP09GA (raw VIIRS) is needed starting 16 days prior to the first coarse date
        VIIRS_download_start_date = VIIRS_start_date - timedelta(days=16)
        VIIRS_end_date = end_date

        # Define start date of HLS fine image input time-series
        if using_prior and prior_date_UTC and prior_date_UTC >= VIIRS_start_date:
            # If a valid prior is used and its date is within or before the VIIRS start date,
            # HLS inputs begin the day after the prior
            HLS_start_date = prior_date_UTC + timedelta(days=1)
        else:
            # If no prior or prior is too old, HLS inputs begin on the same day as the VIIRS inputs
            HLS_start_date = VIIRS_start_date
        HLS_end_date = end_date # HLS end date is always the same as the target date

        logger.info(
            f"Processing STARS HLS-VIIRS NDVI and albedo for tile {cl.place(tile)} from "
            f"{cl.time(VIIRS_start_date)} to {cl.time(end_date)}"
        )

        # Get HLS listing to check for data availability
        try:
            HLS_listing = HLS_connection.listing(
                tile=tile, start_UTC=HLS_start_date, end_UTC=HLS_end_date
            )
        except HLSTileNotAvailable as e:
            logger.exception(e)
            raise LandFilter(f"Sentinel tile {tile} cannot be processed due to HLS tile unavailability.")
        except Exception as e:
            logger.exception(e)
            raise AuxiliaryServerUnreachable(
                f"Unable to scan Harmonized Landsat Sentinel server: {HLS_connection.remote}"
            )

        # Check for missing HLS Sentinel data
        missing_sentinel_dates = HLS_listing[HLS_listing.sentinel == "missing"].date_UTC
        if len(missing_sentinel_dates) > 0:
            raise AuxiliaryLatency(
                f"HLS Sentinel is not yet available at tile {tile} for dates: "
                f"{', '.join(missing_sentinel_dates)}"
            )

        # Log available HLS Sentinel data
        sentinel_listing = HLS_listing[~pd.isna(HLS_listing.sentinel)][
            ["date_UTC", "sentinel"]
        ]
        logger.info(f"HLS Sentinel is available on {cl.val(len(sentinel_listing))} dates:")
        for i, (list_date_utc, sentinel_granule) in sentinel_listing.iterrows():
            sentinel_filename = sentinel_granule["meta"]["native-id"]
            logger.info(f"* {cl.time(list_date_utc)}: {cl.file(sentinel_filename)}")

        # Check for missing HLS Landsat data
        missing_landsat_dates = HLS_listing[HLS_listing.landsat == "missing"].date_UTC
        if len(missing_landsat_dates) > 0:
            raise AuxiliaryLatency(
                f"HLS Landsat is not yet available at tile {tile} for dates: "
                f"{', '.join(missing_landsat_dates)}"
            )

        # Log available HLS Landsat data
        landsat_listing = HLS_listing[~pd.isna(HLS_listing.landsat)][
            ["date_UTC", "landsat"]
        ]
        logger.info(f"HLS Landsat is available on {cl.val(len(landsat_listing))} dates:")
        for i, (list_date_utc, landsat_granule) in landsat_listing.iterrows():
            landsat_filename = landsat_granule["meta"]["native-id"]
            logger.info(f"* {cl.time(list_date_utc)}: {cl.file(landsat_filename)}")

        # If only sources are requested, retrieve them and exit
        if sources_only:
            logger.info("Sources only flag enabled. Retrieving source data.")
            retrieve_STARS_sources(
                tile=tile,
                geometry=geometry,
                HLS_start_date=HLS_start_date,
                HLS_end_date=HLS_end_date,
                VIIRS_start_date=VIIRS_download_start_date,
                VIIRS_end_date=VIIRS_end_date,
                HLS_connection=HLS_connection,
                VIIRS_connection=NDVI_VIIRS_connection, # Use NDVI_VIIRS_connection as a general VIIRS connection
            )
            # Regenerate inputs to ensure all files are staged, even if not fused
            NDVI_coarse_geometry = HLS_connection.grid(tile=tile, cell_size=NDVI_resolution)
            albedo_coarse_geometry = HLS_connection.grid(tile=tile, cell_size=albedo_resolution)

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
                downsampled_directory=DOWNSAMPLED_products_directory,
                HLS_connection=HLS_connection,
                NDVI_VIIRS_connection=NDVI_VIIRS_connection,
                albedo_VIIRS_connection=albedo_VIIRS_connection,
                calibrate_fine=calibrate_fine,
            )
        else:
            # Otherwise, proceed with full product processing
            process_STARS_product(
                tile=tile,
                date_UTC=date_UTC,
                time_UTC=time_UTC,
                build=build,
                product_counter=product_counter,
                HLS_start_date=HLS_start_date,
                HLS_end_date=HLS_end_date,
                VIIRS_start_date=VIIRS_start_date,
                VIIRS_end_date=VIIRS_end_date,
                NDVI_resolution=NDVI_resolution,
                albedo_resolution=albedo_resolution,
                target_resolution=target_resolution,
                downsampled_directory=DOWNSAMPLED_products_directory,
                model_directory=model_directory,
                input_staging_directory=input_staging_directory,
                L2T_STARS_granule_directory=L2T_STARS_granule_directory,
                L2T_STARS_zip_filename=L2T_STARS_zip_filename,
                L2T_STARS_browse_filename=L2T_STARS_browse_filename,
                metadata=metadata,
                prior=prior,
                HLS_connection=HLS_connection,
                NDVI_VIIRS_connection=NDVI_VIIRS_connection,
                albedo_VIIRS_connection=albedo_VIIRS_connection,
                using_prior=using_prior,
                calibrate_fine=calibrate_fine,
                remove_input_staging=remove_input_staging,
                remove_prior=remove_prior,
                remove_posterior=remove_posterior,
                initialize_julia=initialize_julia,
                threads=threads,
                num_workers=num_workers,
            )

    # --- Exception Handling for PGE ---
    except (ConnectionError, urllib.error.HTTPError, CMRServerUnreachable) as exception:
        logger.exception(exception)
        exit_code = AUXILIARY_SERVER_UNREACHABLE
    except DownloadFailed as exception:
        logger.exception(exception)
        exit_code = DOWNLOAD_FAILED
    except HLSBandNotAcquired as exception:
        logger.exception(exception)
        exit_code = DOWNLOAD_FAILED
    except HLSNotAvailable as exception:
        logger.exception(exception)
        exit_code = LAND_FILTER  # This might indicate no HLS data for the tile, similar to land filter
    except (HLSSentinelMissing, HLSLandsatMissing) as exception:
        logger.exception(exception)
        exit_code = AUXILIARY_LATENCY
    except ECOSTRESSExitCodeException as exception:
        # Catch custom ECOSTRESS exceptions and use their defined exit code
        logger.exception(exception)
        exit_code = exception.exit_code
    except Exception as exception:
        # Catch any other unexpected exceptions
        logger.exception(exception)
        exit_code = UNCLASSIFIED_FAILURE_EXIT_CODE

    logger.info(f"L2T_STARS exit code: {exit_code}")
    return exit_code
