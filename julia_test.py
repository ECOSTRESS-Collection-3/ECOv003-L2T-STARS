#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np

try:
    import rasterio
except ImportError:
    rasterio = None


# Exact 5 target files written by process_ECOSTRESS_data_fusion_distributed_bias.jl
OUTPUT_FILES = [
    "STARS_albedo_2026-10-10_11SPS_70m.tif",
    "STARS_albedo.UQ_2026-10-10_11SPS_70m.tif",
    "STARS_albedo.flag_2026-10-10_11SPS_70m.tif",
    "STARS_albedo.bias_2026-10-10_11SPS_70m.tif",
    "STARS_albedo.bias.UQ_2026-10-10_11SPS_70m.tif",
]


def run_julia_fusion(repo_root: Path) -> None:
    test_outputs_dir = repo_root / "test_outputs"
    test_outputs_dir.mkdir(parents=True, exist_ok=True)

    default_downsampled = (
        Path.home()
        / "data"
        / "ECOv003_testing"
        / "L2T_STARS_SOURCES"
        / "VCD43NRT_DOWNSAMPLED_products"
    )
    downsampled_dir = os.environ.get("DOWNSAMPLED_DIR", str(default_downsampled))

    # Standard Julia executable call (no "+1.11" version argument)
    cmd = [
        "julia",
        "--project=ECOv003_L2T_STARS",
        "--threads",
        "1",
        "ECOv003_L2T_STARS/process_ECOSTRESS_data_fusion_distributed_bias.jl",
        "8",
        "11SPS",
        "980",
        "70",
        "2026-10-03",
        "2026-10-10",
        "2026-10-07",
        "2026-10-10",
        downsampled_dir,
        "albedo",
        "test_outputs/STARS_albedo_2026-10-10_11SPS_70m.tif",
        "test_outputs/STARS_albedo.UQ_2026-10-10_11SPS_70m.tif",
        "test_outputs/STARS_albedo.flag_2026-10-10_11SPS_70m.tif",
        "test_outputs/STARS_albedo.bias_2026-10-10_11SPS_70m.tif",
        "test_outputs/STARS_albedo.bias.UQ_2026-10-10_11SPS_70m.tif",
        "test_inputs/STARS_albedo_2026-10-06_11SPS_70m.tif",
        "test_inputs/STARS_albedo.UQ_2026-10-06_11SPS_70m.tif",
        "test_inputs/STARS_albedo.bias_2026-10-06_11SPS_70m.tif",
        "test_inputs/STARS_albedo.bias.UQ_2026-10-06_11SPS_70m.tif",
    ]

    print("=" * 96)
    print(f"Executing STARS Data Fusion in: {repo_root}")
    print("=" * 96)
    
    # Create a copy of the environment and strip out dynamic linker overrides
    clean_env = os.environ.copy()
    clean_env.pop("DYLD_LIBRARY_PATH", None)
    clean_env.pop("DYLD_FALLBACK_LIBRARY_PATH", None)
    clean_env.pop("LD_LIBRARY_PATH", None)
    
    # Execute the command with the sanitized environment
    subprocess.run(cmd, cwd=repo_root, check=True, env=clean_env)
    print("\nJulia process finished with exit status 0.\n")


def compute_statistics(test_path: Path, ref_path: Path) -> Dict[str, Any]:
    if rasterio is None:
        raise RuntimeError("Please install rasterio to inspect GeoTIFFs: pip install rasterio")

    with rasterio.open(test_path) as src_t, rasterio.open(ref_path) as src_r:
        if src_t.shape != src_r.shape:
            return {
                "error": f"Shape mismatch: test={src_t.shape} vs ref={src_r.shape}"
            }

        arr_t = src_t.read(1)
        arr_r = src_r.read(1)
        nodata = src_t.nodata

    # Treat flag raster as discrete integer mask
    is_flag = "flag" in test_path.name

    if is_flag:
        valid_mask = np.ones(arr_t.shape, dtype=bool)
        if nodata is not None:
            valid_mask &= (arr_t != nodata) & (arr_r != nodata)

        t_valid = arr_t[valid_mask]
        r_valid = arr_r[valid_mask]

        if t_valid.size == 0:
            return {"error": "All pixels masked as NoData"}

        exact_matches = np.sum(t_valid == r_valid)
        accuracy = (exact_matches / t_valid.size) * 100.0

        return {
            "is_flag": True,
            "valid_count": int(t_valid.size),
            "match_pct": accuracy,
            "max_abs_diff": float(np.max(np.abs(t_valid - r_valid))),
            "rmse": float(np.sqrt(np.mean((t_valid - r_valid) ** 2))),
            "bias": float(np.mean(t_valid - r_valid)),
            "pearson_r": 1.0 if accuracy == 100.0 else 0.0,
        }

    # Continuous float rasters (albedo, uncertainty, bias)
    t_f = arr_t.astype(np.float64)
    r_f = arr_r.astype(np.float64)

    valid_mask = ~np.isnan(t_f) & ~np.isnan(r_f)
    if nodata is not None and not np.isnan(nodata):
        valid_mask &= (t_f != nodata) & (r_f != nodata)

    # Check for NaN alignment mismatch between test and reference
    nan_mismatch = np.sum(np.isnan(t_f) != np.isnan(r_f))

    t_valid = t_f[valid_mask]
    r_valid = r_f[valid_mask]

    if t_valid.size == 0:
        return {"error": "All pixels are NaN/NoData in both rasters"}

    diff = t_valid - r_valid
    abs_diff = np.abs(diff)

    max_abs_diff = float(np.max(abs_diff))
    mean_abs_diff = float(np.mean(abs_diff))
    rmse = float(np.sqrt(np.mean(diff**2)))
    bias = float(np.mean(diff))

    std_t = np.std(t_valid)
    std_r = np.std(r_valid)
    if std_t > 1e-12 and std_r > 1e-12:
        pearson_r = float(np.corrcoef(t_valid, r_valid)[0, 1])
    else:
        pearson_r = 1.0 if np.allclose(t_valid, r_valid, atol=1e-7) else 0.0

    match_pct = (np.sum(abs_diff <= 1e-5) / t_valid.size) * 100.0

    return {
        "is_flag": False,
        "valid_count": int(t_valid.size),
        "nan_mismatch": int(nan_mismatch),
        "match_pct": match_pct,
        "max_abs_diff": max_abs_diff,
        "mean_abs_diff": mean_abs_diff,
        "rmse": rmse,
        "bias": bias,
        "pearson_r": pearson_r,
    }


def compare_outputs(test_dir: Path, expected_dir: Path) -> None:
    print("=" * 96)
    print("STARS FUSION VERIFICATION: test_outputs vs expected_outputs")
    print("=" * 96)

    col_fmt = "{:<48} {:<10} {:<12} {:<12} {:<10}"
    print(col_fmt.format("Output Raster", "Match %", "Max |Diff|", "RMSE", "Pearson r"))
    print("-" * 96)

    for filename in OUTPUT_FILES:
        test_file = test_dir / filename
        ref_file = expected_dir / filename

        if not test_file.exists():
            print(f"{filename:<48} [MISSING TEST OUTPUT]")
            continue
        if not ref_file.exists():
            print(f"{filename:<48} [MISSING IN expected_outputs]")
            continue

        stats = compute_statistics(test_file, ref_file)
        if "error" in stats:
            print(f"{filename:<48} ERROR: {stats['error']}")
            continue

        row_str = col_fmt.format(
            filename,
            f"{stats['match_pct']:.2f}%",
            f"{stats['max_abs_diff']:.3e}",
            f"{stats['rmse']:.3e}",
            f"{stats['pearson_r']:.6f}",
        )
        print(row_str)

        if stats.get("nan_mismatch", 0) > 0:
            print(f"  └─ Warning: {stats['nan_mismatch']} pixels have discordant NaN masks.")

    print("=" * 96)


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    os.chdir(repo_root)

    run_julia_fusion(repo_root)
    compare_outputs(repo_root / "test_outputs", repo_root / "expected_outputs")


if __name__ == "__main__":
    main()