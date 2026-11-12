import logging
import socket
import sys
from datetime import datetime
from os import makedirs
from os.path import join, abspath, dirname, expanduser, exists, splitext, basename
from shutil import which
from typing import List
from uuid import uuid4
from dateutil import parser
import colored_logging as cl
import argparse  # Import argparse for command-line argument parsing

from sentinel_tiles import SentinelTileGrid

from ECOv003_granules import L2TLSTE
from ECOv003_exit_codes import *

from .constants import *
from .generate_L2T_STARS_runconfig import generate_L2T_STARS_runconfig
from .runconfig import ECOSTRESSRunConfig, read_runconfig
from .L2T_STARS import L2T_STARS

from .version import __version__

# Configure the logger for the module
logger = logging.getLogger(__name__)

# Define the template for the ECOv003_DL run-config XML
ECOv003_DL_TEMPLATE = join(abspath(dirname(__file__)), "ECOv003_DL.xml")
# Default build ID
BUILD = "0700"

def generate_downloader_runconfig(
        L2G_LSTE_filename: str,
        L2T_LSTE_filenames: List[str],
        orbit: int = None,
        scene: int = None,
        working_directory: str = None,
        L2T_STARS_sources_directory: str = None,
        L2T_STARS_indices_directory: str = None,
        L2T_STARS_model_directory: str = None,
        executable_filename: str = None,
        runconfig_filename: str = None,
        log_filename: str = None,
        build: str = None,
        processing_node: str = None,
        production_datetime: datetime = None,
        job_ID: str = None,
        instance_ID: str = None,
        product_counter: int = None,
        template_filename: str = None) -> str:
    """
    Generates an ECOv003 Downloader run-config XML file.

    Args:
        L2G_LSTE_filename (str): Path to the L2G LSTE input file.
        L2T_LSTE_filenames (List[str]): List of paths to L2T LSTE input files.
        orbit (int, optional): Orbit number. Defaults to None, extracted from L2G filename.
        scene (int, optional): Scene ID. Defaults to None, extracted from L2G filename.
        working_directory (str, optional): Working directory for the PGE. Defaults to None,
                                           derived from run ID.
        L2T_STARS_sources_directory (str, optional): Directory for L2T STARS sources. Defaults to None,
                                                     derived from working directory.
        L2T_STARS_indices_directory (str, optional): Directory for L2T STARS indices. Defaults to None,
                                                     derived from working directory.
        L2T_STARS_model_directory (str, optional): Directory for L2T STARS model files. Defaults to None,
                                                   derived from working directory.
        executable_filename (str, optional): Path to the ECOv003_DL executable. Defaults to None,
                                             searches PATH or uses "ECOv003_DL".
        runconfig_filename (str, optional): Output run-config filename. Defaults to None,
                                            derived from working directory and run ID.
        log_filename (str, optional): Output log filename. Defaults to None,
                                      derived from working directory and run ID.
        build (str, optional): Build ID. Defaults to DEFAULT_BUILD.
        processing_node (str, optional): Name of the processing node. Defaults to current hostname.
        production_datetime (datetime, optional): Production date and time. Defaults to UTC now.
        job_ID (str, optional): Job ID. Defaults to production_datetime.
        instance_ID (str, optional): Instance ID. Defaults to a new UUID.
        product_counter (int, optional): Product counter. Defaults to 1.
        template_filename (str, optional): Path to the run-config XML template. Defaults to ECOv003_DL_TEMPLATE.

    Returns:
        str: The absolute path to the generated run-config XML file.

    Raises:
        IOError: If the L2G LSTE file is not found.
        ValueError: If no L2T LSTE filenames are provided.
    """
    # Resolve absolute path for L2G LSTE filename
    L2G_LSTE_filename = abspath(expanduser(L2G_LSTE_filename))

    # Check if L2G LSTE file exists
    if not exists(L2G_LSTE_filename):
        raise IOError(f"L2G LSTE file not found: {L2G_LSTE_filename}")

    logger.info(f"L2G LSTE file: {cl.file(L2G_LSTE_filename)}")
    # Extract source granule ID from L2G LSTE filename
    source_granule_ID = splitext(basename(L2G_LSTE_filename))[0]
    logger.info(f"source granule ID: {cl.name(source_granule_ID)}")

    # Determine orbit number
    if orbit is None:
        orbit = int(source_granule_ID.split("_")[-5])
    logger.info(f"orbit: {cl.val(orbit)}")

    # Determine scene ID
    if scene is None:
        scene = int(source_granule_ID.split("_")[-4])
    logger.info(f"scene: {cl.val(scene)}")

    # Set template filename
    if template_filename is None:
        template_filename = ECOv003_DL_TEMPLATE
    template_filename = abspath(expanduser(template_filename))

    # Generate run ID
    run_ID = f"ECOv003_DL_{orbit:05d}_{scene:05d}"

    # Determine working directory
    if working_directory is None:
        working_directory = run_ID
    working_directory = abspath(expanduser(working_directory))

    # Determine run-config filename
    if runconfig_filename is None:
        runconfig_filename = join(working_directory, "runconfig", f"{run_ID}.xml")
    runconfig_filename = abspath(expanduser(runconfig_filename))

    # Determine L2T STARS sources directory
    if L2T_STARS_sources_directory is None:
        L2T_STARS_sources_directory = join(working_directory, STARS_SOURCES_DIRECTORY)
    L2T_STARS_sources_directory = abspath(expanduser(L2T_STARS_sources_directory))

    # Determine L2T STARS indices directory
    if L2T_STARS_indices_directory is None:
        L2T_STARS_indices_directory = join(working_directory, STARS_INDICES_DIRECTORY)
    L2T_STARS_indices_directory = abspath(expanduser(L2T_STARS_indices_directory))

    # Determine L2T STARS model directory
    if L2T_STARS_model_directory is None:
        L2T_STARS_model_directory = join(working_directory, STARS_MODEL_DIRECTORY)
    L2T_STARS_model_directory = abspath(expanduser(L2T_STARS_model_directory))

    # Determine executable filename
    if executable_filename is None:
        executable_filename = which("ECOv003_DL")
    if executable_filename is None:
        executable_filename = "ECOv003_DL" # Fallback if not found in PATH

    # Determine log filename
    if log_filename is None:
        log_filename = join(working_directory, f"{run_ID}.log")
    log_filename = abspath(expanduser(log_filename))

    # Set build ID
    if build is None:
        build = BUILD

    # Set processing node
    if processing_node is None:
        processing_node = socket.gethostname()

    # Set production datetime
    if production_datetime is None:
        production_datetime = datetime.utcnow()
    # Convert datetime object to string if it's not already
    if isinstance(production_datetime, datetime):
        production_datetime = str(production_datetime)

    # Set job ID
    if job_ID is None:
        job_ID = production_datetime

    # Set instance ID
    if instance_ID is None:
        instance_ID = str(uuid4())

    # Set product counter
    if product_counter is None:
        product_counter = 1

    logger.info(f"generating run-config for orbit {cl.val(orbit)} scene {cl.val(scene)}")
    logger.info(f"loading ECOv003_DL template: {cl.file(template_filename)}")

    # Read the template file content
    with open(template_filename, "r") as file:
        template = file.read()

    # Replace placeholders in the template with actual values
    logger.info(f"orbit: {cl.val(orbit)}")
    template = template.replace("orbit_number", f"{orbit:05d}")
    logger.info(f"scene: {cl.val(scene)}")
    template = template.replace("scene_ID", f"{scene:03d}")

    # Ensure L2G_LSTE_filename is absolute
    L2G_LSTE_filename = abspath(expanduser(L2G_LSTE_filename))
    logger.info(f"L2G_LSTE file: {cl.file(L2G_LSTE_filename)}")
    template = template.replace("L2G_LSTE_filename", L2G_LSTE_filename)

    # Check if L2T LSTE filenames are provided
    if len(L2T_LSTE_filenames) == 0:
        raise ValueError(f"no L2T LSTE filenames given")

    logger.info(f"listing {len(L2T_LSTE_filenames)} L2T_LSTE files: ")

    # Format L2T LSTE filenames into XML elements
    L2T_LSTE_filenames_XML = "\n            ".join([
        f"<element>{abspath(expanduser(filename))}</element>"
        for filename
        in L2T_LSTE_filenames
    ])
    template = template.replace("<element>L2T_LSTE_filename1</element>", L2T_LSTE_filenames_XML)

    logger.info(f"working directory: {cl.dir(working_directory)}")
    template = template.replace("working_directory", working_directory)
    logger.info(f"L2T STARS sources directory: {cl.dir(L2T_STARS_sources_directory)}")
    template = template.replace("L2T_STARS_sources_directory", L2T_STARS_sources_directory)
    logger.info(f"L2T STARS indices directory: {cl.dir(L2T_STARS_indices_directory)}")
    template = template.replace("L2T_STARS_indices_directory", L2T_STARS_indices_directory)
    logger.info(f"L2T STARS model directory: {cl.dir(L2T_STARS_model_directory)}")
    template = template.replace("L2T_STARS_model_directory", L2T_STARS_model_directory)
    logger.info(f"executable: {cl.file(executable_filename)}")
    template = template.replace("executable_filename", executable_filename)
    logger.info(f"run-config: {cl.file(runconfig_filename)}")
    template = template.replace("runconfig_filename", runconfig_filename)
    logger.info(f"log: {cl.file(log_filename)}")
    template = template.replace("log_filename", log_filename)
    logger.info(f"build: {cl.val(build)}")
    template = template.replace("build_ID", build)
    logger.info(f"processing node: {cl.val(processing_node)}")
    template = template.replace("processing_node", processing_node)
    logger.info(f"production date/time: {cl.time(production_datetime)}")
    template = template.replace("production_datetime", production_datetime)
    logger.info(f"job ID: {cl.val(job_ID)}")
    template = template.replace("job_ID", job_ID)
    logger.info(f"instance ID: {cl.val(instance_ID)}")
    template = template.replace("instance_ID", instance_ID)
    logger.info(f"product counter: {cl.val(product_counter)}")
    template = template.replace("product_counter", f"{product_counter:02d}")

    # Create directory for the run-config file if it doesn't exist
    makedirs(dirname(abspath(runconfig_filename)), exist_ok=True)
    logger.info(f"writing run-config file: {cl.file(runconfig_filename)}")

    # Write the modified template to the run-config file
    with open(runconfig_filename, "w") as file:
        file.write(template)

    return runconfig_filename


class ECOv003DLConfig(ECOSTRESSRunConfig):
    """
    Parses and holds the configuration for the ECOv003 Downloader PGE from a run-config XML file.
    Inherits from ECOSTRESSRunConfig for common run-config parsing functionalities.
    """
    def __init__(self, filename: str):
        try:
            logger.info(f"loading ECOv003_DL run-config: {cl.file(filename)}")
            runconfig = read_runconfig(filename)

            # Validate and extract working directory
            if "StaticAncillaryFileGroup" not in runconfig:
                raise MissingRunConfigValue(f"missing StaticAncillaryFileGroup in ECOv003_DL run-config: {filename}")
            if "ECOv003_DL_WORKING" not in runconfig["StaticAncillaryFileGroup"]:
                raise MissingRunConfigValue(
                    f"missing StaticAncillaryFileGroup/ECOv003_DL_WORKING in ECOv003_DL run-config: {filename}")
            working_directory = abspath(runconfig["StaticAncillaryFileGroup"]["ECOv003_DL_WORKING"])
            logger.info(f"working directory: {cl.dir(working_directory)}")

            # Validate and extract L2T STARS sources directory
            if "L2T_STARS_SOURCES" not in runconfig["StaticAncillaryFileGroup"]:
                raise MissingRunConfigValue(
                    f"missing StaticAncillaryFileGroup/L2T_STARS_SOURCES in ECOv003_DL run-config: {filename}")
            L2T_STARS_sources_directory = abspath(runconfig["StaticAncillaryFileGroup"]["L2T_STARS_SOURCES"])
            logger.info(f"L2T STARS sources directory: {cl.dir(L2T_STARS_sources_directory)}")

            # Validate and extract L2T STARS indices directory
            if "L2T_STARS_INDICES" not in runconfig["StaticAncillaryFileGroup"]:
                raise MissingRunConfigValue(
                    f"missing StaticAncillaryFileGroup/L2T_STARS_INDICES in ECOv003_DL run-config: {filename}")
            L2T_STARS_indices_directory = abspath(runconfig["StaticAncillaryFileGroup"]["L2T_STARS_INDICES"])
            logger.info(f"L2T STARS indices directory: {cl.dir(L2T_STARS_indices_directory)}")

            # Validate and extract L2T STARS model directory
            if "L2T_STARS_MODEL" not in runconfig["StaticAncillaryFileGroup"]:
                raise MissingRunConfigValue(
                    f"missing StaticAncillaryFileGroup/L2T_STARS_MODEL in ECOv003_DL run-config: {filename}")
            L2T_STARS_model_directory = abspath(runconfig["StaticAncillaryFileGroup"]["L2T_STARS_MODEL"])
            logger.info(f"L2T STARS model directory: {cl.dir(L2T_STARS_model_directory)}")

            # Validate ProductPathGroup
            if "ProductPathGroup" not in runconfig:
                raise MissingRunConfigValue(f"missing ProductPathGroup in ECOv003_DL run-config: {filename}")

            # Validate and extract InputFileGroup and L2G_LSTE
            if "InputFileGroup" not in runconfig:
                raise MissingRunConfigValue(f"missing InputFileGroup in ECOv003_DL run-config: {filename}")
            if "L2G_LSTE" not in runconfig["InputFileGroup"]:
                raise MissingRunConfigValue(f"missing InputFileGroup/L2G_LSTE in ECOv003_DL run-config: {filename}")
            L2G_LSTE_filename = abspath(runconfig["InputFileGroup"]["L2G_LSTE"])
            logger.info(f"L2G_LSTE file: {cl.file(L2G_LSTE_filename)}")

            # Validate and extract L2T_LSTE filenames
            if "L2T_LSTE" not in runconfig["InputFileGroup"]:
                raise MissingRunConfigValue(
                    f"missing InputFileGroup/L2T_LSTE in ECOv003_DL run-config: {filename}")
            L2T_LSTE_filenames = runconfig["InputFileGroup"]["L2T_LSTE"]
            logger.info(f"reading {len(L2T_LSTE_filenames)} L2T_LSTE files")

            # Extract orbit and scene IDs
            orbit = int(runconfig["Geometry"]["OrbitNumber"])
            logger.info(f"orbit: {cl.val(orbit)}")
            if "SceneId" not in runconfig["Geometry"]:
                raise MissingRunConfigValue(f"missing Geometry/SceneId in L2T_STARS run-config: {filename}")
            scene = int(runconfig["Geometry"]["SceneId"])
            logger.info(f"scene: {cl.val(scene)}")

            # Extract build ID
            if "BuildID" not in runconfig["PrimaryExecutable"]:
                raise MissingRunConfigValue(
                    f"missing PrimaryExecutable/BuildID in L1_L2_RAD_LSTE run-config {filename}")
            build = str(runconfig["PrimaryExecutable"]["BuildID"])

            # Extract product counter
            if "ProductCounter" not in runconfig["ProductPathGroup"]:
                raise MissingRunConfigValue(
                    f"missing ProductPathGroup/ProductCounter in L1_L2_RAD_LSTE run-config {filename}")
            product_counter = int(runconfig["ProductPathGroup"]["ProductCounter"])

            # Determine UTC time from L2G LSTE filename (assuming a specific naming convention)
            time_UTC = parser.parse(basename(L2G_LSTE_filename).split("_")[-3])

            # Define PGE name and version
            PGE_name = "DOWNLOADER"
            PGE_version = __version__

            # Store extracted configuration values as attributes
            self.working_directory = working_directory
            self.L2G_LSTE_filename = L2G_LSTE_filename
            self.L2T_LSTE_filenames = L2T_LSTE_filenames
            self.L2T_STARS_sources_directory = L2T_STARS_sources_directory
            self.L2T_STARS_indices_directory = L2T_STARS_indices_directory
            self.L2T_STARS_model_directory = L2T_STARS_model_directory
            self.orbit = orbit
            self.scene = scene
            self.product_counter = product_counter
            self.time_UTC = time_UTC
            self.PGE_name = PGE_name
            self.PGE_version = PGE_version
        except MissingRunConfigValue as e:
            # Re-raise specific run-config value errors
            raise e
        except ECOSTRESSExitCodeException as e:
            # Re-raise specific ECOSTRESS exit code exceptions
            raise e
        except Exception as e:
            # Catch all other exceptions and wrap them in UnableToParseRunConfig
            logger.exception(e)
            raise UnableToParseRunConfig(f"unable to parse run-config file: {filename}")


def ECOv003_DL(runconfig_filename: str, tiles: List[str] = None) -> int:
    """
    ECOSTRESS Collection 3 Downloader PGE.
    This function orchestrates the download process for data required for L2T LSTE product generation.

    Args:
        runconfig_filename (str): Filename for the XML run-config.
        tiles (List[str], optional): A list of specific Sentinel tile IDs to process. If None, all tiles
                                     listed in the run-config will be considered. Defaults to None.

    Returns:
        int: An exit code indicating the success or failure of the operation.
    """
    exit_code = SUCCESS_EXIT_CODE

    # Configure colored logging for better readability in the console
    cl.configure()
    # Get logger for this function (redundant if already configured globally, but good practice)
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"ECOSTRESS Collection 2 Downloader PGE ({cl.val(__version__)})")
        logger.info(f"run-config: {cl.file(runconfig_filename)}")
        # Load and parse the run-config file
        runconfig = ECOv003DLConfig(runconfig_filename)

        # Extract parameters from the loaded run-config
        working_directory = runconfig.working_directory
        logger.info(f"working directory: {cl.dir(working_directory)}")
        L2T_STARS_sources_directory = runconfig.L2T_STARS_sources_directory
        logger.info(f"L2T STARS sources directory: {cl.dir(L2T_STARS_sources_directory)}")
        L2T_STARS_indices_directory = runconfig.L2T_STARS_indices_directory
        logger.info(f"L2T STARS indices directory: {cl.dir(L2T_STARS_indices_directory)}")
        L2T_STARS_model_directory = runconfig.L2T_STARS_model_directory
        logger.info(f"L2T STARS model directory: {cl.dir(L2T_STARS_model_directory)}")
        L2G_LSTE_filename = runconfig.L2G_LSTE_filename
        logger.info(f"L2G LSTE file: {cl.file(L2G_LSTE_filename)}")

        orbit = runconfig.orbit
        logger.info(f"orbit: {cl.val(orbit)}")
        scene = runconfig.scene
        logger.info(f"scene: {cl.val(scene)}")

        time_UTC = runconfig.time_UTC # Already parsed in ECOv003DLConfig

        L2T_LSTE_filenames = runconfig.L2T_LSTE_filenames
        logger.info(
            f"processing {cl.val(len(L2T_LSTE_filenames))} tiles for orbit {cl.val(orbit)} scene {cl.val(scene)}")

        # Iterate through each L2T LSTE filename (representing a tile)
        for L2T_LSTE_filename in L2T_LSTE_filenames:
            # Create an L2TLSTE granule object to extract tile information
            L2T_LSTE_granule = L2TLSTE(L2T_LSTE_filename)
            tile = L2T_LSTE_granule.tile
            # Initialize SentinelTileGrid to check if the tile is on land
            sentinel_tiles = SentinelTileGrid(target_resolution=70)

            # Check if the Sentinel tile is on land
            if not sentinel_tiles.land(tile):
                logger.warning(f"Sentinel tile {tile} is not on land. Skipping processing for this tile.")
                continue # Skip to the next tile

            # If specific tiles are provided via arguments, skip if current tile is not in the list
            if tiles is not None and tile not in tiles:
                logger.info(f"Skipping tile {tile} as it's not in the specified --tiles list.")
                continue

            logger.info(f"L2T LSTE filename: {cl.file(L2T_LSTE_filename)}")
            logger.info(f"orbit: {cl.val(orbit)} scene: {cl.val(scene)} tile: {cl.val(tile)}")

            # Generate the run-config for the L2T_STARS process for the current tile
            L2T_STARS_runconfig_filename = generate_L2T_STARS_runconfig(
                L2T_LSTE_filename=L2T_LSTE_filename,
                orbit=orbit,
                scene=scene,
                tile=tile,
                time_UTC=time_UTC,
                working_directory=working_directory,
                sources_directory=L2T_STARS_sources_directory,
                indices_directory=L2T_STARS_indices_directory,
                model_directory=L2T_STARS_model_directory
            )

            # Execute the L2T_STARS process (downloader mode)
            # The 'sources_only=True' argument indicates that this call is primarily for downloading
            # or preparing necessary source data for STARS, not full processing.
            exit_code = L2T_STARS(
                runconfig_filename=L2T_STARS_runconfig_filename,
                sources_only=True
            )

            # Handle specific exit codes from L2T_STARS
            if exit_code == LAND_FILTER:
                logger.warning(f"L2T_STARS reported that Sentinel tile {tile} is not on land. Skipping.")
                continue # Continue to the next tile if it's a land filter issue

            # If L2T_STARS failed for any other reason, return the error code immediately
            if exit_code != 0:
                logger.error(f"L2T_STARS failed for tile {tile} with exit code {exit_code}. Aborting.")
                return exit_code

    except ECOSTRESSExitCodeException as exception:
        # Catch and log specific ECOSTRESS exit code exceptions
        logger.exception(f"An ECOSTRESS specific error occurred: {exception}")
        exit_code = exception.exit_code

    return exit_code


def main(argv=sys.argv):
    """
    Main entry point for the ECOv003_DL PGE.
    Parses command-line arguments and initiates the downloader process.
    """
    # Configure colored logging for the main function
    cl.configure()
    # Get logger for the main function
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(
        description=f"ECOSTRESS Collection 2 Downloader PGE ({__version__}).",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "runconfig_filename",
        type=str,
        help="Path to the XML run-config file for ECOv003_DL."
    )
    parser.add_argument(
        "--tiles",
        nargs='*', # 0 or more arguments
        default=None,
        help="Optional: Space-separated list of specific Sentinel tile IDs (e.g., '30SWJ 30SXJ') "
             "to process. If not provided, all tiles in the run-config will be processed."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit."
    )

    args = parser.parse_args(argv[1:]) # Parse arguments starting from the second element (skip script name)

    # Validate that the runconfig file exists
    if not exists(args.runconfig_filename):
        logger.error(f"Run-config file not found: {cl.file(args.runconfig_filename)}")
        return RUNCONFIG_FILENAME_NOT_SUPPLIED

    logger.info(f"Starting ECOSTRESS Collection 2 Downloader PGE ({cl.val(__version__)})")
    # Call the core ECOv003_DL function with parsed arguments
    exit_code = ECOv003_DL(runconfig_filename=args.runconfig_filename, tiles=args.tiles)
    logger.info(f"ECOSTRESS Collection 2 Downloader PGE finished with exit code: {cl.val(exit_code)}")

    return exit_code


if __name__ == "__main__":
    # Entry point when the script is executed directly
    sys.exit(main(argv=sys.argv))
