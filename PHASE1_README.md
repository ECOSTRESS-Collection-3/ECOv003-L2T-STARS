# Phase 1: Rust / PyO3 (`maturin`) Scaffold

## Included Files
- `Cargo.toml` — Rust crate configuration (`_stars_rust` `cdylib` with `pyo3`, `numpy`, `rayon`, `faer`, `sobol_burley`).
- `src/lib.rs` — Initial `#[pymodule]` entry point exposing `smoke_test()`.
- `ECOv003_L2T_STARS/_stars_rust.pyi` — Python type stub for IDE support.
- `pyproject.toml` — Updated `[build-system]` and `[tool.maturin]` configuration bundling legacy Julia files without requiring Julia at install time.
- `makefile` — Updated `make install` (`maturin develop --release`) and `make clean` (`target/`).
- `tests/test_rust_smoke.py` — Pytest check verifying `_stars_rust` builds, imports, and executes.

## Apply & Verify
1. Copy the contents of this archive into the root of `ECOv003-L2T-STARS`.
2. Append `target/` and `ECOv003_L2T_STARS/*.so` to `.gitignore`.
3. Build and test:
   ```bash
   pip install "maturin>=1.7,<2.0"
   make install
   make test
   ```
