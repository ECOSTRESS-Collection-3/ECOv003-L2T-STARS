pub mod covariance;
pub mod kalman;
pub mod sobol;
pub mod spatial;

use numpy::{PyArray2, PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArray3, PyUntypedArrayMethods};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::covariance::{compute_n_eff, fast_var_est};
use crate::kalman::{fuse_scene_parallel, FusionInputs};

#[pyfunction]
fn smoke_test() -> PyResult<String> {
    let n_threads = rayon::current_num_threads();
    Ok(format!("_stars_rust active (rayon threads: {})", n_threads))
}

#[pyfunction]
#[pyo3(signature = (coarse_cov_stack, coarse_cell_size, fine_cell_size, min_num_obs=8, default_var=1e-4))]
fn estimate_spatial_variance<'py>(
    py: Python<'py>,
    coarse_cov_stack: PyReadonlyArray3<'py, f64>,
    coarse_cell_size: f64,
    fine_cell_size: f64,
    min_num_obs: usize,
    default_var: f64,
) -> PyResult<Bound<'py, PyArray2<f64>>> {
    let shape = coarse_cov_stack.shape();
    let (nx, ny, nt) = (shape[0], shape[1], shape[2]);
    let slice = coarse_cov_stack
        .as_slice()
        .map_err(|_| PyValueError::new_err("coarse_cov_stack must be C-contiguous float64"))?;

    let agg_scale = (coarse_cell_size / fine_cell_size).round() as usize;
    let n_eff = compute_n_eff(agg_scale, 2.0, 1.5);
    let sp_var = py.allow_threads(|| fast_var_est(slice, nx, ny, nt, n_eff, min_num_obs, default_var));

    let arr = ndarray::Array2::from_shape_vec((nx, ny), sp_var)
        .map_err(|e| PyValueError::new_err(format!("shape error: {e}")))?;
    Ok(PyArray2::from_owned_array(py, arr))
}

#[pyfunction]
#[pyo3(signature = (
    coarse_stack,
    coarse_time_indices,
    fine_stack,
    fine_time_indices,
    coarse_origin,
    coarse_cell_size,
    fine_origin,
    fine_cell_size,
    prior_mean,
    prior_var,
    prior_bias_mean,
    prior_bias_var,
    cov_scale,
    coarse_res_scalar,
    target_time_index,
    num_workers=8,
    nsamp=100,
    window_buffer=4.0,
    cov_wt=0.2,
    nb_coarse=2.0
))]
#[allow(clippy::too_many_arguments)]
fn fuse_stars_product<'py>(
    py: Python<'py>,
    coarse_stack: PyReadonlyArray3<'py, f64>,
    coarse_time_indices: PyReadonlyArray1<'py, usize>,
    fine_stack: PyReadonlyArray3<'py, f64>,
    fine_time_indices: PyReadonlyArray1<'py, usize>,
    coarse_origin: [f64; 2],
    coarse_cell_size: [f64; 2],
    fine_origin: [f64; 2],
    fine_cell_size: [f64; 2],
    prior_mean: PyReadonlyArray2<'py, f64>,
    prior_var: PyReadonlyArray2<'py, f64>,
    prior_bias_mean: PyReadonlyArray2<'py, f64>,
    prior_bias_var: PyReadonlyArray2<'py, f64>,
    cov_scale: PyReadonlyArray2<'py, f64>,
    coarse_res_scalar: f64,
    target_time_index: usize,
    num_workers: usize,
    nsamp: usize,
    window_buffer: f64,
    cov_wt: f64,
    nb_coarse: f64,
) -> PyResult<(
    Bound<'py, PyArray2<f64>>,
    Bound<'py, PyArray2<f64>>,
    Bound<'py, PyArray2<f64>>,
    Bound<'py, PyArray2<f64>>,
)> {
    let cshape = coarse_stack.shape();
    let fshape = fine_stack.shape();
    let (coarse_nx, coarse_ny, coarse_nt) = (cshape[0], cshape[1], cshape[2]);
    let (fine_nx, fine_ny, fine_nt) = (fshape[0], fshape[1], fshape[2]);

    let inp = FusionInputs {
        coarse_stack: coarse_stack.as_slice().map_err(|_| PyValueError::new_err("coarse_stack must be contiguous"))?,
        coarse_nx,
        coarse_ny,
        coarse_nt,
        coarse_times: coarse_time_indices.as_slice().map_err(|_| PyValueError::new_err("coarse_time_indices must be contiguous"))?,
        fine_stack: fine_stack.as_slice().map_err(|_| PyValueError::new_err("fine_stack must be contiguous"))?,
        fine_nx,
        fine_ny,
        fine_nt,
        fine_times: fine_time_indices.as_slice().map_err(|_| PyValueError::new_err("fine_time_indices must be contiguous"))?,
        coarse_origin,
        coarse_cell_size,
        fine_origin,
        fine_cell_size,
        prior_mean: prior_mean.as_slice().map_err(|_| PyValueError::new_err("prior_mean must be contiguous"))?,
        prior_var: prior_var.as_slice().map_err(|_| PyValueError::new_err("prior_var must be contiguous"))?,
        prior_bias_mean: prior_bias_mean.as_slice().map_err(|_| PyValueError::new_err("prior_bias_mean must be contiguous"))?,
        prior_bias_var: prior_bias_var.as_slice().map_err(|_| PyValueError::new_err("prior_bias_var must be contiguous"))?,
        cov_scale: cov_scale.as_slice().map_err(|_| PyValueError::new_err("cov_scale must be contiguous"))?,
        coarse_res_scalar,
        target_time: target_time_index,
        nsamp,
        window_buffer,
        nb_coarse,
        cov_wt,
    };

    let (fused_mean, fused_sd, fused_bias, fused_bias_sd) =
        py.allow_threads(|| fuse_scene_parallel(&inp, num_workers));

    let out_mean = PyArray2::from_owned_array(
        py,
        ndarray::Array2::from_shape_vec((fine_nx, fine_ny), fused_mean)
            .map_err(|e| PyValueError::new_err(e.to_string()))?,
    );
    let out_sd = PyArray2::from_owned_array(
        py,
        ndarray::Array2::from_shape_vec((fine_nx, fine_ny), fused_sd)
            .map_err(|e| PyValueError::new_err(e.to_string()))?,
    );
    let out_bias = PyArray2::from_owned_array(
        py,
        ndarray::Array2::from_shape_vec((coarse_nx, coarse_ny), fused_bias)
            .map_err(|e| PyValueError::new_err(e.to_string()))?,
    );
    let out_bias_sd = PyArray2::from_owned_array(
        py,
        ndarray::Array2::from_shape_vec((coarse_nx, coarse_ny), fused_bias_sd)
            .map_err(|e| PyValueError::new_err(e.to_string()))?,
    );

    Ok((out_mean, out_sd, out_bias, out_bias_sd))
}

#[pymodule]
fn _stars_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(smoke_test, m)?)?;
    m.add_function(wrap_pyfunction!(estimate_spatial_variance, m)?)?;
    m.add_function(wrap_pyfunction!(fuse_stars_product, m)?)?;
    Ok(())
}
