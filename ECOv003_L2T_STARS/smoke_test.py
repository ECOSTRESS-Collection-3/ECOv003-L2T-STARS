import importlib
import pkgutil
import subprocess
import tempfile
from pathlib import Path


def test():
    """Run import and callable smoke tests for the Python and Julia environments."""
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

    julia_script = Path(__file__).parent / "julia_smoke_test.jl"
    project_dir = Path(__file__).parent

    try:
        result = subprocess.run(
            ["julia", f"--project={project_dir}", str(julia_script)],
            capture_output=True,
            text=True,
            timeout=300
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            failed.append(f"Julia smoke test failed (exit code {result.returncode})")
    except Exception as e:
        msg = f"Julia smoke test error: {e}"
        print(msg)
        failed.append(msg)

    if failed:
        print(f"\n{len(failed)} smoke test failure(s)")
        return 1

    print("\nSmoke tests passed")
    return 0
