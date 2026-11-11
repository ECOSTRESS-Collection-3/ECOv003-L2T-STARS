#!/usr/bin/env python3
"""
Reconfigure this package for a target Julia version with a complete environment overhaul.

Usage: python set_julia_version.py 1.13        (or 1.13.3)

Installs the Julia channel with juliaup if missing, cleans out stale manifest/cache
artifacts, updates the registry, recalculates dependencies from scratch, runs the
smoke test, and synchronizes the Dockerfile, README.md, and julia_test.sh.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "ECOv003_L2T_STARS"
MANIFEST = PROJECT / "Manifest.toml"


def run(command):
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def substitute(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text()
    new_text, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count == 0:
        raise SystemExit(f"{path.name}: pattern not found: {pattern}")
    path.write_text(new_text)


def purge_stale_environment(channel: str):
    """Remove manifest locks and precompile cache to force a fresh resolution."""
    # 1. Remove pinned Manifest
    if MANIFEST.exists():
        print(f"Purging existing manifest: {MANIFEST}")
        MANIFEST.unlink()

    # 2. Clean compiled caches for this specific Julia channel to prevent symbol pollution
    compiled_dir = Path.home() / ".julia" / "compiled" / f"v{channel}"
    if compiled_dir.exists():
        print(f"Purging precompile cache: {compiled_dir}")
        shutil.rmtree(compiled_dir, ignore_errors=True)


def main() -> int:
    if len(sys.argv) != 2 or not re.fullmatch(r"\d+\.\d+(\.\d+)?", sys.argv[1]):
        print(__doc__)
        return 2
    channel = ".".join(sys.argv[1].split(".")[:2])

    probe = subprocess.run(["julia", f"+{channel}", "--version"], capture_output=True, cwd=ROOT)
    if probe.returncode != 0:
        run(["juliaup", "add", channel])

    # Clean stale locks and compiled caches before building the new environment
    purge_stale_environment(channel)

    julia = ["julia", f"+{channel}", f"--project={PROJECT}"]

    # Update package registry first, then resolve from clean Project.toml
    overhaul_expr = (
        "using Pkg; "
        "Pkg.Registry.update(); "
        "Pkg.resolve(); "
        "Pkg.instantiate(); "
        "Pkg.precompile()"
    )
    run([*julia, "-e", overhaul_expr])

    run([*julia, str(PROJECT / "julia_smoke_test.jl"),
         str(PROJECT / "process_ECOSTRESS_data_fusion_distributed_bias.jl")])

    # Full patch version that produced the manifest, used for the Docker download
    full = re.search(r'^julia_version\s*=\s*"(\d+\.\d+\.\d+)', MANIFEST.read_text(), re.MULTILINE)
    if not full:
        raise SystemExit("cannot read julia_version from Manifest.toml")
    full = full.group(1)

    substitute(ROOT / "Dockerfile", r"^ENV JULIA_VERSION=.*$", f"ENV JULIA_VERSION={full}")
    substitute(ROOT / "Dockerfile", r"julialang-s3\.julialang\.org/bin/linux/x64/[\d.]+/",
               f"julialang-s3.julialang.org/bin/linux/x64/{channel}/")
    substitute(ROOT / "README.md", r"This requires Julia \d+\.\d+ ", f"This requires Julia {channel} ")
    substitute(ROOT / "julia_test.sh", r"Julia \d+\.\d+ matches", f"Julia {channel} matches")
    substitute(ROOT / "julia_test.sh", r"^julia \+\d+\.\d+ ", f"julia +{channel} ")

    print(f"Configured for Julia {full}. Review with `git diff`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())