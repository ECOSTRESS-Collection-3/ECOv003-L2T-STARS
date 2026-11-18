import importlib
import pkgutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np


def test_python() -> list[str]:
    """Run import and dummy callable tests for the Python environment."""
    import ECOv003_L2T_STARS
    from ECOv003_L2T_STARS.generate_filename import generate_filename
    from ECOv003_L2T_STARS.runconfig import parse_runconfig

    failed = []
    package_path = Path(ECOv003_L2T_STARS.__file__).parent

    for module in pkgutil.iter_modules([str(package_path)]):
        module_name = f"ECOv003_L2T_STARS.{module.name}"
        try:
            importlib.import_module(module_name)
            print(f"OK    Python import: {module_name}")
        except Exception as e:
            msg = f"FAIL  Python import: {module_name} -> {e}"
            print(msg)
            failed.append(msg)

    try:
        parsed = parse_runconfig("<input><scalar name='smoke'>ok</scalar></input>")
        assert parsed["smoke"] == "ok"
        with tempfile.TemporaryDirectory() as directory:
            filename = generate_filename(directory, "smoke", "2000-01-01", "H00V00", 70)
            assert Path(filename).name == "STARS_smoke_2000-01-01_H00V00_70m.tif"
        print("OK    Python dummy calls")
    except Exception as e:
        msg = f"FAIL  Python dummy calls -> {e}"
        print(msg)
        failed.append(msg)

    return failed


def test_rust() -> list[str]:
    """Run smoke test checks against the compiled _stars_rust extension."""
    failed = []
    try:
        from ECOv003_L2T_STARS import _stars_rust

        status = _stars_rust.smoke_test()
        assert "_stars_rust active" in status
        print(f"OK    Rust extension: {status}")

        stack = np.ones((4, 4, 10), dtype=np.float64)
        var = _stars_rust.estimate_spatial_variance(stack, 490.0, 70.0)
        assert var.shape == (4, 4)
        print("OK    Rust spatial variance kernel")
    except Exception as e:
        msg = f"FAIL  Rust extension smoke test -> {e}"
        print(msg)
        failed.append(msg)

    return failed


def test_julia() -> list[str]:
    """Run smoke test script in the optional legacy Julia environment."""
    failed = []
    base_dir = Path(__file__).parent
    julia_script = base_dir / "julia_smoke_test.jl"

    try:
        result = subprocess.run(
            ["julia", f"--project={base_dir}", str(julia_script)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.stdout:
            print(result.stdout.rstrip())
        if result.returncode != 0:
            if result.stderr:
                print(result.stderr.rstrip())
            failed.append(f"Julia smoke test failed (exit code {result.returncode})")
    except Exception as e:
        msg = f"Julia smoke test error: {e}"
        print(msg)
        failed.append(msg)

    return failed


def test() -> int:
    """Run Python and Rust smoke tests (no Julia runtime required) and return an exit status code."""
    failed = []

    failed.extend(test_python())
    failed.extend(test_rust())

    if failed:
        print(f"\n{len(failed)} smoke test failure(s)")
        return 1

    print("\nSmoke tests passed")
    return 0


test_python.__test__ = False
test_rust.__test__ = False
test_julia.__test__ = False
test.__test__ = False


if __name__ == "__main__":
    raise SystemExit(test())