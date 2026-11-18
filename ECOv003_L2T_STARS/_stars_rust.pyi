import numpy as np
from numpy.typing import NDArray

def smoke_test() -> str: ...

def estimate_spatial_variance(
    coarse_cov_stack: NDArray[np.float64],
    coarse_cell_size: float,
    fine_cell_size: float,
    min_num_obs: int = 8,
    default_var: float = 1e-4,
) -> NDArray[np.float64]: ...

def fuse_stars_product(
    coarse_stack: NDArray[np.float64],
    coarse_time_indices: NDArray[np.uintp],
    fine_stack: NDArray[np.float64],
    fine_time_indices: NDArray[np.uintp],
    coarse_origin: list[float],
    coarse_cell_size: list[float],
    fine_origin: list[float],
    fine_cell_size: list[float],
    prior_mean: NDArray[np.float64],
    prior_var: NDArray[np.float64],
    prior_bias_mean: NDArray[np.float64],
    prior_bias_var: NDArray[np.float64],
    cov_scale: NDArray[np.float64],
    coarse_res_scalar: float,
    target_time_index: int,
    num_workers: int = 8,
    nsamp: int = 100,
    window_buffer: float = 4.0,
    cov_wt: float = 0.2,
    nb_coarse: float = 2.0,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
]: ...
