"""
Management of the Julia environments used by this package.

All Julia code (data fusion and VNP43NRT) runs in one project, this directory, whose
Project.toml/Manifest.toml pin the exact package versions. VNP43NRT_jl is a path
dependency of that project.

pip cannot install Julia packages, so run ``ECOv003-L2T-STARS-install-julia`` once after
``pip install`` (the Dockerfile does this). Every Julia call in this package runs with
``--project=<dir>`` so it always uses these pinned environments.
"""
import argparse
import logging
import re
import subprocess
import sys
from os.path import abspath, dirname, join
from typing import List, Optional

logger = logging.getLogger(__name__)

PACKAGE_DIRECTORY = abspath(dirname(__file__))
JULIA_PROJECT = PACKAGE_DIRECTORY

SMOKE_TEST = join(PACKAGE_DIRECTORY, "julia_smoke_test.jl")

# Julia project directory -> scripts that run in it
PROJECT_SCRIPTS = {
    JULIA_PROJECT: [
        join(PACKAGE_DIRECTORY, "process_ECOSTRESS_data_fusion_distributed_bias.jl"),
        join(PACKAGE_DIRECTORY, "VNP43NRT", "process_VNP43NRT.jl"),
    ],
}


class JuliaEnvironmentError(RuntimeError):
    pass


def _run(command: List[str]) -> None:
    logger.info(" ".join(command))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.stdout:
        logger.info(result.stdout)
    if result.returncode != 0:
        raise JuliaEnvironmentError(
            f"command failed with exit code {result.returncode}: {' '.join(command)}\n"
            f"{result.stdout}\n{result.stderr}"
        )


def _manifest_julia_version(project: str) -> Optional[str]:
    try:
        with open(join(project, "Manifest.toml")) as file:
            match = re.search(r'^julia_version\s*=\s*"(\d+\.\d+)', file.read(), re.MULTILINE)
    except OSError:
        return None
    return match.group(1) if match else None


def check_julia_version() -> None:
    """Raise if the installed Julia minor version differs from the one the manifests were resolved with."""
    result = subprocess.run(["julia", "--version"], capture_output=True, text=True, check=False)
    match = re.search(r"(\d+\.\d+)\.\d+", result.stdout)
    if result.returncode != 0 or not match:
        raise JuliaEnvironmentError("julia executable not found or not working")
    installed = match.group(1)
    for project in PROJECT_SCRIPTS:
        expected = _manifest_julia_version(project)
        if expected is not None and expected != installed:
            raise JuliaEnvironmentError(
                f"Julia {installed} is installed but {project}/Manifest.toml was resolved with "
                f"Julia {expected}; install Julia {expected}.x"
            )


def instantiate_julia_environments() -> None:
    """Install the exact package versions recorded in each Manifest.toml and precompile them."""
    check_julia_version()
    for project in PROJECT_SCRIPTS:
        _run(["julia", f"--project={project}", "-e", "using Pkg; Pkg.instantiate(); Pkg.precompile()"])


def verify_julia_environments() -> None:
    """Load every package imported by the Julia scripts in the environment they run in."""
    for project, scripts in PROJECT_SCRIPTS.items():
        _run(["julia", f"--project={project}", SMOKE_TEST, *scripts])


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Install and verify the pinned Julia environment")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="only check the Julia version and that every import loads; do not install anything",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        if args.verify_only:
            check_julia_version()
        else:
            instantiate_julia_environments()
        verify_julia_environments()
    except JuliaEnvironmentError as e:
        logger.error(e)
        return 1
    logger.info("Julia environments are installed and verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
