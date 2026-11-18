import logging
import shutil
from datetime import datetime, date
from os import remove
from os.path import basename, exists
from typing import Literal, Union

import colored_logging as cl
from rasters import Raster

from harmonized_landsat_sentinel import HLS2Connection

from ECOv003_granules import L2TSTARS, NDVI_COLORMAP, ALBEDO_COLORMAP
from ECOv003_exit_codes import BlankOutput
from VCD43NRT import VCD43NRT

from .constants import *
from .generate_model_state_tile_date_directory import generate_model_state_tile_date_directory
from .generate_STARS_inputs import generate_STARS_inputs
from .generate_filename import generate_filename
from .process_rust_data_fusion import process_rust_data_fusion

from .prior import Prior

logger = logging.getLogger(__name__)


def _run_data_fusion(
    backend: Literal["rust", "julia"],
    *,
    tile: str,
    coarse_cell_size: int,
    fine_cell_size: int,
    VIIRS_start_date: date,
    VIIRS_end_date: date,
    HLS_start_date: date,
    HLS_end_date: date,
    downsampled_directory: str,
    product_name: str,
    posterior_filename: str,
    posterior_UQ_filename: str,
    posterior_flag_filename: str,
    posterior_bias_filename: str,
    posterior_bias_UQ_filename: str,
    prior_filename: str = None,
    prior_UQ_filename: str = None,
    prior_bias_filename: str = None,
    prior_bias_UQ_filename: str = None,
    initialize_julia: bool = False,
    threads: Union[int, str] = "auto",
    num_workers: int = 4,
) -> None:
    """Dispatch STARS data fusion to the selected backend ('rust' default or legacy 'julia')."""
    if backend == "rust":
        process_rust_data_fusion(
            tile=tile,
            coarse_cell_size=coarse_cell_size,
            fine_cell_size=fine_cell_size,
            VIIRS_start_date=VIIRS_start_date,
            VIIRS_end_date=VIIRS_end_date,
            HLS_start_date=HLS_start_date,
            HLS_end_date=HLS_end_date,
            downsampled_directory=downsampled_directory,
            product_name=product_name,
            posterior_filename=posterior_filename,
            posterior_UQ_filename=posterior_UQ_filename,
            posterior_flag_filename=posterior_flag_filename,
            posterior_bias_filename=posterior_bias_filename,
            posterior_bias_UQ_filename=posterior_bias_UQ_filename,
            prior_filename=prior_filename,
            prior_UQ_filename=prior_UQ_filename,
            prior_bias_filename=prior_bias_filename,
            prior_bias_UQ_filename=prior_bias_UQ_filename,
            num_workers=num_workers,
        )
    elif backend == "julia":
        from .process_julia_data_fusion import process_julia_data_fusion

        process_julia_data_fusion(
            tile=tile,
            coarse_cell_size=coarse_cell_size,
            fine_cell_size=fine_cell_size,
            VIIRS_start_date=VIIRS_start_date,
            VIIRS_end_date=VIIRS_end_date,
            HLS_start_date=HLS_start_date,
            HLS_end_date=HLS_end_date,
            downsampled_directory=downsampled_directory,
            product_name=product_name,
            posterior_filename=posterior_filename,
            posterior_UQ_filename=posterior_UQ_filename,
            posterior_flag_filename=posterior_flag_filename,
            posterior_bias_filename=posterior_bias_filename,
            posterior_bias_UQ_filename=posterior_bias_UQ_filename,
            prior_filename=prior_filename,
            prior_UQ_filename=prior_UQ_filename,
            prior_bias_filename=prior_bias_filename,
            prior_bias_UQ_filename=prior_bias_UQ_filename,
            initialize_julia=initialize_julia,
            threads=threads,
            num_workers=num_workers,
        )
    else:
        raise ValueError(f"Unsupported STARS fusion backend: {backend!r} (expected 'rust' or 'julia')")


def copy_prior_to_posterior(
    posterior_filename: str,
    posterior_UQ_filename: str,
    posterior_flag_filename: str,
    posterior_bias_filename: str,
    posterior_bias_UQ_filename: str,
    prior_filename: str,
    prior_UQ_filename: str,
    prior_flag_filename: str,
    prior_bias_filename: str,
    prior_bias_UQ_filename: str,
):
    """Helper function to assist with creating nearly-identical STARS granules"""
    pairings = [
        (posterior_filename, prior_filename),
        (posterior_UQ_filename, prior_UQ_filename),
        (posterior_flag_filename, prior_flag_filename),
        (posterior_bias_filename, prior_bias_filename),
        (posterior_bias_UQ_filename, prior_bias_UQ_filename),
    ]

    for posterior, prior in pairings:
        image = Raster.open(prior)
        image.to_geotiff(posterior, use_compression=False, include_preview=False)


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
    downsampled_directory: str,
    model_directory: str,
    input_staging_directory: str,
    L2T_STARS_granule_directory: str,
    L2T_STARS_zip_filename: str,
    L2T_STARS_browse_filename: str,
    metadata: dict,
    prior: Prior,
    HLS_connection: HLS2Connection,
    NDVI_VCD43NRT_connection: VCD43NRT,
    albedo_VCD43NRT_connection: VCD43NRT,
    using_prior: bool = False,
    calibrate_fine: bool = False,
    remove_input_staging: bool = True,
    remove_prior: bool = REMOVE_PRIOR,
    remove_posterior: bool = REMOVE_POSTERIOR,
    backend: Literal["rust", "julia"] = FUSION_BACKEND,
    initialize_julia: bool = False,
    threads: Union[int, str] = "auto",
    num_workers: int = 4,
):
    """
    Orchestrates the generation of the L2T_STARS product for a given tile and date.
    """
    if backend not in ("rust", "julia"):
        raise ValueError(f"Unsupported STARS fusion backend: {backend!r} (expected 'rust' or 'julia')")

    # Get the target geometries for coarse NDVI and albedo based on the HLS grid
    NDVI_coarse_geometry = HLS_connection.grid(tile=tile, cell_size=NDVI_resolution)
    albedo_coarse_geometry = HLS_connection.grid(tile=tile, cell_size=albedo_resolution)

    logger.info(
        f"Processing the L2T_STARS product at tile {cl.place(tile)} for date {cl.time(date_UTC)} "
        f"(backend={cl.val(backend)})"
    )

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
        downsampled_directory=downsampled_directory,
        HLS_connection=HLS_connection,
        NDVI_VCD43NRT_connection=NDVI_VCD43NRT_connection,
        albedo_VCD43NRT_connection=albedo_VCD43NRT_connection,
        calibrate_fine=calibrate_fine,
    )

    # --- Process NDVI Data Fusion ---
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

    # Run STARS data fusion for NDVI, conditionally including prior data
    if using_prior:
        if prior.prior_date_UTC == date_UTC:
            copy_prior_to_posterior(
                posterior_filename=posterior_NDVI_filename,
                posterior_UQ_filename=posterior_NDVI_UQ_filename,
                posterior_flag_filename=posterior_NDVI_flag_filename,
                posterior_bias_filename=posterior_NDVI_bias_filename,
                posterior_bias_UQ_filename=posterior_NDVI_bias_UQ_filename,
                prior_filename=prior.prior_NDVI_filename,
                prior_UQ_filename=prior.prior_NDVI_UQ_filename,
                prior_flag_filename=prior.prior_NDVI_flag_filename,
                prior_bias_filename=prior.prior_NDVI_bias_filename,
                prior_bias_UQ_filename=prior.prior_NDVI_bias_UQ_filename,
            )
        else:
            logger.info(f"Running {backend} data fusion for NDVI with prior data.")
            _run_data_fusion(
                backend,
                tile=tile,
                coarse_cell_size=NDVI_resolution,
                fine_cell_size=target_resolution,
                VIIRS_start_date=VIIRS_start_date,
                VIIRS_end_date=VIIRS_end_date,
                HLS_start_date=HLS_start_date,
                HLS_end_date=HLS_end_date,
                downsampled_directory=downsampled_directory,
                product_name="NDVI",
                posterior_filename=posterior_NDVI_filename,
                posterior_UQ_filename=posterior_NDVI_UQ_filename,
                posterior_flag_filename=posterior_NDVI_flag_filename,
                posterior_bias_filename=posterior_NDVI_bias_filename,
                posterior_bias_UQ_filename=posterior_NDVI_bias_UQ_filename,
                prior_filename=prior.prior_NDVI_filename,
                prior_UQ_filename=prior.prior_NDVI_UQ_filename,
                prior_bias_filename=prior.prior_NDVI_bias_filename,
                prior_bias_UQ_filename=prior.prior_NDVI_bias_UQ_filename,
                initialize_julia=initialize_julia,
                threads=threads,
                num_workers=num_workers,
            )
    else:
        logger.info(f"Running {backend} data fusion for NDVI without prior data.")
        _run_data_fusion(
            backend,
            tile=tile,
            coarse_cell_size=NDVI_resolution,
            fine_cell_size=target_resolution,
            VIIRS_start_date=VIIRS_start_date,
            VIIRS_end_date=VIIRS_end_date,
            HLS_start_date=HLS_start_date,
            HLS_end_date=HLS_end_date,
            downsampled_directory=downsampled_directory,
            product_name="NDVI",
            posterior_filename=posterior_NDVI_filename,
            posterior_UQ_filename=posterior_NDVI_UQ_filename,
            posterior_flag_filename=posterior_NDVI_flag_filename,
            posterior_bias_filename=posterior_NDVI_bias_filename,
            posterior_bias_UQ_filename=posterior_NDVI_bias_UQ_filename,
            initialize_julia=initialize_julia,
            threads=threads,
            num_workers=num_workers,
        )

    for filename in [
        posterior_NDVI_filename,
        posterior_NDVI_UQ_filename,
        posterior_NDVI_flag_filename,
        posterior_NDVI_bias_filename,
        posterior_NDVI_bias_UQ_filename,
    ]:
        if not exists(filename):
            raise BlankOutput(f"Posterior NDVI raster file not found: {filename}")

    # Open the resulting NDVI rasters
    NDVI = Raster.open(posterior_NDVI_filename)
    NDVI_UQ = Raster.open(posterior_NDVI_UQ_filename)
    NDVI_bias = Raster.open(posterior_NDVI_bias_filename)
    NDVI_bias_UQ = Raster.open(posterior_NDVI_bias_UQ_filename)
    NDVI_flag = Raster.open(posterior_NDVI_flag_filename)

    # --- Process Albedo Data Fusion ---
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

    # Run STARS data fusion for albedo, conditionally including prior data
    if using_prior:
        if prior.prior_date_UTC == date_UTC:
            copy_prior_to_posterior(
                posterior_filename=posterior_albedo_filename,
                posterior_UQ_filename=posterior_albedo_UQ_filename,
                posterior_flag_filename=posterior_albedo_flag_filename,
                posterior_bias_filename=posterior_albedo_bias_filename,
                posterior_bias_UQ_filename=posterior_albedo_bias_UQ_filename,
                prior_filename=prior.prior_albedo_filename,
                prior_UQ_filename=prior.prior_albedo_UQ_filename,
                prior_flag_filename=prior.prior_albedo_flag_filename,
                prior_bias_filename=prior.prior_albedo_bias_filename,
                prior_bias_UQ_filename=prior.prior_albedo_bias_UQ_filename,
            )
        else:
            logger.info(f"Running {backend} data fusion for albedo with prior data.")
            _run_data_fusion(
                backend,
                tile=tile,
                coarse_cell_size=albedo_resolution,
                fine_cell_size=target_resolution,
                VIIRS_start_date=VIIRS_start_date,
                VIIRS_end_date=VIIRS_end_date,
                HLS_start_date=HLS_start_date,
                HLS_end_date=HLS_end_date,
                downsampled_directory=downsampled_directory,
                product_name="albedo",
                posterior_filename=posterior_albedo_filename,
                posterior_UQ_filename=posterior_albedo_UQ_filename,
                posterior_flag_filename=posterior_albedo_flag_filename,
                posterior_bias_filename=posterior_albedo_bias_filename,
                posterior_bias_UQ_filename=posterior_albedo_bias_UQ_filename,
                prior_filename=prior.prior_albedo_filename,
                prior_UQ_filename=prior.prior_albedo_UQ_filename,
                prior_bias_filename=prior.prior_albedo_bias_filename,
                prior_bias_UQ_filename=prior.prior_albedo_bias_UQ_filename,
                initialize_julia=initialize_julia,
                threads=threads,
                num_workers=num_workers,
            )
    else:
        logger.info(f"Running {backend} data fusion for albedo without prior data.")
        _run_data_fusion(
            backend,
            tile=tile,
            coarse_cell_size=albedo_resolution,
            fine_cell_size=target_resolution,
            VIIRS_start_date=VIIRS_start_date,
            VIIRS_end_date=VIIRS_end_date,
            HLS_start_date=HLS_start_date,
            HLS_end_date=HLS_end_date,
            downsampled_directory=downsampled_directory,
            product_name="albedo",
            posterior_filename=posterior_albedo_filename,
            posterior_UQ_filename=posterior_albedo_UQ_filename,
            posterior_flag_filename=posterior_albedo_flag_filename,
            posterior_bias_filename=posterior_albedo_bias_filename,
            posterior_bias_UQ_filename=posterior_albedo_bias_UQ_filename,
            initialize_julia=initialize_julia,
            threads=threads,
            num_workers=num_workers,
        )

    for filename in [
        posterior_albedo_filename,
        posterior_albedo_UQ_filename,
        posterior_albedo_flag_filename,
        posterior_albedo_bias_filename,
        posterior_albedo_bias_UQ_filename,
    ]:
        if not exists(filename):
            raise BlankOutput(f"Posterior albedo raster file not found: {filename}")

    # Open the resulting albedo rasters
    albedo = Raster.open(posterior_albedo_filename)
    albedo_UQ = Raster.open(posterior_albedo_UQ_filename)
    albedo_bias = Raster.open(posterior_albedo_bias_filename)
    albedo_bias_UQ = Raster.open(posterior_albedo_bias_UQ_filename)
    albedo_flag = Raster.open(posterior_albedo_flag_filename)

    # --- Validate Output and Create Final Product ---
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
    granule.add_layer("NDVI-bias", NDVI_bias, cmap="viridis")
    granule.add_layer("NDVI-bias-UQ", NDVI_bias_UQ, cmap="viridis")
    granule.add_layer("NDVI-flag", NDVI_flag, cmap="jet")
    granule.add_layer("albedo", albedo, cmap=ALBEDO_COLORMAP)
    granule.add_layer("albedo-UQ", albedo_UQ, cmap="jet")
    granule.add_layer("albedo-bias", albedo_bias, cmap="viridis")
    granule.add_layer("albedo-bias-UQ", albedo_bias_UQ, cmap="viridis")
    granule.add_layer("albedo-flag", albedo_flag, cmap="jet")

    # Update metadata and write to the granule
    metadata["StandardMetadata"]["BuildID"] = build
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

    if not exists(L2T_STARS_browse_filename):
        logger.info(
            f"Browse image not found after initial creation attempt. Regenerating: {cl.file(L2T_STARS_browse_filename)}"
        )
        granule_for_browse = L2TSTARS(L2T_STARS_zip_filename)
        granule_for_browse.write_browse_image(PNG_filename=L2T_STARS_browse_filename)

    # Re-write posterior files to ensure consistent compression/colormaps
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
            shutil.rmtree(input_staging_directory, ignore_errors=True)

    if using_prior and remove_prior:
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
