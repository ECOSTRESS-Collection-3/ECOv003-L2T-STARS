#!/usr/bin/env python3
"""
Run offline Julia STARS data fusion verification against `test_bundle/`,
stream live Julia console logs, and display a comparison statistics table.
"""

import argparse
from datetime import datetime
from pathlib import Path
import tempfile
from typing import Any, Dict, List

import colored_logging as cl
import numpy as np
import rasterio

from ECOv003_L2T_STARS.process_julia_data_fusion import process_julia_data_fusion

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUNDLE_DIR = REPO_ROOT / "test_bundle"

PRODUCTS = [
    ("NDVI", 490),
    ("albedo", 980),
]

SUFFIXES = ["", ".UQ", ".flag", ".bias", ".bias.UQ"]


def compute_layer_stats(local_arr: np.ndarray, expected_arr: np.ndarray, is_flag: bool = False) -> Dict[str, Any]:
    if local_arr.shape != expected_arr.shape:
        return {"error": f"shape mismatch {local_arr.shape} vs {expected_arr.shape}"}

    a_raw = local_arr.astype(np.float64)
    b_raw = expected_arr.astype(np.float64)

    a_nan = ~np.isfinite(a_raw)
    b_nan = ~np.isfinite(b_raw)
    nan_disagreements = int(np.count_nonzero(a_nan != b_nan))
    valid = ~(a_nan | b_nan)

    if not np.any(valid):
        return {"error": f"no jointly valid pixels (NaN diff={nan_disagreements})"}

    a = a_raw[valid]
    b = b_raw[valid]
    diff = a - b
    abs_diff = np.abs(diff)

    if is_flag:
        exact_pct = float(np.mean(a == b) * 100.0)
        tol_pct = exact_pct
    else:
        exact_pct = float(np.mean(a == b) * 100.0)
        tol_pct = float(np.mean(abs_diff <= 1e-5) * 100.0)

    rmse = float(np.sqrt(np.mean(diff ** 2)))
    mae = float(np.mean(abs_diff))
    bias = float(np.mean(diff))
    max_diff = float(np.max(abs_diff))

    if np.std(a) > 1e-12 and np.std(b) > 1e-12:
        r = float(np.corrcoef(a, b)[0, 1])
    else:
        r = 1.0 if np.allclose(a, b, atol=1e-7) else 0.0

    return {
        "n": int(a.size),
        "nan_diff": nan_disagreements,
        "exact_pct": exact_pct,
        "tol_pct": tol_pct,
        "bias": bias,
        "mae": mae,
        "rmse": rmse,
        "max_diff": max_diff,
        "r": r,
    }


def print_comparison_table(rows: List[Dict[str, Any]]) -> None:
    print("\n" + "=" * 124)
    print("OFFLINE JULIA STARS DATA FUSION VERIFICATION SUMMARY (Generated vs test_bundle/reference_outputs)")
    print("=" * 124)
    header = (
        f"{'Output Raster':<44} {'Pixels':>9} {'NaN Diff':>9} {'Exact %':>9} "
        f"{'<=1e-5 %':>9} {'Bias':>12} {'MAE':>12} {'RMSE':>12} {'Max |Diff|':>12} {'Pearson r':>10}"
    )
    print(header)
    print("-" * 124)

    for row in rows:
        name = row["name"]
        if "error" in row:
            print(f"{name:<44} ERROR: {row['error']}")
            continue
        print(
            f"{name:<44} "
            f"{row['n']:>9,d} "
            f"{row['nan_diff']:>9,d} "
            f"{row['exact_pct']:>8.2f}% "
            f"{row['tol_pct']:>8.2f}% "
            f"{row['bias']:>+12.4e} "
            f"{row['mae']:>12.4e} "
            f"{row['rmse']:>12.4e} "
            f"{row['max_diff']:>12.4e} "
            f"{row['r']:>10.6f}"
        )

    print("=" * 124 + "\n")


def run_verification(
    bundle_dir: Path,
    threads: int = 1,
    num_workers: int = 8,
    keep_work_dir: bool = False,
) -> int:
    cl.configure()

    if not bundle_dir.exists():
        raise FileNotFoundError(f"Test bundle directory not found: {bundle_dir}")

    downsampled_dir = bundle_dir / "inputs" / "DOWNSAMPLED_products"
    priors_dir = bundle_dir / "priors"
    ref_dir = bundle_dir / "reference_outputs"

    if keep_work_dir:
        out_dir = REPO_ROOT / f"verify_julia_out_{datetime.now():%Y%m%d_%H%M%S}"
        out_dir.mkdir(parents=True, exist_ok=True)
        temp_ctx = None
    else:
        temp_ctx = tempfile.TemporaryDirectory(prefix="ecov003_julia_verify_")
        out_dir = Path(temp_ctx.name)

    try:
        rows: List[Dict[str, Any]] = []
        all_passed = True

        for product_name, coarse_res in PRODUCTS:
            posteriors = {
                suffix: out_dir / f"STARS_{product_name}{suffix}_2026-10-10_11SPS_70m.tif"
                for suffix in SUFFIXES
            }

            process_julia_data_fusion(
                tile="11SPS",
                coarse_cell_size=coarse_res,
                fine_cell_size=70,
                VIIRS_start_date=datetime.strptime("2026-10-03", "%Y-%m-%d").date(),
                VIIRS_end_date=datetime.strptime("2026-10-10", "%Y-%m-%d").date(),
                HLS_start_date=datetime.strptime("2026-10-07", "%Y-%m-%d").date(),
                HLS_end_date=datetime.strptime("2026-10-10", "%Y-%m-%d").date(),
                downsampled_directory=str(downsampled_dir),
                product_name=product_name,
                posterior_filename=str(posteriors[""]),
                posterior_UQ_filename=str(posteriors[".UQ"]),
                posterior_flag_filename=str(posteriors[".flag"]),
                posterior_bias_filename=str(posteriors[".bias"]),
                posterior_bias_UQ_filename=str(posteriors[".bias.UQ"]),
                prior_filename=str(priors_dir / f"STARS_{product_name}_2026-10-06_11SPS_70m.tif"),
                prior_UQ_filename=str(priors_dir / f"STARS_{product_name}.UQ_2026-10-06_11SPS_70m.tif"),
                prior_bias_filename=str(priors_dir / f"STARS_{product_name}.bias_2026-10-06_11SPS_70m.tif"),
                prior_bias_UQ_filename=str(priors_dir / f"STARS_{product_name}.bias.UQ_2026-10-06_11SPS_70m.tif"),
                threads=threads,
                num_workers=num_workers,
            )

            for suffix, out_path in posteriors.items():
                ref_path = ref_dir / out_path.name
                with rasterio.open(out_path) as src_out, rasterio.open(ref_path) as src_ref:
                    stats = compute_layer_stats(
                        src_out.read(1),
                        src_ref.read(1),
                        is_flag=(suffix == ".flag"),
                    )
                stats["name"] = out_path.name
                rows.append(stats)

                if "error" in stats or stats["nan_diff"] > 0 or stats["rmse"] > 1e-4:
                    all_passed = False

        print_comparison_table(rows)
        return 0 if all_passed else 1
    finally:
        if temp_ctx is not None:
            temp_ctx.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run offline Julia STARS data fusion against test_bundle and print comparison statistics."
    )
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=DEFAULT_BUNDLE_DIR,
        help=f"Path to test_bundle directory (default: {DEFAULT_BUNDLE_DIR})",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help="Julia threads per worker (default: 1)",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=8,
        help="Number of Julia distributed workers (default: 8)",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="Keep output directory after completion for inspection",
    )
    args = parser.parse_args()
    return run_verification(
        bundle_dir=args.bundle_dir,
        threads=args.threads,
        num_workers=args.num_workers,
        keep_work_dir=args.keep_work_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())