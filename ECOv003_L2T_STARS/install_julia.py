"""Install the Julia runtime and manifest-pinned packages used by STARS."""

import logging
import shutil
import subprocess
import sys
from urllib.error import URLError
from urllib.request import urlopen

from .julia_environment import (
    PROJECT_SCRIPTS,
    JuliaEnvironmentError,
    _run,
    find_julia_command,
    find_juliaup,
    manifest_julia_version,
    verify_julia_environments,
)

logger = logging.getLogger(__name__)


def _install_juliaup(version: str) -> str:
    if sys.platform == "win32":
        winget = shutil.which("winget")
        if not winget:
            raise JuliaEnvironmentError(
                "Juliaup is not installed and winget is unavailable. "
                "Install Juliaup from https://github.com/JuliaLang/juliaup and retry."
            )
        _run([winget, "install", "--id", "9NJNWW8PVKMN", "-e", "-s", "msstore",
              "--accept-package-agreements", "--accept-source-agreements"])
    elif sys.platform.startswith(("linux", "darwin", "freebsd")):
        try:
            with urlopen("https://install.julialang.org", timeout=60) as response:
                installer = response.read()
        except (OSError, URLError) as e:
            raise JuliaEnvironmentError(f"Could not download the Juliaup installer: {e}") from e
        result = subprocess.run(
            ["sh", "-s", "--", "--yes", "--default-channel", version, "--add-to-path=no"],
            input=installer, capture_output=True, check=False,
        )
        if result.returncode:
            raise JuliaEnvironmentError(
                f"Juliaup installer failed with exit code {result.returncode}:\n"
                f"{result.stdout.decode(errors='replace')}\n{result.stderr.decode(errors='replace')}"
            )
    else:
        raise JuliaEnvironmentError(f"Automatic Juliaup installation is unsupported on {sys.platform}")

    juliaup = find_juliaup()
    if not juliaup:
        raise JuliaEnvironmentError(
            "Juliaup was installed but could not be found. Add it to PATH and retry."
        )
    return juliaup


def install_julia() -> None:
    """Ensure the manifest's Julia runtime and packages are installed and usable.

    This may download and install Juliaup, Julia, and Julia packages in the user's
    Julia depot. It does not change the default Julia version or shell PATH.
    """
    version = manifest_julia_version()
    try:
        julia = find_julia_command()
    except FileNotFoundError:
        juliaup = find_juliaup()
        if juliaup is None:
            logger.info("Installing Juliaup and Julia %s", version)
            juliaup = _install_juliaup(version)
        logger.info("Ensuring Julia %s is installed with Juliaup", version)
        _run([juliaup, "add", version])
        try:
            julia = find_julia_command()
        except FileNotFoundError as e:
            raise JuliaEnvironmentError(f"Julia {version} is still unavailable after installation: {e}") from e

    for project in PROJECT_SCRIPTS:
        _run([*julia, f"--project={project}", "-e", "using Pkg; Pkg.instantiate(); Pkg.precompile()"])
    verify_julia_environments(julia)
    logger.info("Julia %s and its pinned packages are installed and verified", version)
