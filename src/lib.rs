pub mod covariance;
pub mod kalman;
pub mod sobol;
pub mod spatial;

use numpy::{
    PyArray2, PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArray3, PyUntypedArrayMethods,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::covariance::{compute_n_eff, fast_var_est};
use crate::kalman::{run_scene_fusion, FusionInputs};

type FusionOutput<'py> = (
    Bound<'py, PyArray2<f64>>,
    Bound<'py, PyArray2<f64>>,
    Bound<'py, PyArray2<f64>>,
    Bound<'py, PyArray2<f64>>,
);

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
    let sp_var =
        py.allow_threads(|| fast_var_est(slice, nx, ny, nt, n_eff, min_num_obs, default_var));

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
) -> PyResult<FusionOutput<'py>> {
    let coarse_times = coarse_time_indices
        .as_slice()
        .map_err(|_| PyValueError::new_err("coarse_time_indices must be contiguous"))?;
    let fine_times = fine_time_indices
        .as_slice()
        .map_err(|_| PyValueError::new_err("fine_time_indices must be contiguous"))?;

    let inp = FusionInputs {
        coarse_data: coarse_stack.as_array(),
        coarse_dates: coarse_times,
        fine_data: fine_stack.as_array(),
        fine_dates: fine_times,
        coarse_origin,
        coarse_csize: coarse_cell_size,
        fine_origin,
        fine_csize: fine_cell_size,
        prior_mean: prior_mean.as_array(),
        prior_var: prior_var.as_array(),
        prior_bias_mean: prior_bias_mean.as_array(),
        prior_bias_var: prior_bias_var.as_array(),
        cov_scale: cov_scale.as_array(),
        coarse_cell_size: coarse_res_scalar,
        n_times: target_time_index,
        nsamp,
        window_buffer,
        cov_wt,
        phi: 0.001,
        ar_par: 1.0,
        nb_coarse,
    };

    let out = py.allow_threads(|| run_scene_fusion(&inp, num_workers));

    Ok((
        PyArray2::from_owned_array(py, out.fused_mean),
        PyArray2::from_owned_array(py, out.fused_sd),
        PyArray2::from_owned_array(py, out.fused_bias),
        PyArray2::from_owned_array(py, out.fused_bias_sd),
    ))
}

#[pymodule]
fn _stars_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(smoke_test, m)?)?;
    m.add_function(wrap_pyfunction!(estimate_spatial_variance, m)?)?;
    m.add_function(wrap_pyfunction!(fuse_stars_product, m)?)?;
    Ok(())
}
