from typing import Union
from datetime import date

import numpy as np

import rasters as rt
from rasters import Raster, RasterGeometry
from VCD43NRT import VCD43NRT


def generate_albedo_coarse_image(
    date_UTC: Union[date, str],
    VCD43NRT_connection: VCD43NRT,
    geometry: RasterGeometry = None
) -> Raster:
    """
    Generates a coarse-resolution albedo image from VIIRS data.

    Args:
        date_UTC (Union[date, str]): The UTC date for which to retrieve albedo data.
        VCD43NRT_connection (VCD43NRT): An initialized VIIRS processor.
        geometry (RasterGeometry, optional): The target geometry for the VIIRS image.
                                            If None, the native VIIRS geometry is used.

    Returns:
        Raster: A Raster object representing the coarse-resolution albedo image.
                Zero values are converted to NaN.
    """
    coarse_image = VCD43NRT_connection.albedo(date_UTC=date_UTC, geometry=geometry)
    # Convert zero values to NaN for consistency
    coarse_image = rt.where(coarse_image == 0, np.nan, coarse_image)
    return coarse_image
