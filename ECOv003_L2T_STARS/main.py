import argparse
import logging
import sys

from .install_julia import install_julia

from .constants import *
from .L2T_STARS import L2T_STARS
from .smoke_test import (
    test as run_smoke_test,
    test_julia as run_test_julia,
    test_python as run_test_python,
    test_rust as run_test_rust,
)
from .version import __version__

logger = logging.getLogger(__name__)


def _run_subtest(test_fn) -> int:
    """Helper to run a sub-test function, print results, and return an exit code."""
    failed = test_fn()
    if failed:
        print(f"\n{len(failed)} smoke test failure(s)")
        return 1
    print("\nSmoke tests passed")
    return 0


def main():
    """
    Main function for parsing command-line arguments and running the L2T_STARS PGE.
    """
    # Fast-dispatch test and utility subcommands before runconfig validation
    first_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if first_arg == "test":
        sys.exit(run_smoke_test())
    elif first_arg == "test-python":
        sys.exit(_run_subtest(run_test_python))
    elif first_arg == "test-rust":
        sys.exit(_run_subtest(run_test_rust))
    elif first_arg == "test-julia":
        sys.exit(_run_subtest(run_test_julia))
    elif first_arg == "install-julia":
        sys.exit(install_julia())

    parser = argparse.ArgumentParser(
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
        f"  python {sys.argv[0]} /path/to/RunConfig.xml\n"
        f"  python {sys.argv[0]} /path/to/RunConfig.xml --backend rust --num-workers 8\n"
        f"  python {sys.argv[0]} /path/to/RunConfig.xml --backend julia\n"
        f"  python {sys.argv[0]} test\n",
    )

    parser.add_argument(
        "runconfig",
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
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit.",
    )

    args = parser.parse_args()

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

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
