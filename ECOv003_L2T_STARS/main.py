import sys
import argparse
import logging

from .version import __version__
from .constants import *
from .L2T_STARS import L2T_STARS
from .smoke_test import test as run_smoke_test

# Initialize the logger for the module
logger = logging.getLogger(__name__)


def main():
    """
    Main function for parsing command-line arguments and running the L2T_STARS PGE.

    This function uses `argparse` for robust command-line argument parsing,
    providing a clear interface for users to specify the run-configuration file
    and other optional parameters.
    """
    if sys.argv[1:2] == ["test"]:
        sys.exit(run_smoke_test())

    parser = argparse.ArgumentParser(
        description="ECOSTRESS Collection 3 L2T_STARS PGE for generating Tiled Auxiliary NDVI and Albedo products.",
        formatter_class=argparse.RawTextHelpFormatter, # Allows for more flexible help text formatting
        epilog=f"L2T_STARS PGE Version: {__version__}\n\n"
               "Example usage:\n"
               "  python {sys.argv[0]} --runconfig /path/to/RunConfig.xml\n"
               "  python {sys.argv[0]} --runconfig /path/to/RunConfig.xml --date 2023-01-15\n"
               "  python {sys.argv[0]} --runconfig /path/to/RunConfig.xml --sources-only\n"
               "  python {sys.argv[0]} --runconfig /path/to/RunConfig.xml --overwrite\n" # Added example usage
    )

    # Positional argument for the runconfig file
    parser.add_argument(
        "runconfig",
        type=str,
        help="Path to the XML run-configuration file.",
    )

    # Optional arguments
    parser.add_argument(
        "--date",
        type=str,
        help="Target UTC date for product generation (YYYY-MM-DD). Overrides date in runconfig.",
        metavar="YYYY-MM-DD"
    )
    parser.add_argument(
        "--spinup-days",
        type=int,
        default=SPINUP_DAYS,
        help=f"Number of days for the VIIRS time-series spin-up. Defaults to {SPINUP_DAYS} days.",
        metavar="DAYS"
    )
    parser.add_argument(
        "--target-resolution",
        type=int,
        default=TARGET_RESOLUTION,
        help=f"Desired output product resolution in meters. Defaults to {TARGET_RESOLUTION}m.",
        metavar="METERS"
    )
    parser.add_argument(
        "--ndvi-resolution",
        type=int,
        default=NDVI_RESOLUTION,
        help=f"Resolution of coarse NDVI data in meters. Defaults to {NDVI_RESOLUTION}m.",
        metavar="METERS"
    )
    parser.add_argument(
        "--albedo-resolution",
        type=int,
        default=ALBEDO_RESOLUTION,
        help=f"Resolution of coarse albedo data in meters. Defaults to {ALBEDO_RESOLUTION}m.",
        metavar="METERS"
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
        "--initialize-julia",
        action="store_true",
        dest="initialize_julia",
        help="Initialize a julia environment before running julia.",
    )
    parser.add_argument(
        "--threads",
        type=str,
        default="auto",
        help='Number of Julia threads to use, or "auto". Defaults to "auto".',
        metavar="COUNT"
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help=f"Number of Julia workers for distributed processing. Defaults to 4.",
        metavar="COUNT"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Reproduce the output files even if they already exist.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit.",
    )

    args = parser.parse_args()

    # Call the main L2T_STARS processing function with parsed arguments
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
        initialize_julia=args.initialize_julia,
        threads=args.threads,
        num_workers=args.num_workers,
        overwrite=args.overwrite, # Pass the new overwrite argument
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
