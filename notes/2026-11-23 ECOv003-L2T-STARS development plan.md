# `ECOv003-L2T-STARS` Development Plan (`v1.19.0`)

- **Date:** November 23, 2026
- **Target Release:** `v1.19.0`

## `v1.19.0` Deliverables

1. **Fix Concurrent Posterior Cleanup Race Condition (`#94`):** Isolate intermediate posterior GeoTIFFs under `model_directory/<tile>/<date_UTC>/<granule_ID>` in `ECOv003_L2T_STARS/process_STARS_product.py` and verify via `tests/test_process_STARS_product.py`.
2. **Capture Julia Subprocess Output on Failure (`#95`):** Pass `capture_output=True, text=True` to `subprocess.run(...)` in `ECOv003_L2T_STARS/process_julia_data_fusion.py` and log `stdout`/`stderr` on non-zero exit codes, verified via `tests/test_process_julia_data_fusion.py`.
3. **Granule Provenance Metadata:** Record `StandardMetadata["PGEVersion"] = __version__` in `L2T_STARS.py` and `process_STARS_product.py`.
4. **CLI Consolidation:** Consolidate `build_parser()` and `main(argv=None)` into `ECOv003_L2T_STARS/L2T_STARS.py` (with `main.py` re-exporting) and return `SUCCESS_EXIT_CODE` from `install-julia`.
5. **Container & Smoke-Test Alignment (`#96`):** Update `Dockerfile` to `mambaorg/micromamba:ubuntu24.04` with `libgdal-netcdf`, `libgdal-hdf5`, pinned `GDAL_DRIVER_PATH`/`GDAL_DATA`/`PROJ_DATA`, and Rust compilation; expand `smoke_test.py`, `tests/test_docker_smoke.py`, and `makefile`.
6. **Documentation & Release Rollout (`#96`):** Update `README.md` and `notes/`, bump `pyproject.toml` to `1.19.0`, rebuild `ecostress-level-2-3-4`, purge truncated `.nc4` files in `GEOS5FP_download/`, and re-drive failed I&T DAG tasks.
