import argparse
import logging
import sys
from datetime import date, timedelta
from os import makedirs
from os.path import join, exists, basename
from typing import Literal, Sequence, Union
import urllib

import colored_logging as cl
logging.getLogger("numexpr").setLevel(logging.WARNING)
import pandas as pd
from dateutil import parser

from sentinel_tiles import sentinel_tiles

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

from ECOv003_exit_codes import *

from ECOv002_granules import L2TLSTE as ECOv002L2TLSTE
from ECOv003_granules import L2TLSTE

from VCD43NRT.exceptions import (
    CMRServerUnreachable as VCD43NRTCMRServerUnreachable,
    DownloadFailed as VCD43NRTDownloadFailed,
    VIIRSUnavailableError as VCD43NRTVIIRSUnavailableError,
)

from .version import __version__
from .constants import *
from VCD43NRT import VCD43NRT
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
    viirs_mission_priority: Union[str, Sequence[str]] = VCD43NRT_MISSION_PRIORITY,
    calibrate_fine: bool = CALIBRATE_FINE,
    sources_only: bool = SOURCES_ONLY,
    remove_input_staging: bool = REMOVE_INPUT_STAGING,
    remove_prior: bool = REMOVE_PRIOR,
    remove_posterior: bool = REMOVE_POSTERIOR,
    backend: Literal["rust", "julia"] = FUSION_BACKEND,
    initialize_julia: bool = False,
    threads: Union[int, str] = THREADS,
    num_workers: int = WORKERS,
    overwrite: bool = OVERWRITE,
) -> int:
    """
    ECOSTRESS Collection 3 L2T_STARS PGE (Product Generation Executive).
    """
    exit_code = SUCCESS_EXIT_CODE

    try:
        if backend not in ("rust", "julia"):
            raise ValueError(f"Unsupported STARS fusion backend: {backend!r} (expected 'rust' or 'julia')")

        # Load and parse the run-configuration file
        runconfig = L2TSTARSConfig(runconfig_filename)

        # Configure logging with the specified log filename from runconfig
        working_directory = runconfig.working_directory
        granule_ID = runconfig.granule_ID
        log_filename = join(working_directory, "log", f"{granule_ID}.log")
        cl.configure(filename=log_filename)

        logger.info(f"L2T_STARS PGE ({cl.val(__version__)})")
        logger.info(f"L2T_STARS run-config: {cl.file(runconfig_filename)}")
        logger.info(f"Granule ID: {cl.val(granule_ID)}")
        logger.info(f"Fusion backend: {cl.val(backend)}")

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

        # Determine collection from the L2T LSTE filename
        collection = basename(L2T_LSTE_filename).split("_")[0]

        if collection == "ECOv003":
            L2T_LSTE_granule = L2TLSTE(L2T_LSTE_filename)
        elif collection == "ECOv002":
            L2T_LSTE_granule = ECOv002L2TLSTE(L2T_LSTE_filename)
        else:
            raise ValueError(f"Unsupported collection in filename: {L2T_LSTE_filename}")

        geometry = L2T_LSTE_granule.geometry
        metadata = L2T_LSTE_granule.metadata_dict
        metadata["StandardMetadata"]["PGEName"] = "L2T_STARS"

        input_pointer = basename(L2T_LSTE_filename)
        metadata["StandardMetadata"]["InputPointer"] = input_pointer

        short_name = L2T_STARS_SHORT_NAME
        logger.info(f"L2T STARS short name: {cl.val(short_name)}")
        metadata["StandardMetadata"]["ShortName"] = short_name

        long_name = L2T_STARS_LONG_NAME
        logger.info(f"L2T STARS long name: {cl.val(long_name)}")
        metadata["StandardMetadata"]["LongName"] = long_name

        metadata["StandardMetadata"]["AuxiliaryInputPointer"] = "HLS,VIIRS"
        if "ProductMetadata" in metadata:
            metadata["ProductMetadata"].pop("AuxiliaryNWP", None)
            metadata["ProductMetadata"].pop("NWPSource", None)

        time_UTC = L2T_LSTE_granule.time_UTC
        logger.info(f"ECOSTRESS overpass time: {cl.time(f'{time_UTC:%Y-%m-%d %H:%M:%S} UTC')}")

        if date_UTC is None:
            date_UTC = L2T_LSTE_granule.date_UTC
            logger.info(f"ECOSTRESS overpass date: {cl.time(f'{date_UTC:%Y-%m-%d} UTC')}")
        else:
            logger.warning(f"Over-riding target date from command line to: {date_UTC}")
            if isinstance(date_UTC, str):
                date_UTC = parser.parse(date_UTC).date()

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

        products_directory = join(working_directory, STARS_PRODUCTS_DIRECTORY)
        logger.info(f"STARS products directory: {cl.dir(products_directory)}")
        HLS_download_directory = join(sources_directory, HLS_DOWNLOAD_DIRECTORY)
        logger.info(f"HLS download directory: {cl.dir(HLS_download_directory)}")
        HLS_products_directory = join(sources_directory, HLS_PRODUCTS_DIRECTORY)
        logger.info(f"HLS products directory: {cl.dir(HLS_products_directory)}")
        VCD43NRT_download_directory = join(sources_directory, VCD43NRT_DOWNLOAD_DIRECTORY)
        logger.info(f"VCD43NRT download directory: {cl.dir(VCD43NRT_download_directory)}")
        VCD43NRT_input_products_directory = join(
            sources_directory, VCD43NRT_INPUT_PRODUCTS_DIRECTORY
        )
        logger.info(
            f"VCD43NRT input products directory: {cl.dir(VCD43NRT_input_products_directory)}"
        )
        VCD43NRT_mosaic_directory = join(sources_directory, VCD43NRT_MOSAIC_DIRECTORY)
        logger.info(f"VCD43NRT mosaic directory: {cl.dir(VCD43NRT_mosaic_directory)}")
        GEOS5FP_download_directory = join(sources_directory, GEOS5FP_DOWNLOAD_DIRECTORY)
        logger.info(f"GEOS-5 FP download directory: {cl.dir(GEOS5FP_download_directory)}")
        GEOS5FP_products_directory = join(sources_directory, GEOS5FP_PRODUCTS_DIRECTORY)
        logger.info(f"GEOS-5 FP products directory: {cl.dir(GEOS5FP_products_directory)}")
        VCD43NRT_products_directory = join(sources_directory, VCD43NRT_PRODUCTS_DIRECTORY)
        logger.info(f"VCD43NRT products directory: {cl.dir(VCD43NRT_products_directory)}")
        VCD43NRT_staging_directory = join(sources_directory, VCD43NRT_STAGING_DIRECTORY)
        logger.info(f"VCD43NRT staging directory: {cl.dir(VCD43NRT_staging_directory)}")
        DOWNSAMPLED_products_directory = join(sources_directory, STARS_DOWNSAMPLED_DIRECTORY)
        logger.info(f"DOWNSAMPLED products directory: {cl.dir(DOWNSAMPLED_products_directory)}")

        if not overwrite and exists(L2T_STARS_zip_filename):
            logger.info(
                f"Found L2T STARS product zip: {cl.file(L2T_STARS_zip_filename)}. Overwrite is False, returning."
            )
            return exit_code
        elif overwrite and exists(L2T_STARS_zip_filename):
            logger.info(
                f"Found L2T STARS product zip: {cl.file(L2T_STARS_zip_filename)}. Overwrite is True, proceeding."
            )

        logger.info(f"Connecting to CMR Search server: {CMR_SEARCH_URL}")
        try:
            HLS_connection = HLS2Connection(
                working_directory=working_directory,
                download_directory=HLS_download_directory,
                target_resolution=target_resolution,
            )
        except CMRServerUnreachable as e:
            logger.exception(e)
            raise AuxiliaryServerUnreachable(
                f"Unable to connect to CMR Search server: {CMR_SEARCH_URL}"
            )

        if not sentinel_tiles.land(tile=tile):
            raise LandFilter(f"Sentinel tile {tile} is not on land. Skipping processing.")

        if isinstance(viirs_mission_priority, str):
            viirs_mission_priority = tuple(
                mission.strip()
                for mission in viirs_mission_priority.split(",")
                if mission.strip()
            )
        else:
            viirs_mission_priority = tuple(viirs_mission_priority)

        if not viirs_mission_priority:
            raise ValueError("VIIRS mission priority cannot be empty")

        logger.info(
            f"VCD43NRT mission priority: {', '.join(viirs_mission_priority)}"
        )
        try:
            VCD43NRT_connection = VCD43NRT(
                working_directory=working_directory,
                download_directory=VCD43NRT_download_directory,
                mosaic_directory=VCD43NRT_mosaic_directory,
                GEOS5FP_download=GEOS5FP_download_directory,
                VNP09GA_directory=VCD43NRT_input_products_directory,
                VCD43NRT_directory=VCD43NRT_products_directory,
                VCD43NRT_staging_directory=VCD43NRT_staging_directory,
                mission=viirs_mission_priority[0],
                mission_priority=viirs_mission_priority,
                fallback_mode=True,
            )
        except VCD43NRTCMRServerUnreachable as e:
            logger.exception(e)
            raise AuxiliaryServerUnreachable(
                "Unable to connect to the VIIRS CMR search service."
            )

        NDVI_VCD43NRT_connection = VCD43NRT_connection
        albedo_VCD43NRT_connection = VCD43NRT_connection

        end_date = date_UTC
        VIIRS_start_date = end_date - timedelta(days=spinup_days)
        VIIRS_download_start_date = VIIRS_start_date - timedelta(days=16)
        VIIRS_end_date = end_date

        if using_prior and prior_date_UTC and prior_date_UTC >= VIIRS_start_date:
            HLS_start_date = prior_date_UTC + timedelta(days=1)
        else:
            HLS_start_date = VIIRS_start_date
        HLS_end_date = end_date

        logger.info(
            f"Processing STARS HLS-VIIRS NDVI and albedo for tile {cl.place(tile)} from "
            f"{cl.time(VIIRS_start_date)} to {cl.time(end_date)}"
        )

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
                f"Unable to scan Harmonized Landsat Sentinel server: {CMR_SEARCH_URL}"
            )

        missing_sentinel_dates = HLS_listing[HLS_listing.sentinel == "missing"].date_UTC
        if len(missing_sentinel_dates) > 0:
            raise AuxiliaryLatency(
                f"HLS Sentinel is not yet available at tile {tile} for dates: "
                f"{', '.join(missing_sentinel_dates)}"
            )

        sentinel_listing = HLS_listing[~pd.isna(HLS_listing.sentinel)][
            ["date_UTC", "sentinel"]
        ]
        logger.info(f"HLS Sentinel is available on {cl.val(len(sentinel_listing))} dates:")
        for i, (list_date_utc, sentinel_granule) in sentinel_listing.iterrows():
            sentinel_filename = sentinel_granule["meta"]["native-id"]
            logger.info(f"* {cl.time(list_date_utc)}: {cl.file(sentinel_filename)}")

        missing_landsat_dates = HLS_listing[HLS_listing.landsat == "missing"].date_UTC
        if len(missing_landsat_dates) > 0:
            raise AuxiliaryLatency(
                f"HLS Landsat is not yet available at tile {tile} for dates: "
                f"{', '.join(missing_landsat_dates)}"
            )

        landsat_listing = HLS_listing[~pd.isna(HLS_listing.landsat)][
            ["date_UTC", "landsat"]
        ]
        logger.info(f"HLS Landsat is available on {cl.val(len(landsat_listing))} dates:")
        for i, (list_date_utc, landsat_granule) in landsat_listing.iterrows():
            landsat_filename = landsat_granule["meta"]["native-id"]
            logger.info(f"* {cl.time(list_date_utc)}: {cl.file(landsat_filename)}")

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
                VCD43NRT_connection=NDVI_VCD43NRT_connection,
            )
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
                NDVI_VCD43NRT_connection=NDVI_VCD43NRT_connection,
                albedo_VCD43NRT_connection=albedo_VCD43NRT_connection,
                calibrate_fine=calibrate_fine,
            )
        else:
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
                NDVI_VCD43NRT_connection=NDVI_VCD43NRT_connection,
                albedo_VCD43NRT_connection=albedo_VCD43NRT_connection,
                using_prior=using_prior,
                calibrate_fine=calibrate_fine,
                remove_input_staging=remove_input_staging,
                remove_prior=remove_prior,
                remove_posterior=remove_posterior,
                backend=backend,
                initialize_julia=initialize_julia,
                threads=threads,
                num_workers=num_workers,
            )

    # --- Exception Handling for PGE ---
    except VCD43NRTDownloadFailed as exception:
        logger.exception(exception)
        exit_code = DOWNLOAD_FAILED
    except (
        ConnectionError,
        urllib.error.HTTPError,
        CMRServerUnreachable,
        VCD43NRTCMRServerUnreachable,
    ) as exception:
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
        exit_code = LAND_FILTER
    except (HLSSentinelMissing, HLSLandsatMissing, VCD43NRTVIIRSUnavailableError) as exception:
        logger.exception(exception)
        exit_code = AUXILIARY_LATENCY
    except LandFilter as exception:
        logger.info(exception)
        exit_code = LAND_FILTER
    except ECOSTRESSExitCodeException as exception:
        logger.exception(exception)
        exit_code = exception.exit_code
    except Exception as exception:
        logger.exception(exception)
        exit_code = UNCLASSIFIED_FAILURE_EXIT_CODE

    logger.info(f"L2T_STARS exit code: {exit_code}")
    return exit_code
