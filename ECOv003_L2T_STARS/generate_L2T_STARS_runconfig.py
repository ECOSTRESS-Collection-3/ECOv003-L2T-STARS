from typing import Union
from datetime import datetime, timezone
from os import makedirs
from os.path import join, abspath, exists, expanduser, dirname, basename
from glob import glob
import logging
from shutil import which
from uuid import uuid4
import socket

import colored_logging as cl
from pytictoc import TicToc  # Import pytictoc

from ECOv002_granules import L2TLSTE as ECOv002L2TLSTE

from ECOv003_granules import L2TLSTE
from ECOv003_granules import L2TSTARS

from .constants import *

logger = logging.getLogger(__name__)

def generate_L2T_STARS_runconfig(
    L2T_LSTE_filename: str,
    prior_L2T_STARS_filename: str = "",
    orbit: int = None,
    scene: int = None,
    tile: str = None,
    time_UTC: Union[datetime, str] = None,
    working_directory: str = None,
    sources_directory: str = None,
    indices_directory: str = None,
    model_directory: str = None,
    executable_filename: str = None,
    output_directory: str = None,
    runconfig_filename: str = None,
    log_filename: str = None,
    build: str = None,
    processing_node: str = None,
    production_datetime: datetime = None,
    job_ID: str = None,
    instance_ID: str = None,
    product_counter: int = None,
    template_filename: str = None,
) -> str:
    """
    Generates an XML run-configuration file for the L2T_STARS processing.

    This function dynamically creates an XML run-config file by populating a template
    with provided or default parameters. It also checks for and returns existing
    run-configs to prevent redundant generation.

    Args:
        L2T_LSTE_filename (str): Path to the input ECOSTRESS L2T LSTE granule file.
        prior_L2T_STARS_filename (str, optional): Path to a prior L2T_STARS product file.
            Defaults to "".
        orbit (int, optional): Orbit number. If None, derived from L2T_LSTE_filename.
        scene (int, optional): Scene ID. If None, derived from L2T_LSTE_filename.
        tile (str, optional): HLS tile ID (e.g., '11SPS'). If None, derived from L2T_LSTE_filename.
        time_UTC (Union[datetime, str], optional): UTC time of the L2T_LSTE granule. If None,
            derived from L2T_LSTE_filename.
        working_directory (str, optional): Root directory for all processing outputs.
            Defaults to ".".
        sources_directory (str, optional): Directory for downloaded source data (HLS, VIIRS).
        indices_directory (str, optional): Directory for intermediate index products.
        model_directory (str, optional): Directory for model state files (priors, posteriors).
        executable_filename (str, optional): Path to the L2T_STARS executable. If None,
            'L2T_STARS' is assumed to be in the system's PATH.
        output_directory (str, optional): Directory for final L2T_STARS products.
        runconfig_filename (str, optional): Specific filename for the generated run-config.
            If None, a default name based on granule ID is used.
        log_filename (str, optional): Specific filename for the log file. If None,
            a default name based on granule ID is used.
        build (str, optional): Build ID of the PGE. Defaults to DEFAULT_BUILD.
        processing_node (str, optional): Name of the processing node. Defaults to system hostname.
        production_datetime (datetime, optional): Production date and time. Defaults to now (UTC).
        job_ID (str, optional): Job identifier. Defaults to a timestamp.
        instance_ID (str, optional): Unique instance identifier. Defaults to a UUID.
        product_counter (int, optional): Counter for product generation. Defaults to 1.
        template_filename (str, optional): Path to the XML run-config template file.
            Defaults to L2T_STARS_TEMPLATE.

    Returns:
        str: The absolute path to the generated or existing run-configuration file.
    """
    timer = TicToc()  # Initialize pytictoc timer
    timer.tic()  # Start the timer

    # Determine collection from the L2T LSTE filename
    collection = basename(L2T_LSTE_filename).split("_")[0]
    
    if collection == "ECOv003":
        # Load the collection 3 L2T LSTE granule to extract necessary metadata if not provided
        L2T_LSTE_granule = L2TLSTE(L2T_LSTE_filename)
    elif collection == "ECOv002":
        # Load the collection 2 L2T LSTE granule to extract necessary metadata if not provided
        L2T_LSTE_granule = ECOv002L2TLSTE(L2T_LSTE_filename)
    else:
        raise ValueError(f"Unsupported collection in filename: {L2T_LSTE_filename}")

    # Use values from L2T_LSTE granule if not explicitly provided
    if orbit is None:
        orbit = L2T_LSTE_granule.orbit
    if scene is None:
        scene = L2T_LSTE_granule.scene
    if tile is None:
        tile = L2T_LSTE_granule.tile
    if time_UTC is None:
        time_UTC = L2T_LSTE_granule.time_UTC

    # Set default values for other parameters if not provided
    if build is None:
        build = BUILD
    if working_directory is None:
        working_directory = "."

    date_UTC = time_UTC.date()

    logger.info(
        f"Started generating L2T_STARS run-config for tile {cl.val(tile)} on date {cl.time(date_UTC)}"
    )

    # Check for previous run-configs to avoid re-generating
    pattern = join(
        working_directory, "runconfig", f"ECOv003_L2T_STARS_{tile}_*_*.xml"
    )
    logger.info(f"Scanning for previous run-configs: {cl.val(pattern)}")
    previous_runconfigs = glob(pattern)
    previous_runconfig_count = len(previous_runconfigs)

    if previous_runconfig_count > 0:
        logger.info(f"Found {cl.val(previous_runconfig_count)} previous run-configs")
        # Return the most recent run-config if found
        previous_runconfig = sorted(previous_runconfigs)[-1]
        logger.info(f"Previous run-config: {cl.file(previous_runconfig)}")
        return previous_runconfig

    # Resolve the path to the run-config template
    if template_filename is None:
        template_filename = L2T_STARS_TEMPLATE
    template_filename = abspath(expanduser(template_filename))

    # Set production datetime if not provided
    if production_datetime is None:
        production_datetime = datetime.now(timezone.utc)

    # Set product counter if not provided
    if product_counter is None:
        product_counter = 1

    # Format timestamp and generate granule ID
    granule_ID = L2TSTARS.generate_granule_name(
        orbit,
        scene,
        tile,
        time_UTC,
        process_count=product_counter,
    )

    # Define run-config filename and resolve absolute path
    if runconfig_filename is None:
        runconfig_filename = join(working_directory, "runconfig", f"{granule_ID}.xml")
    runconfig_filename = abspath(expanduser(runconfig_filename))

    # If the run-config file already exists, log and return its path
    if exists(runconfig_filename):
        logger.info(f"Run-config already exists {cl.file(runconfig_filename)}")
        return runconfig_filename

    # Resolve absolute paths for various directories if not already defined
    working_directory = abspath(expanduser(working_directory))
    if sources_directory is None:
        sources_directory = join(working_directory, STARS_SOURCES_DIRECTORY)
    if indices_directory is None:
        indices_directory = join(working_directory, STARS_INDICES_DIRECTORY)
    if model_directory is None:
        model_directory = join(working_directory, STARS_MODEL_DIRECTORY)

    # Determine executable path; fall back to just the name if not found in PATH
    if executable_filename is None:
        executable_filename = which("L2T_STARS")
    if executable_filename is None:
        executable_filename = "L2T_STARS"

    # Define output and log file paths
    if output_directory is None:
        output_directory = join(working_directory, OUTPUT_DIRECTORY)
    output_directory = abspath(expanduser(output_directory))
    if log_filename is None:
        log_filename = join(working_directory, "log", f"{granule_ID}.log")
    log_filename = abspath(expanduser(log_filename))

    # Get processing node hostname
    if processing_node is None:
        processing_node = socket.gethostname()

    # Set Job ID and Instance ID
    if job_ID is None:
        timestamp = f"{time_UTC:%Y%m%d}"
        job_ID = timestamp
    if instance_ID is None:
        instance_ID = str(uuid4())  # Generate a unique UUID for the instance

    # Resolve absolute path for the input L2T_LSTE file
    L2T_LSTE_filename = abspath(expanduser(L2T_LSTE_filename))

    logger.info(f"Loading L2T_STARS template: {cl.file(template_filename)}")

    # Read the XML template file content
    with open(template_filename, "r") as file:
        template = file.read()

    # Replace placeholders in the template with actual values
    logger.info(f"Orbit: {cl.val(orbit)}")
    template = template.replace("orbit_number", f"{orbit:05d}")
    logger.info(f"Scene: {cl.val(scene)}")
    template = template.replace("scene_ID", f"{scene:03d}")
    logger.info(f"Tile: {cl.val(tile)}")
    template = template.replace("tile_ID", f"{tile}")
    logger.info(f"L2T_LSTE file: {cl.file(L2T_LSTE_filename)}")
    template = template.replace("L2T_LSTE_filename", L2T_LSTE_filename)
    logger.info(f"Prior L2T_STARS file: {cl.file(prior_L2T_STARS_filename)}")
    template = template.replace("prior_L2T_STARS_filename", prior_L2T_STARS_filename)
    logger.info(f"Working directory: {cl.dir(working_directory)}")
    template = template.replace("working_directory", working_directory)
    logger.info(f"Sources directory: {cl.dir(sources_directory)}")
    template = template.replace("sources_directory", sources_directory)
    logger.info(f"Indices directory: {cl.dir(indices_directory)}")
    template = template.replace("indices_directory", indices_directory)
    logger.info(f"Model directory: {cl.dir(model_directory)}")
    template = template.replace("model_directory", model_directory)
    logger.info(f"Executable: {cl.file(executable_filename)}")
    template = template.replace("executable_filename", executable_filename)
    logger.info(f"Output directory: {cl.dir(output_directory)}")
    template = template.replace("output_directory", output_directory)
    logger.info(f"Run-config: {cl.file(runconfig_filename)}")
    template = template.replace("runconfig_filename", runconfig_filename)
    logger.info(f"Log: {cl.file(log_filename)}")
    template = template.replace("log_filename", log_filename)
    logger.info(f"Build: {cl.val(build)}")
    template = template.replace("build_ID", build)
    logger.info(f"Processing node: {cl.val(processing_node)}")
    template = template.replace("processing_node", processing_node)
    logger.info(f"Production date/time: {cl.time(production_datetime)}")
    template = template.replace("production_datetime", f"{production_datetime:%Y-%m-%dT%H:%M:%SZ}")
    logger.info(f"Job ID: {cl.val(job_ID)}")
    template = template.replace("job_ID", job_ID)
    logger.info(f"Instance ID: {cl.val(instance_ID)}")
    template = template.replace("instance_ID", instance_ID)
    logger.info(f"Product counter: {cl.val(product_counter)}")
    template = template.replace("product_counter", f"{product_counter:02d}")

    # Create the directory for the run-config file if it doesn't exist
    makedirs(dirname(abspath(runconfig_filename)), exist_ok=True)
    logger.info(f"Writing run-config file: {cl.file(runconfig_filename)}")

    # Write the populated template to the run-config file
    with open(runconfig_filename, "w") as file:
        file.write(template)

    logger.info(
        f"Finished generating L2T_STARS run-config for orbit {cl.val(orbit)} scene {cl.val(scene)} ({timer.tocvalue():.2f} seconds)"
    )

    return runconfig_filename
