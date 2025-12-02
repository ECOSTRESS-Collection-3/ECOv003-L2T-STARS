import subprocess
from os.path import abspath, dirname
import logging

logger = logging.getLogger(__name__)

directory = abspath(dirname(__file__))

def main():
    VNP43NRT_jl_directory = directory
    command = ["julia", f"--project={VNP43NRT_jl_directory}", "-e", "using Pkg; Pkg.instantiate()"]
    logger.info(f"Running: {' '.join(command)}")
    result = subprocess.run(command, check=False)
    return result

if __name__ == "__main__":
    main()
