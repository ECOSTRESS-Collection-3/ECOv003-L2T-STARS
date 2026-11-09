from typing import Union
from datetime import date
import numpy as np

import rasters as rt
from rasters import Raster, RasterGeometry

from VCD43NRT import VCD43NRT

def generate_NDVI_coarse_image(
        date_UTC: Union[date, str],
        VCD43NRT_connection: VCD43NRT,
        geometry: RasterGeometry = None) -> Raster:
    """
    Generates a coarse-resolution NDVI image from VIIRS data.

    Args:
        date_UTC (Union[date, str]): The UTC date for which to retrieve NDVI data.
        VCD43NRT_connection (VCD43NRT): An initialized VIIRS processor.
        geometry (RasterGeometry, optional): The target geometry for the VIIRS image.
                                            If None, the native VIIRS geometry is used.

    Returns:
        Raster: A Raster object representing the coarse-resolution NDVI image.
                Zero values are converted to NaN.
    """
    coarse_image = VCD43NRT_connection.NDVI(date_UTC=date_UTC, geometry=geometry)
    # Convert zero values (often used as NoData in some datasets) to NaN for proper handling
    coarse_image = rt.where(coarse_image == 0, np.nan, coarse_image)
    return coarse_image
