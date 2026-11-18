from datetime import date, timedelta
import logging
from os import makedirs
from os.path import dirname, exists, join
from time import perf_counter
from typing import Optional

import colored_logging as cl
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject

from . import _stars_rust

logger = logging.getLogger(__name__)

DEFAULT_MEAN = 0.12
DEFAULT_SD = 0.01
DEFAULT_BIAS_MEAN = 0.0
DEFAULT_BIAS_SD = 0.001


def _read_band_f64(filename: str) -> tuple[np.ndarray, dict]:
    with rasterio.open(filename) as src:
        arr = src.read(1).astype(np.float64)
        nodata = src.nodata
        if nodata is not None and not np.isnan(nodata):
            arr[arr == nodata] = np.nan
        profile = src.profile.copy()
        transform = src.transform
    # Transpose (row=y, col=x) -> Julia/STARS (x, y) orientation
    return np.ascontiguousarray(arr.T), {"profile": profile, "transform": transform}


def _write_geotiff_f32(label: str, filename: str, data_xy: np.ndarray, meta: dict) -> None:
    logger.info(f"[Rust] writing {label} GeoTIFF: {cl.file(filename)}")
    makedirs(dirname(filename), exist_ok=True)
    profile = meta["profile"].copy()
    profile.pop("blockxsize", None)
    profile.pop("blockysize", None)
    use_tiles = profile["width"] >= 256 and profile["height"] >= 256
    profile.update(
        driver="GTiff",
        dtype="float32",
        count=1,
        nodata=np.nan,
        compress="deflate",
        predictor=2,
        tiled=use_tiles,
        **({"blockxsize": 256, "blockysize": 256} if use_tiles else {}),
    )
    with rasterio.open(filename, "w", **profile) as dst:
        dst.write(data_xy.T.astype(np.float32), 1)


def _write_geotiff_i32(label: str, filename: str, data_xy: np.ndarray, meta: dict) -> None:
    logger.info(f"[Rust] writing {label} GeoTIFF: {cl.file(filename)}")
    makedirs(dirname(filename), exist_ok=True)
    profile = meta["profile"].copy()
    profile.pop("blockxsize", None)
    profile.pop("blockysize", None)
    use_tiles = profile["width"] >= 256 and profile["height"] >= 256
    profile.update(
        driver="GTiff",
        dtype="int32",
        count=1,
        nodata=-9999,
        compress="deflate",
        predictor=2,
        tiled=use_tiles,
        **({"blockxsize": 256, "blockysize": 256} if use_tiles else {}),
    )
    with rasterio.open(filename, "w", **profile) as dst:
        dst.write(data_xy.T.astype(np.int32), 1)


def process_rust_data_fusion(
    tile: str,
    coarse_cell_size: int,
    fine_cell_size: int,
    VIIRS_start_date: date,
    VIIRS_end_date: date,
    HLS_start_date: date,
    HLS_end_date: date,
    downsampled_directory: str,
    product_name: str,
    posterior_filename: str,
    posterior_UQ_filename: str,
    posterior_flag_filename: str,
    posterior_bias_filename: str,
    posterior_bias_UQ_filename: str,
    prior_filename: Optional[str] = None,
    prior_UQ_filename: Optional[str] = None,
    prior_bias_filename: Optional[str] = None,
    prior_bias_UQ_filename: Optional[str] = None,
    num_workers: int = 8,
) -> None:
    t0 = perf_counter()
    logger.info(
        f"[Rust] starting STARS data fusion for {cl.name(product_name)} at tile {cl.place(tile)} "
        f"({cl.val(coarse_cell_size)}m -> {cl.val(fine_cell_size)}m, workers={cl.val(num_workers)})"
    )
    logger.info(
        f"[Rust] VIIRS window: {cl.time(VIIRS_start_date)} to {cl.time(VIIRS_end_date)} | "
        f"HLS window: {cl.time(HLS_start_date)} to {cl.time(HLS_end_date)}"
    )

    t_inputs_start = perf_counter()
    coarse_dates_all = [
        VIIRS_start_date + timedelta(days=d)
        for d in range((VIIRS_end_date - VIIRS_start_date).days + 1)
    ]
    coarse_file_by_date = {}
    for d in coarse_dates_all:
        ds = d.strftime("%Y-%m-%d")
        fn = join(downsampled_directory, f"{d.year}", ds, tile, f"STARS_{product_name}_{tile}_{coarse_cell_size}m.tif")
        if exists(fn):
            coarse_file_by_date[ds] = fn

    fine_flag_start_date = HLS_end_date - timedelta(days=7)
    dates = [
        HLS_start_date + timedelta(days=d)
        for d in range((HLS_end_date - HLS_start_date).days + 1)
    ]
    all_fine_dates = [
        min(fine_flag_start_date, HLS_start_date) + timedelta(days=d)
        for d in range((HLS_end_date - min(fine_flag_start_date, HLS_start_date)).days + 1)
    ]
    fine_file_by_date = {}
    for d in all_fine_dates:
        ds = d.strftime("%Y-%m-%d")
        fn = join(downsampled_directory, f"{d.year}", ds, tile, f"STARS_{product_name}_{tile}_{fine_cell_size}m.tif")
        if exists(fn):
            fine_file_by_date[ds] = fn

    logger.info(
        f"[Rust] discovered {cl.val(len(coarse_file_by_date))} coarse {product_name} rasters and "
        f"{cl.val(len(fine_file_by_date))} fine {product_name} rasters"
    )

    coarse_template_fn = next(iter(coarse_file_by_date.values()))
    fine_template_fn = next(iter(fine_file_by_date.values()))
    _, coarse_meta = _read_band_f64(coarse_template_fn)
    _, fine_meta = _read_band_f64(fine_template_fn)

    coarse_nx = coarse_meta["profile"]["width"]
    coarse_ny = coarse_meta["profile"]["height"]
    fine_nx = fine_meta["profile"]["width"]
    fine_ny = fine_meta["profile"]["height"]

    ct = coarse_meta["transform"]
    ft = fine_meta["transform"]
    coarse_csize = [float(ct.a), float(ct.e)]
    fine_csize = [float(ft.a), float(ft.e)]
    coarse_origin = [float(ct.c) + abs(coarse_csize[0]) / 2.0, float(ct.f) - coarse_cell_size + abs(coarse_csize[1]) / 2.0]
    fine_origin = [float(ft.c) + abs(fine_csize[0]) / 2.0, float(ft.f) - fine_cell_size + abs(fine_csize[1]) / 2.0]

    # Load covariance stack & cache coarse slices
    cov_stack = np.full((coarse_nx, coarse_ny, len(coarse_dates_all)), np.nan, dtype=np.float64)
    coarse_cache = {}
    for i, d in enumerate(coarse_dates_all):
        ds = d.strftime("%Y-%m-%d")
        fn = coarse_file_by_date.get(ds)
        if fn is not None:
            sl, _ = _read_band_f64(fn)
            coarse_cache[ds] = sl
            cov_stack[:, :, i] = sl

    # Assemble coarse fusion stack
    matched_coarse_idx = []
    matched_coarse_slices = []
    for t_idx, d in enumerate(dates, start=1):
        ds = d.strftime("%Y-%m-%d")
        if ds in coarse_cache:
            matched_coarse_idx.append(t_idx)
            matched_coarse_slices.append(coarse_cache[ds])
    if matched_coarse_slices:
        coarse_stack = np.ascontiguousarray(np.stack(matched_coarse_slices, axis=2))
        coarse_times = np.array(matched_coarse_idx, dtype=np.uintp)
    else:
        coarse_stack = np.full((coarse_nx, coarse_ny, 1), np.nan, dtype=np.float64)
        coarse_times = np.array([1], dtype=np.uintp)

    # Assemble fine fusion stack
    matched_fine_idx = []
    matched_fine_slices = []
    for t_idx, d in enumerate(dates, start=1):
        ds = d.strftime("%Y-%m-%d")
        fn = fine_file_by_date.get(ds)
        if fn is not None:
            sl, _ = _read_band_f64(fn)
            matched_fine_idx.append(t_idx)
            matched_fine_slices.append(sl)
    if matched_fine_slices:
        fine_stack = np.ascontiguousarray(np.stack(matched_fine_slices, axis=2))
        fine_times = np.array(matched_fine_idx, dtype=np.uintp)
    else:
        fine_stack = np.full((fine_nx, fine_ny, 1), np.nan, dtype=np.float64)
        fine_times = np.array([1], dtype=np.uintp)

    # 7-day HLS availability flag
    fine_pixels = np.sum(~np.isnan(fine_stack), axis=2)
    if np.any(fine_pixels == 0) and fine_flag_start_date < HLS_start_date:
        n_flag_days = (HLS_start_date - fine_flag_start_date).days
        for d_off in range(n_flag_days):
            ds = (fine_flag_start_date + timedelta(days=d_off)).strftime("%Y-%m-%d")
            fn = fine_file_by_date.get(ds)
            if fn is not None:
                sl, _ = _read_band_f64(fn)
                fine_pixels += ~np.isnan(sl)
    hls_flag = (fine_pixels == 0).astype(np.int32)

    # Priors
    use_prior = all(
        p is not None and exists(p)
        for p in (prior_filename, prior_UQ_filename, prior_bias_filename, prior_bias_UQ_filename)
    )
    if use_prior:
        logger.info(f"[Rust] loading prior state from {cl.file(prior_filename)}")
        prior_mean, _ = _read_band_f64(prior_filename)
        prior_sd, _ = _read_band_f64(prior_UQ_filename)
        prior_bias_mean, _ = _read_band_f64(prior_bias_filename)
        prior_bias_sd, _ = _read_band_f64(prior_bias_UQ_filename)
        if np.any(np.isnan(prior_mean)):
            prior_flag = np.isnan(prior_mean)
            if np.any(np.sum(~np.isnan(fine_stack), axis=2) == 0):
                scale_factor = coarse_cell_size // fine_cell_size
                coarse_valid = np.repeat(
                    np.repeat(np.sum(~np.isnan(coarse_stack), axis=2), scale_factor, axis=0),
                    scale_factor,
                    axis=1,
                )
                prior_flag[coarse_valid > 0] = False
            prior_flag[fine_pixels > 0] = False
            prior_mean[np.isnan(prior_mean)] = np.nanmean(prior_mean)
        else:
            prior_flag = np.zeros((fine_nx, fine_ny), dtype=bool)
        prior_var = np.ascontiguousarray(prior_sd ** 2)
        prior_bias_var = np.ascontiguousarray(prior_bias_sd ** 2)
    else:
        logger.info("[Rust] initializing cold-start default priors")
        prior_mean = np.full((fine_nx, fine_ny), DEFAULT_MEAN, dtype=np.float64)
        prior_var = np.full((fine_nx, fine_ny), DEFAULT_SD ** 2, dtype=np.float64)
        prior_bias_mean = np.full((coarse_nx, coarse_ny), DEFAULT_BIAS_MEAN, dtype=np.float64)
        prior_bias_var = np.full((coarse_nx, coarse_ny), DEFAULT_BIAS_SD ** 2, dtype=np.float64)
        prior_flag = np.ones((fine_nx, fine_ny), dtype=bool)
        scale_factor = coarse_cell_size // fine_cell_size
        coarse_valid = np.repeat(
            np.repeat(np.sum(~np.isnan(coarse_stack), axis=2), scale_factor, axis=0),
            scale_factor,
            axis=1,
        )
        prior_flag[coarse_valid > 0] = False
        prior_flag[fine_pixels > 0] = False

    t_inputs_sec = perf_counter() - t_inputs_start
    logger.info(f"[Rust] input loading & preprocessing completed in {t_inputs_sec:.2f} s")

    # Spatial variance estimation + GDAL cubicspline resampling
    t_cov_start = perf_counter()
    sp_var = _stars_rust.estimate_spatial_variance(
        np.ascontiguousarray(cov_stack),
        float(coarse_cell_size),
        float(fine_cell_size),
    )

    src_log_sd = np.log(np.sqrt(sp_var)).T.astype(np.float64)
    sp_rs_yx = np.full((fine_ny, fine_nx), np.nan, dtype=np.float64)
    reproject(
        source=src_log_sd,
        destination=sp_rs_yx,
        src_transform=coarse_meta["transform"],
        src_crs=coarse_meta["profile"]["crs"],
        dst_transform=fine_meta["transform"],
        dst_crs=fine_meta["profile"]["crs"],
        resampling=Resampling.cubic_spline,
        src_nodata=np.nan,
        dst_nodata=np.nan,
    )
    sp_rs = sp_rs_yx.T
    if np.any(np.isnan(sp_rs)):
        sp_rs[np.isnan(sp_rs)] = np.nanmean(sp_rs)
    cov_scale = np.ascontiguousarray(np.exp(sp_rs))
    t_cov_sec = perf_counter() - t_cov_start
    logger.info(f"[Rust] spatial variance estimation & resampling completed in {t_cov_sec:.2f} s")

    n_windows = coarse_nx * coarse_ny
    logger.info(
        f"[Rust] dispatching {cl.val(n_windows)} spatial windows ({coarse_nx}x{coarse_ny}) "
        f"across {cl.val(num_workers)} Rayon threads"
    )
    t_fusion_start = perf_counter()
    fused_mean, fused_sd, fused_bias, fused_bias_sd = _stars_rust.fuse_stars_product(
        coarse_stack,
        coarse_times,
        fine_stack,
        fine_times,
        coarse_origin,
        coarse_csize,
        fine_origin,
        fine_csize,
        np.ascontiguousarray(prior_mean),
        prior_var,
        np.ascontiguousarray(prior_bias_mean),
        prior_bias_var,
        cov_scale,
        float(coarse_cell_size),
        len(dates),
        num_workers=num_workers,
    )
    t_fusion_sec = perf_counter() - t_fusion_start
    logger.info(f"[Rust] data fusion completed in {t_fusion_sec:.2f} s")

    if "NDVI" in posterior_filename:
        np.clip(fused_mean, -1.0, 1.0, out=fused_mean)
    else:
        np.clip(fused_mean, 0.0, 1.0, out=fused_mean)

    fused_mean[prior_flag] = np.nan

    t_write_start = perf_counter()
    _write_geotiff_f32("fused mean", posterior_filename, fused_mean, fine_meta)
    _write_geotiff_i32("fused flag", posterior_flag_filename, hls_flag, fine_meta)
    _write_geotiff_f32("fused SD", posterior_UQ_filename, fused_sd, fine_meta)
    _write_geotiff_f32("bias mean", posterior_bias_filename, fused_bias, coarse_meta)
    _write_geotiff_f32("bias SD", posterior_bias_UQ_filename, fused_bias_sd, coarse_meta)
    t_write_sec = perf_counter() - t_write_start

    t_total_sec = perf_counter() - t0
    logger.info(
        f"[Rust] timing summary ({product_name}, tile {tile}): "
        f"inputs={t_inputs_sec:.2f}s, cov_est={t_cov_sec:.2f}s, "
        f"fusion={t_fusion_sec:.2f}s, write={t_write_sec:.2f}s, total={t_total_sec:.2f}s"
    )
    logger.info(f"[Rust] finished STARS data fusion for {product_name} at tile {tile} in {t_total_sec:.2f} s")
