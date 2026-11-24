"""Generate a VCD43NRT granule for one date and MODLAND tile.

VIIRS downloads require Earthdata authentication.
"""

import logging
from datetime import date
from pathlib import Path

from VCD43NRT import VCD43NRT


def main():
    logging.basicConfig(level=logging.INFO)

    target_date = date(2024, 10, 30)
    tile = "h08v05"
    working_directory = Path("~/data/VCD43NRT_example").expanduser()

    processor = VCD43NRT(
        working_directory=str(working_directory),
        mission="SNPP",
        mission_priority=("SNPP", "JPSS1", "JPSS2"),
        fallback_mode=True,
    )
    granule = processor.VCD43NRT(date_UTC=target_date, tile=tile)

    print(f"Product directory: {granule.directory}")
    print(f"NDVI: {granule.variable_filename('NDVI')}")
    print(f"Albedo: {granule.variable_filename('albedo')}")
    print(f"Available layers: {', '.join(sorted(granule.variables))}")


if __name__ == "__main__":
    main()
