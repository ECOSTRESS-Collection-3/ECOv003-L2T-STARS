use pyo3::prelude::*;

/// Smoke test verifying that the compiled `_stars_rust` PyO3 extension loads and executes.
#[pyfunction]
fn smoke_test() -> PyResult<String> {
    let n_threads = rayon::current_num_threads();
    Ok(format!("_stars_rust active (rayon threads: {})", n_threads))
}

/// Python module definition for `ECOv003_L2T_STARS._stars_rust`.
#[pymodule]
fn _stars_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(smoke_test, m)?)?;
    Ok(())
}
