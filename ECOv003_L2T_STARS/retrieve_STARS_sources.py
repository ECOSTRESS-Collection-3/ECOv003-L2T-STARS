from datetime import date, timedelta
import logging

from rasters import RasterGeometry

import colored_logging as cl

from harmonized_landsat_sentinel import HLS2Connection

from harmonized_landsat_sentinel import (
    HLSTileNotAvailable,
    HLSSentinelNotAvailable,
    HLSLandsatNotAvailable,
    HLSDownloadFailed,
    HLSNotAvailable,
)

from ECOv003_exit_codes import *

from VCD43NRT import VCD43NRT

logger = logging.getLogger(__name__)

def retrieve_STARS_sources(
    tile: str,
    geometry: RasterGeometry,
    HLS_start_date: date,
    HLS_end_date: date,
    VIIRS_start_date: date,
    VIIRS_end_date: date,
    HLS_connection: HLS2Connection,
    VCD43NRT_connection: VCD43NRT):
    """
    Retrieves necessary Harmonized Landsat Sentinel (HLS) and VIIRS source data.

    This function downloads HLS Sentinel and Landsat data, and prefetches VIIRS VNP09GA
    data for the specified tile and date ranges. It includes error handling for
    download failures and data unavailability.

    Args:
        tile (str): The HLS tile ID.
        geometry (RasterGeometry): The spatial geometry of the area of interest.
        HLS_start_date (date): The start date for HLS data retrieval.
        HLS_end_date (date): The end date for HLS data retrieval.
        VIIRS_start_date (date): The start date for VIIRS data retrieval.
        VIIRS_end_date (date): The end date for VIIRS data retrieval.
        HLS_connection (HLS2Connection): An initialized HLS data connection object.
        VCD43NRT_connection (VCD43NRT): An initialized VIIRS processing connection.

    Raises:
        DownloadFailed: If an HLS download fails.
        AuxiliaryLatency: If HLS data for a given tile/date is not available (latency issue).
    """
    logger.info(
        f"Retrieving HLS sources for tile {cl.place(tile)} from {cl.time(HLS_start_date)} to {cl.time(HLS_end_date)}"
    )
    # Iterate through each day in the HLS date range to retrieve Sentinel and Landsat data
    for day_offset in range((HLS_end_date - HLS_start_date).days + 1):
        processing_date = HLS_start_date + timedelta(days=day_offset)
        try:
            logger.info(
                f"Retrieving HLS Sentinel at tile {cl.place(tile)} on date {cl.time(processing_date)}"
            )
            # Attempt to download HLS Sentinel data
            HLS_connection.sentinel(tile=tile, date_UTC=processing_date)
            logger.info(
                f"Retrieving HLS Landsat at tile {cl.place(tile)} on date {cl.time(processing_date)}"
            )
            # Attempt to download HLS Landsat data
            HLS_connection.landsat(tile=tile, date_UTC=processing_date)
        except HLSDownloadFailed as e:
            logger.exception(e)
            raise AuxiliaryDownloadFailed(e)
        except (
            HLSTileNotAvailable,
            HLSSentinelNotAvailable,
            HLSLandsatNotAvailable,
        ) as e:
            # Log warnings for data not being available, but continue processing
            logger.warning(e)
        except Exception as e:
            # Catch other unexpected exceptions during HLS retrieval
            logger.warning("Exception raised while retrieving HLS tiles")
            logger.exception(e)
            continue  # Continue to the next date even if one HLS retrieval fails

    logger.info(
        f"Retrieving VIIRS sources for tile {cl.place(tile)} from {cl.time(VIIRS_start_date)} to {cl.time(VIIRS_end_date)}"
    )
    # Prefetch VNP09GA data for the specified VIIRS date range and geometry
    VCD43NRT_connection.prefetch_VNP09GA(
        start_date=VIIRS_start_date,
        end_date=VIIRS_end_date,
        geometry=geometry,
    )
