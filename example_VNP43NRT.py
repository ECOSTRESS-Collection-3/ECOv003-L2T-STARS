"""Generate a VNP43NRT granule for one date and MODLAND tile.

Install the Python package and initialize Julia with
``ECOv003-L2T-STARS-install-julia`` before running this example.
VNP09GA downloads require Earthdata authentication.
"""

import logging
from datetime import date
from pathlib import Path

from ECOv003_L2T_STARS.VNP43NRT import VNP43NRT


def main():
    logging.basicConfig(level=logging.INFO)

    # Change these settings to select the date, MODLAND tile, and output location.
    target_date = date(2024, 10, 30)
    tile = "h08v05"
    working_directory = Path("~/data/VNP43NRT_example").expanduser()

    processor = VNP43NRT(working_directory=str(working_directory))
    granule = processor.VNP43NRT(
        date_UTC=target_date,
        tile=tile,
        diagnostics=False,
    )

    print(f"Product directory: {granule.directory}")
    print(f"NDVI: {granule.variable_filename('NDVI')}")
    print(f"Albedo: {granule.variable_filename('albedo')}")
    print(f"Available layers: {', '.join(sorted(granule.variables))}")


if __name__ == "__main__":
    main()
