from os.path import abspath, exists, expanduser
import logging

from dateutil import parser

import colored_logging as cl

from ECOv003_exit_codes import *
from ECOv003_granules import L2TLSTE
from ECOv003_granules import L2TSTARS

from .constants import *
from .runconfig import ECOSTRESSRunConfig

logger = logging.getLogger(__name__)

class L2TSTARSConfig(ECOSTRESSRunConfig):
    """
    Parses and validates the L2T_STARS specific parameters from an XML run-configuration file.

    This class extends the base ECOSTRESSRunConfig to extract paths, IDs,
    and processing parameters relevant to the L2T_STARS product generation.
    It performs validation to ensure all critical parameters are present.
    """

    def __init__(self, filename: str):
        """
        Initializes the L2TSTARSConfig by parsing the provided run-config XML file.

        Args:
            filename (str): The path to the L2T_STARS run-configuration XML file.

        Raises:
            MissingRunConfigValue: If a required value is missing from the run-config.
            UnableToParseRunConfig: If the run-config file cannot be parsed due to other errors.
        """
        logger.info(f"Loading L2T_STARS run-config: {cl.file(filename)}")
        # Read the run-config XML into a dictionary
        runconfig = self.read_runconfig(filename)

        # reverting to StaticAncillaryFileGroup for now instead of StaticAuxiliaryFileGroup

        try:
            # Validate and extract working directory from StaticAncillaryFileGroup
            if "StaticAncillaryFileGroup" not in runconfig:
                raise MissingRunConfigValue(
                    f"Missing StaticAncillaryFileGroup in L2T_STARS run-config: {filename}"
                )
            if "L2T_STARS_WORKING" not in runconfig["StaticAncillaryFileGroup"]:
                raise MissingRunConfigValue(
                    f"Missing StaticAncillaryFileGroup/L2T_STARS_WORKING in L2T_STARS run-config: {filename}"
                )
            self.working_directory = abspath(
                runconfig["StaticAncillaryFileGroup"]["L2T_STARS_WORKING"]
            )
            logger.info(f"Working directory: {cl.dir(self.working_directory)}")

            # Validate and extract sources directory
            if "L2T_STARS_SOURCES" not in runconfig["StaticAncillaryFileGroup"]:
                raise MissingRunConfigValue(
                    f"Missing StaticAncillaryFileGroup/L2T_STARS_SOURCES in L2T_STARS run-config: {filename}"
                )
            self.sources_directory = abspath(
                runconfig["StaticAncillaryFileGroup"]["L2T_STARS_SOURCES"]
            )
            logger.info(f"Sources directory: {cl.dir(self.sources_directory)}")

            # Validate and extract indices directory
            if "L2T_STARS_INDICES" not in runconfig["StaticAncillaryFileGroup"]:
                raise MissingRunConfigValue(
                    f"Missing StaticAncillaryFileGroup/L2T_STARS_INDICES in L2T_STARS run-config: {filename}"
                )
            self.indices_directory = abspath(
                runconfig["StaticAncillaryFileGroup"]["L2T_STARS_INDICES"]
            )
            logger.info(f"Indices directory: {cl.dir(self.indices_directory)}")

            # Validate and extract model directory
            if "L2T_STARS_MODEL" not in runconfig["StaticAncillaryFileGroup"]:
                raise MissingRunConfigValue(
                    f"Missing StaticAncillaryFileGroup/L2T_STARS_MODEL in L2T_STARS run-config: {filename}"
                )
            self.model_directory = abspath(
                runconfig["StaticAncillaryFileGroup"]["L2T_STARS_MODEL"]
            )
            logger.info(f"Model directory: {cl.dir(self.model_directory)}")

            # Validate and extract output directory from ProductPathGroup
            if "ProductPathGroup" not in runconfig:
                raise MissingRunConfigValue(
                    f"Missing ProductPathGroup in L2T_STARS run-config: {filename}"
                )
            if "ProductPath" not in runconfig["ProductPathGroup"]:
                raise MissingRunConfigValue(
                    f"Missing ProductPathGroup/ProductPath in L2T_STARS run-config: {filename}"
                )
            self.output_directory = abspath(
                runconfig["ProductPathGroup"]["ProductPath"]
            )
            logger.info(f"Output directory: {cl.dir(self.output_directory)}")

            # Validate and extract input L2T_LSTE filename
            if "InputFileGroup" not in runconfig:
                raise MissingRunConfigValue(
                    f"Missing InputFileGroup in L2G_L2T_LSTE run-config: {filename}"
                )
            if "L2T_LSTE" not in runconfig["InputFileGroup"]:
                raise MissingRunConfigValue(
                    f"Missing InputFileGroup/L2T_LSTE in L2T_STARS run-config: {filename}"
                )
            self.L2T_LSTE_filename = abspath(runconfig["InputFileGroup"]["L2T_LSTE"])
            logger.info(f"L2T_LSTE file: {cl.file(self.L2T_LSTE_filename)}")

            # Extract optional prior L2T_STARS filename
            self.L2T_STARS_prior_filename = None
            if "L2T_STARS_PRIOR" in runconfig["InputFileGroup"]:
                prior_filename = runconfig["InputFileGroup"]["L2T_STARS_PRIOR"]
                if prior_filename:
                    prior_filename = abspath(expanduser(prior_filename))
                    if exists(prior_filename):
                        self.L2T_STARS_prior_filename = prior_filename
                    else:
                        logger.warning(f"L2T_STARS prior file not found: {prior_filename}")
                logger.info(
                    f"L2T_STARS prior file: {cl.file(self.L2T_STARS_prior_filename)}"
                )

            # Extract geometry parameters (orbit, scene, tile)
            self.orbit = int(runconfig["Geometry"]["OrbitNumber"])
            logger.info(f"Orbit: {cl.val(self.orbit)}")
            if "SceneId" not in runconfig["Geometry"]:
                raise MissingRunConfigValue(
                    f"Missing Geometry/SceneId in L2T_STARS run-config: {filename}"
                )
            self.scene = int(runconfig["Geometry"]["SceneId"])
            logger.info(f"Scene: {cl.val(self.scene)}")
            if "TileId" not in runconfig["Geometry"]:
                raise MissingRunConfigValue(
                    f"Missing Geometry/TileId in L2T_STARS run-config: {filename}"
                )
            self.tile = str(runconfig["Geometry"]["TileId"])
            logger.info(f"Tile: {cl.val(self.tile)}")

            # Extract production details
            if "ProductionDateTime" not in runconfig["JobIdentification"]:
                raise MissingRunConfigValue(
                    f"Missing JobIdentification/ProductionDateTime in L2T_STARS run-config {filename}"
                )
            self.production_datetime = parser.parse(
                runconfig["JobIdentification"]["ProductionDateTime"]
            )
            logger.info(f"Production time: {cl.time(self.production_datetime)}")

            # Extract build ID
            if "BuildID" not in runconfig["PrimaryExecutable"]:
                raise MissingRunConfigValue(
                    f"Missing PrimaryExecutable/BuildID in L2T_STARS run-config {filename}"
                )
            self.build = str(runconfig["PrimaryExecutable"]["BuildID"])

            # Extract product counter
            if "ProductCounter" not in runconfig["ProductPathGroup"]:
                raise MissingRunConfigValue(
                    f"Missing ProductPathGroup/ProductCounter in L2T_STARS run-config {filename}"
                )
            self.product_counter = int(runconfig["ProductPathGroup"]["ProductCounter"])

            # Get UTC time from the L2T_LSTE granule itself
            l2t_lste_granule_obj = L2TLSTE(self.L2T_LSTE_filename)
            time_UTC = l2t_lste_granule_obj.time_UTC

            # Construct the full granule ID and paths for the output product
            granule_ID = L2TSTARS.generate_granule_name(
                self.orbit,
                self.scene,
                self.tile,
                time_UTC,
                self.product_counter
            )
            self.granule_ID = granule_ID
            self.L2T_STARS_granule_directory = join(self.output_directory, granule_ID)
            self.L2T_STARS_zip_filename = f"{self.L2T_STARS_granule_directory}.zip"
            self.L2T_STARS_browse_filename = (
                f"{self.L2T_STARS_granule_directory}.png"
            )

        except MissingRunConfigValue as e:
            # Re-raise specific missing value errors
            raise e
        except ECOSTRESSExitCodeException as e:
            # Re-raise custom ECOSTRESS exit code exceptions
            raise e
        except Exception as e:
            # Catch any other parsing errors and raise a generic UnableToParseRunConfig
            logger.exception(e)
            raise UnableToParseRunConfig(
                f"Unable to parse run-config file: {filename}"
            )
