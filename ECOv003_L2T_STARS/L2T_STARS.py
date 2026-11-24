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
from .install_julia import install_julia
from .process_STARS_product import process_STARS_product
from .retrieve_STARS_sources import retrieve_STARS_sources
from .smoke_test import (
    test as run_smoke_test,
    test_julia as run_test_julia,
    test_python as run_test_python,
    test_rust as run_test_rust,
)

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
        metadata["StandardMetadata"]["PGEVersion"] = __version__

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


def _run_subtest(test_fn) -> int:
    """Helper to run a sub-test function, print results, and return an exit code."""
    failed = test_fn()
    if failed:
        print(f"\n{len(failed)} smoke test failure(s)")
        return 1
    print("\nSmoke tests passed")
    return SUCCESS_EXIT_CODE


def build_parser() -> argparse.ArgumentParser:
    """Builds and returns the argparse parser for ECOv003-L2T-STARS."""
    parser = argparse.ArgumentParser(
        prog="ECOv003-L2T-STARS",
        description="ECOSTRESS Collection 3 L2T_STARS PGE for generating Tiled Auxiliary NDVI and Albedo products.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=f"L2T_STARS PGE Version: {__version__}\n\n"
        "Commands:\n"
        "  test                 Run Python and Rust extension smoke tests\n"
        "  test-python          Run Python-only import and dummy tests\n"
        "  test-rust            Run Rust (_stars_rust) extension smoke tests\n"
        "  test-julia           Run optional legacy Julia smoke tests\n"
        "  install-julia        Install optional legacy Julia runtime and packages\n\n"
        "Example usage:\n"
        "  ECOv003-L2T-STARS /path/to/RunConfig.xml\n"
        "  ECOv003-L2T-STARS /path/to/RunConfig.xml --backend rust --num-workers 8\n"
        "  ECOv003-L2T-STARS /path/to/RunConfig.xml --backend julia\n"
        "  ECOv003-L2T-STARS test\n",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        default=False,
        help="Run Python and Rust extension smoke tests.",
    )
    parser.add_argument(
        "runconfig",
        nargs="?",
        type=str,
        help="Path to the XML run-configuration file.",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Target UTC date for product generation (YYYY-MM-DD). Overrides date in runconfig.",
        metavar="YYYY-MM-DD",
    )
    parser.add_argument(
        "--spinup-days",
        type=int,
        default=SPINUP_DAYS,
        help=f"Number of days for the VIIRS time-series spin-up. Defaults to {SPINUP_DAYS} days.",
        metavar="DAYS",
    )
    parser.add_argument(
        "--target-resolution",
        type=int,
        default=TARGET_RESOLUTION,
        help=f"Desired output product resolution in meters. Defaults to {TARGET_RESOLUTION}m.",
        metavar="METERS",
    )
    parser.add_argument(
        "--ndvi-resolution",
        type=int,
        default=NDVI_RESOLUTION,
        help=f"Resolution of coarse NDVI data in meters. Defaults to {NDVI_RESOLUTION}m.",
        metavar="METERS",
    )
    parser.add_argument(
        "--albedo-resolution",
        type=int,
        default=ALBEDO_RESOLUTION,
        help=f"Resolution of coarse albedo data in meters. Defaults to {ALBEDO_RESOLUTION}m.",
        metavar="METERS",
    )
    parser.add_argument(
        "--viirs-mission-priority",
        type=lambda value: tuple(
            mission.strip() for mission in value.split(",") if mission.strip()
        ),
        default=VCD43NRT_MISSION_PRIORITY,
        metavar="MISSION[,MISSION...]",
        help=(
            "Ordered VIIRS mission preference for each observation date "
            "(SNPP,JPSS1,JPSS2 by default)."
        ),
    )
    parser.add_argument(
        "--calibrate-fine",
        action="store_true",
        default=CALIBRATE_FINE,
        help=f"Calibrate fine resolution HLS data to coarse resolution VIIRS data. Defaults to {'True' if CALIBRATE_FINE else 'False'}.",
    )
    parser.add_argument(
        "--sources-only",
        action="store_true",
        help="Only retrieve and stage source data (HLS, VIIRS); do not perform data fusion or generate final product.",
    )
    parser.add_argument(
        "--no-remove-input-staging",
        action="store_false",
        dest="remove_input_staging",
        default=True,
        help="Do NOT remove the input staging directory after processing.",
    )
    parser.add_argument(
        "--no-remove-prior",
        action="store_false",
        dest="remove_prior",
        default=REMOVE_PRIOR,
        help="Do NOT remove prior intermediate files after use.",
    )
    parser.add_argument(
        "--no-remove-posterior",
        action="store_false",
        dest="remove_posterior",
        default=REMOVE_POSTERIOR,
        help="Do NOT remove posterior intermediate files after product generation.",
    )
    parser.add_argument(
        "--backend",
        choices=("rust", "julia"),
        default=FUSION_BACKEND,
        help=f"STARS data fusion backend ('rust' default, 'julia' legacy). Defaults to {FUSION_BACKEND!r}.",
    )
    parser.add_argument(
        "--initialize-julia",
        action="store_true",
        dest="initialize_julia",
        help="Initialize a julia environment before running legacy Julia backend.",
    )
    parser.add_argument(
        "--threads",
        type=str,
        default="auto",
        help='Number of Julia threads to use when --backend julia is set, or "auto". Defaults to "auto".',
        metavar="COUNT",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=WORKERS,
        help=f"Number of parallel worker threads/processes for data fusion. Defaults to {WORKERS}.",
        metavar="COUNT",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Reproduce the output files even if they already exist.",
    )

    return parser


def main(argv=None) -> int:
    """
    Main function for parsing command-line arguments and running the L2T_STARS PGE.
    """
    if argv is None:
        argv = sys.argv[1:]
    elif len(argv) > 0 and argv[0] == sys.argv[0]:
        argv = argv[1:]

    first_arg = argv[0] if len(argv) > 0 else None

    if first_arg == "test":
        return run_smoke_test()
    elif first_arg == "test-python":
        return _run_subtest(run_test_python)
    elif first_arg == "test-rust":
        return _run_subtest(run_test_rust)
    elif first_arg == "test-julia":
        return _run_subtest(run_test_julia)
    elif first_arg == "install-julia":
        install_julia()
        return SUCCESS_EXIT_CODE

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.test:
        return run_smoke_test()

    if not args.runconfig:
        parser.print_usage()
        return RUNCONFIG_FILENAME_NOT_SUPPLIED

    exit_code = L2T_STARS(
        runconfig_filename=args.runconfig,
        date_UTC=args.date,
        spinup_days=args.spinup_days,
        target_resolution=args.target_resolution,
        NDVI_resolution=args.ndvi_resolution,
        albedo_resolution=args.albedo_resolution,
        viirs_mission_priority=args.viirs_mission_priority,
        calibrate_fine=args.calibrate_fine,
        sources_only=args.sources_only,
        remove_input_staging=args.remove_input_staging,
        remove_prior=args.remove_prior,
        remove_posterior=args.remove_posterior,
        backend=args.backend,
        initialize_julia=args.initialize_julia,
        threads=args.threads,
        num_workers=args.num_workers,
        overwrite=args.overwrite,
    )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
