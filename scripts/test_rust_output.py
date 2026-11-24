#!/usr/bin/env python3
"""
Run offline Rust STARS data fusion verification against `test_bundle/`,
benchmark execution runtime, and display a comparison statistics table.
"""

import argparse
from datetime import datetime
from pathlib import Path
import tempfile
from time import perf_counter
from typing import Any, Dict, List

import colored_logging as cl
import rasterio

from ECOv003_L2T_STARS.process_rust_data_fusion import process_rust_data_fusion
from pathlib import Path as _P; import sys as _S; _S.path.insert(0, str(_P(__file__).resolve().parent)); from test_julia_output import PRODUCTS, SUFFIXES, compute_layer_stats, print_comparison_table

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUNDLE_DIR = REPO_ROOT / "test_bundle"


def run_verification(
    bundle_dir: Path,
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
        out_dir = REPO_ROOT / f"verify_rust_out_{datetime.now():%Y%m%d_%H%M%S}"
        out_dir.mkdir(parents=True, exist_ok=True)
        temp_ctx = None
    else:
        temp_ctx = tempfile.TemporaryDirectory(prefix="ecov003_rust_verify_")
        out_dir = Path(temp_ctx.name)

    try:
        rows: List[Dict[str, Any]] = []
        all_passed = True
        t_start = perf_counter()

        for product_name, coarse_res in PRODUCTS:
            posteriors = {
                suffix: out_dir / f"STARS_{product_name}{suffix}_2026-10-10_11SPS_70m.tif"
                for suffix in SUFFIXES
            }

            process_rust_data_fusion(
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
        print(f"Total Rust verification elapsed time: {perf_counter() - t_start:.2f} s")
        return 0 if all_passed else 1
    finally:
        if temp_ctx is not None:
            temp_ctx.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run offline Rust STARS data fusion against test_bundle and print comparison statistics."
    )
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=DEFAULT_BUNDLE_DIR,
        help=f"Path to test_bundle directory (default: {DEFAULT_BUNDLE_DIR})",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=8,
        help="Number of Rayon worker threads (default: 8)",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="Keep output directory after completion for inspection",
    )
    args = parser.parse_args()
    return run_verification(
        bundle_dir=args.bundle_dir,
        num_workers=args.num_workers,
        keep_work_dir=args.keep_work_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
