import subprocess
from typing import Union
from datetime import date
from os.path import abspath, dirname, join, exists
import os
import logging

from .instantiate_STARSDataFusion_jl import instantiate_STARSDataFusion_jl

logger = logging.getLogger(__name__)

def process_julia_data_fusion(
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
        environment_name: str = "@ECOv003-L2T-STARS",  # Unused in current Julia command, but kept for consistency
        initialize_julia: bool = False,
        threads: Union[int, str] = "auto",
        num_workers: int = 4):
    """
    Executes the Julia-based data fusion process for NDVI or albedo.

    This function prepares and runs a Julia script that performs the core
    STARS data fusion. It passes all necessary input and output paths,
    date ranges, and resolution parameters to the Julia script. Optionally,
    it can also pass prior information to the Julia system.

    Args:
        tile (str): The HLS tile ID.
        coarse_cell_size (int): The cell size of the coarse resolution data (e.g., VIIRS).
        fine_cell_size (int): The cell size of the fine resolution data (e.g., HLS and target).
        VIIRS_start_date (date): Start date for VIIRS data processing.
        VIIRS_end_date (date): End date for VIIRS data processing.
        HLS_start_date (date): Start date for HLS data processing.
        HLS_end_date (date): End date for HLS data processing.
        downsampled_directory (str): Directory containing coarse and fine downsampled data.
        product_name (str): Name of the product, e.g. "NDVI" or "albedo"
        posterior_filename (str): Output path for the fused posterior mean image.
        posterior_UQ_filename (str): Output path for the fused posterior uncertainty image.
        posterior_flag_filename (str): Output path for the fused posterior flag image.
        posterior_bias_filename (str): Output path for the fused posterior bias image.
        posterior_bias_UQ_filename (str): Output path for the fused posterior bias uncertainty image.
        prior_filename (str, optional): Path to the prior mean image. Defaults to None.
        prior_UQ_filename (str, optional): Path to the prior uncertainty image. Defaults to None.
        prior_bias_filename (str, optional): Path to the prior bias image. Defaults to None.
        prior_bias_UQ_filename (str, optional): Path to the prior bias uncertainty image. Defaults to None.
        environment_name (str, optional): Julia environment name. Defaults to "@ECOv003-L2T-STARS".
        threads (Union[int, str], optional): Number of Julia threads to use, or "auto".
                                            Defaults to "auto".
        num_workers (int, optional): Number of Julia workers for distributed processing.
                                     Defaults to 4.
    """
    # Construct the path to the Julia processing script
    julia_script_filename = join(
        abspath(dirname(__file__)), "process_ECOSTRESS_data_fusion_distributed_bias.jl"
    )
    # The directory where the Julia Project.toml is located
    STARS_source_directory = abspath(dirname(__file__))

    # Instantiate Julia dependencies
    if initialize_julia:
        instantiate_STARSDataFusion_jl(STARS_source_directory)

    # Set up the environment for the julia script
    julia_env = os.environ.copy()
    julia_env["JULIA_NUM_THREADS"] = str(threads)
    # Ensure that julia uses its own bundled GDAL instead of conda's GDAL
    julia_env.pop("GDAL_DATA", None)
    julia_env.pop("GDAL_DRIVER_PATH", None)

    # Base Julia command with required arguments
    command = [
        "julia", "--threads", f"{threads}", julia_script_filename,
        f"{num_workers}",
        tile,
        f"{coarse_cell_size}", f"{fine_cell_size}",
        f"{VIIRS_start_date}", f"{VIIRS_end_date}",
        f"{HLS_start_date}", f"{HLS_end_date}",
        downsampled_directory, product_name,
        posterior_filename, posterior_UQ_filename,
        posterior_flag_filename,
        posterior_bias_filename, posterior_bias_UQ_filename,
    ]

    # Conditionally add prior arguments if all prior filenames are provided and exist
    if all(
        [
            filename is not None and exists(filename)
            for filename in [
                prior_filename,
                prior_UQ_filename,
                prior_bias_filename,
                prior_bias_UQ_filename,
            ]
        ]
    ):
        logger.info("Passing prior into Julia data fusion system")
        command += [
            prior_filename, prior_UQ_filename,
            prior_bias_filename, prior_bias_UQ_filename,
        ]
    else:
        logger.info("No complete prior set found; running Julia data fusion without prior.")

    logger.info(f"Executing Julia command: {' '.join(command)}")
    # Execute the Julia command, adding the environment changes
    # This assumes the Julia executable is in the system's PATH.
    subprocess.run(command, check=False, env=julia_env)
