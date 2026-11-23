# `ECOv003-L2T-STARS` Repository History & Collection 3 Operational Context (`v1.0.1` – `v1.19.0`)

- **Date:** November 23, 2026
- **Repository:** `ECOSTRESS-Collection-3/ECOv003-L2T-STARS`
- **Release Span:** `v1.0.1` (November 12, 2024) – `v1.19.0` (November 23, 2026)

## 1. Operational Context

`ECOv003-L2T-STARS` produces daily 70 m gap-filled Normalized Difference Vegetation Index (`NDVI`) and broadband albedo (`albedo`) rasters with 1-sigma uncertainty (`*-UQ`), sensor bias (`*-bias`, `*-bias-UQ`), and 7-day HLS availability masks (`*-flag`) for every daytime ECOSTRESS `L2T_LSTE` tile overpass.

1. **Epoch 1 — Collection 2 Port & Suomi NPP Baseline (`v1.0.1` – `v1.12.1`, Nov 2024 – Oct 2026):** Initial Collection 3 port (`v1.0.1`), modularization and `STARSDataFusion.jl` distributed bias integration (`v1.1.0`–`v1.10.0`), and GDAL subprocess isolation / direct `ArchGDAL` GeoTIFF output (`v1.11.0`–`v1.12.1`) supporting the ~11-month Suomi NPP forward-processing run.
2. **Epoch 2 — November 2, 2026 Suomi NPP Decommissioning, JPSS Cutover & Rust Migration (`v1.13.0` – `v1.19.0`, Nov 2026):** Transitioned from `VNP43NRT` to multi-mission JPSS `VCD43NRT` (`v1.13.0`), aligned Python 3.12 dependencies with `ECOv003-L3T-L4T-JET` (`v1.14.0`–`v1.16.0`), hardened coarse outage handling (`v1.17.0`), replaced the Julia data-fusion loop with compiled Rust `_stars_rust` (`v1.18.0`), and resolved post-I&T concurrency and packaging issues (`v1.19.0`).

## 2. Release Timeline Summary

| Version | Date | Key Changes |
| :--- | :--- | :--- |
| `v1.0.1` | 2024-11-12 | Initial Collection 3 port duplicated from `ECOv002-L2T-STARS`. |
| `v1.1.0` | 2025-06-24 | `ECOv003-exit-codes`, `ECOv003-granules`, `STARSDataFusion.jl` distributed bias fusion. |
| `v1.2.0`–`v1.3.0` | Jul 2025 | `StaticAncillaryFileGroup` XML run-configs, Earthdata `.netrc` login, Python `3.10–3.13`. |
| `v1.4.0`–`v1.5.0` | Jul 2025 | Upgraded to `harmonized-landsat-sentinel v2.0.0` (`HLS2Connection`). |
| `v1.6.0`–`v1.10.0` | Jul–Sep 2025 | Decomposed `L2T_STARS.py` into focused modules; added `ECOv003_DL` downloader PGE. |
| `v1.11.0`–`v1.12.1` | Dec 2025–Oct 2026 | Stripped Conda `GDAL_*` vars for Julia subprocesses; direct `ArchGDAL` writes; pinned Julia `1.11.6`. |
| `v1.13.0` | 2026-11-11 | Migrated coarse VIIRS inputs from Suomi NPP `VNP43NRT` to JPSS `VCD43NRT`. |
| `v1.14.0`–`v1.16.0` | Nov 2026 | Aligned Python 3.12 dependencies (`GEOS5FP~=2.24.0`, `numpy~=2.5.4`, `rasterio~=1.5.2`) with `JET`. |
| `v1.17.0` | 2026-11-17 | Added partial-window coarse outage tolerance (`VIIRS_GIVEUP_DAYS = 4`, exit codes `15`/`16`). |
| `v1.18.0` | 2026-11-18 | Compiled Rust/PyO3 data-fusion extension (`_stars_rust`), `VCD43NRT_staging_directory`, `[INFO]` `LandFilter`. |
| `v1.19.0` | 2026-11-23 | Per-granule posterior isolation (`#94`), Julia `stderr` logging (`#95`), `PGEVersion` metadata, `micromamba` Dockerfile & smoke tests. |
