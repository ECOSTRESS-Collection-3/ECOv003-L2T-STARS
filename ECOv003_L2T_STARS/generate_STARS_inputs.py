from typing import Union
from datetime import date, datetime
from dateutil.rrule import rrule, DAILY
from os.path import exists
import logging

import colored_logging as cl
from rasters import Raster, RasterGeometry
from harmonized_landsat_sentinel import HLS2Connection

from ECOv003_exit_codes import AuxiliaryLatency

from .constants import VIIRS_GIVEUP_DAYS
from .generate_filename import generate_filename
from .daterange import get_date
from .generate_NDVI_coarse_image import generate_NDVI_coarse_image
from .generate_NDVI_fine_image import generate_NDVI_fine_image
from .generate_albedo_coarse_image import generate_albedo_coarse_image
from .generate_albedo_fine_image import generate_albedo_fine_image
from .generate_downsampled_filename import generate_downsampled_filename
from .calibrate_fine_to_coarse import calibrate_fine_to_coarse
from .VIIRS.VIIRSDownloader import VIIRSDownloaderAlbedo, VIIRSDownloaderNDVI

logger = logging.getLogger(__name__)

def generate_STARS_inputs(
    tile: str,
    date_UTC: date,
    HLS_start_date: date,
    HLS_end_date: date,
    VIIRS_start_date: date,
    VIIRS_end_date: date,
    NDVI_resolution: int,
    albedo_resolution: int,
    target_resolution: int,
    NDVI_coarse_geometry: RasterGeometry,
    albedo_coarse_geometry: RasterGeometry,
    downsampled_directory: str,
    HLS_connection: HLS2Connection,
    NDVI_VIIRS_connection: VIIRSDownloaderNDVI,
    albedo_VIIRS_connection: VIIRSDownloaderAlbedo,
    calibrate_fine: bool = False,
):
    """
    Generates and stages the necessary coarse and fine resolution input images
    for the STARS data fusion process.

    This function iterates through the VIIRS date range, retrieving and saving
    coarse NDVI and albedo images. For dates within the HLS range, it also
    retrieves and saves fine NDVI and albedo images. It can optionally
    calibrate the fine images to the coarse images.

    Args:
        tile (str): The HLS tile ID.
        date_UTC (date): The target UTC date for the L2T_STARS product.
        HLS_start_date (date): The start date for HLS data retrieval for the fusion period.
        HLS_end_date (date): The end date for HLS data retrieval for the fusion period.
        VIIRS_start_date (date): The start date for VIIRS data retrieval for the fusion period.
        VIIRS_end_date (date): The end date for VIIRS data retrieval for the fusion period.
        NDVI_resolution (int): The resolution of the coarse NDVI data.
        albedo_resolution (int): The resolution of the coarse albedo data.
        target_resolution (int): The desired output resolution of the fused product.
        NDVI_coarse_geometry (RasterGeometry): The target geometry for coarse NDVI images.
        albedo_coarse_geometry (RasterGeometry): The target geometry for coarse albedo images.
        working_directory (str): The main working directory.
        NDVI_coarse_directory (str): Directory for staging coarse NDVI images.
        NDVI_fine_directory (str): Directory for staging fine NDVI images.
        albedo_coarse_directory (str): Directory for staging coarse albedo images.
        albedo_fine_directory (str): Directory for staging fine albedo images.
        HLS_connection (HLS2Connection): An initialized HLS data connection object.
        NDVI_VIIRS_connection (VIIRSDownloaderNDVI): An initialized VIIRS NDVI downloader.
        albedo_VIIRS_connection (VIIRSDownloaderAlbedo): An initialized VIIRS albedo downloader.
        calibrate_fine (bool, optional): If True, calibrate fine images to coarse images.
                                         Defaults to False.

    Raises:
        AuxiliaryLatency: If coarse VIIRS data is missing within the VIIRS_GIVEUP_DAYS window.
    """
    missing_coarse_dates = set()  # Track dates where coarse data could not be generated

    logger.info(f"preparing coarse and fine images for STARS at {cl.place(tile)}")

    # Process each day within the VIIRS data fusion window
    for processing_date in [
        get_date(dt) for dt in rrule(DAILY, dtstart=VIIRS_start_date, until=VIIRS_end_date)
    ]:
        NDVI_coarse_filename = generate_downsampled_filename(
            directory=downsampled_directory,
            variable="NDVI",
            date_UTC=processing_date,
            tile=tile,
            cell_size=NDVI_resolution
        )

        NDVI_fine_filename = generate_downsampled_filename(
            directory=downsampled_directory,
            variable="NDVI",
            date_UTC=processing_date,
            tile=tile,
            cell_size=target_resolution
        )

        albedo_coarse_filename = generate_downsampled_filename(
            directory=downsampled_directory,
            variable="albedo",
            date_UTC=processing_date,
            tile=tile,
            cell_size=albedo_resolution
        )

        albedo_fine_filename = generate_downsampled_filename(
            directory=downsampled_directory,
            variable="albedo",
            date_UTC=processing_date,
            tile=tile,
            cell_size=target_resolution
        )

        try:
            # Cache whether the NDVI coarse exists to avoid ToCToU
            NDVI_coarse_exists = exists(NDVI_coarse_filename)
            if not NDVI_coarse_exists:
                logger.info(f"preparing coarse image for STARS NDVI at {cl.place(tile)} on {cl.time(processing_date)}")

                NDVI_coarse_image = generate_NDVI_coarse_image(
                    date_UTC=processing_date,
                    VIIRS_connection=NDVI_VIIRS_connection,
                    geometry=NDVI_coarse_geometry
                )

                logger.info(
                    f"saving coarse image for STARS NDVI at {cl.place(tile)} on {cl.time(processing_date)}: {NDVI_coarse_filename}")
                NDVI_coarse_image.to_geotiff(NDVI_coarse_filename)

            if processing_date >= HLS_start_date:
                try:
                    if not exists(NDVI_fine_filename):
                        logger.info(
                            f"preparing fine image for STARS NDVI at {cl.place(tile)} on {cl.time(processing_date)}")

                        NDVI_fine_image = generate_NDVI_fine_image(
                            date_UTC=processing_date,
                            tile=tile,
                            HLS_connection=HLS_connection
                        )

                        if calibrate_fine:
                            # Ensure that the NDVI_coarse_image variable is set
                            if NDVI_coarse_exists:
                                NDVI_coarse_image = Raster.open(NDVI_coarse_filename)
                            logger.info(
                                f"calibrating fine image for STARS NDVI at {cl.place(tile)} on {cl.time(processing_date)}")
                            NDVI_fine_image = calibrate_fine_to_coarse(NDVI_fine_image, NDVI_coarse_image)

                        logger.info(
                            f"saving fine image for STARS NDVI at {cl.place(tile)} on {cl.time(processing_date)}: {NDVI_fine_filename}")
                        NDVI_fine_image.to_geotiff(NDVI_fine_filename)
                except Exception as e:
                    logger.warning(f"HLS NDVI is not available on {processing_date}: {e}")
                    logger.debug(f"Exception details: ", exc_info=True)
        except Exception as e:
            logger.exception(e)
            logger.warning(
                f"Unable to produce coarse NDVI for date {processing_date}"
            )
            missing_coarse_dates.add(processing_date)  # Add date to missing set

        try:
            # Cache whether the albedo coarse exists to avoid ToCToU
            albedo_coarse_exists = exists(albedo_coarse_filename)
            if not albedo_coarse_exists:
                logger.info(
                    f"preparing coarse image for STARS albedo at {cl.place(tile)} on {cl.time(processing_date)}")

                albedo_coarse_image = generate_albedo_coarse_image(
                    date_UTC=processing_date,
                    VIIRS_connection=albedo_VIIRS_connection,
                    geometry=albedo_coarse_geometry
                )

                logger.info(
                    f"saving coarse image for STARS albedo at {cl.place(tile)} on {cl.time(processing_date)}: {albedo_coarse_filename}")
                albedo_coarse_image.to_geotiff(albedo_coarse_filename)

            if processing_date >= HLS_start_date:
                try:
                    if not exists(albedo_fine_filename):
                        logger.info(
                            f"preparing fine image for STARS albedo at {cl.place(tile)} on {cl.time(processing_date)}")

                        albedo_fine_image = generate_albedo_fine_image(
                            date_UTC=processing_date,
                            tile=tile,
                            HLS_connection=HLS_connection
                        )

                        if calibrate_fine:
                            # Ensure that the albedo_coarse_image variable is set
                            if albedo_coarse_exists:
                                albedo_coarse_image = Raster.open(albedo_coarse_filename)

                            logger.info(
                                f"calibrating fine image for STARS albedo at {cl.place(tile)} on {cl.time(processing_date)}")
                            albedo_fine_image = calibrate_fine_to_coarse(albedo_fine_image, albedo_coarse_image)

                        logger.info(
                            f"saving fine image for STARS albedo at {cl.place(tile)} on {cl.time(processing_date)}: {albedo_fine_filename}")
                        albedo_fine_image.to_geotiff(albedo_fine_filename)
                except Exception as e:
                    logger.warning(f"HLS albedo is not available on {processing_date}: {e}")
                    logger.debug(f"Exception details: ", exc_info=True)
        except Exception as e:
            logger.exception(e)
            logger.warning(
                f"Unable to produce coarse albedo for date {processing_date}"
            )
            missing_coarse_dates.add(processing_date)  # Add date to missing set

    # We need to deal with the possibility that VIIRS has not yet published their data yet.
    #  VIIRS_GIVEUP_DAYS is the number of days before we assume that missing observations aren't coming.
    #  If any missing days are closer to now than VIIRS_GIVEUP_DAYS, we want to retry this run later, when VIIRS
    #  might have uploaded the missing observations. To cause this retry, we'll throw the `AncillaryLatency` exception.
    #  L2T_STARS converts this exception to an exit code, and the orchestration system marks this run
    #  as needing a retry at a later date.
    coarse_latency_dates = [
        d
        for d in missing_coarse_dates
        if (datetime.utcnow().date() - d).days <= VIIRS_GIVEUP_DAYS
    ]

    if len(coarse_latency_dates) > 0:
        raise AuxiliaryLatency(
            f"Missing coarse dates within {VIIRS_GIVEUP_DAYS}-day window: "
            f"{', '.join([str(d) for d in sorted(list(coarse_latency_dates))])}"
        )
