import importlib
import os
import shutil
import subprocess
from unittest.mock import Mock, call

import pytest

import ECOv003_L2T_STARS
from ECOv003_L2T_STARS.julia_environment import (
    JULIA_PROJECT,
    JuliaEnvironmentError,
    PROJECT_SCRIPTS,
    find_julia_command,
    manifest_julia_version,
    verify_julia_environments,
)

installer = importlib.import_module("ECOv003_L2T_STARS.install_julia")


def test_install_julia_is_exposed_at_package_level():
    assert ECOv003_L2T_STARS.install_julia is installer.install_julia


def test_install_julia_reuses_existing_runtime(monkeypatch):
    monkeypatch.setattr(installer, "manifest_julia_version", lambda: "1.11.6")
    monkeypatch.setattr(installer, "find_julia_command", lambda: ["/bin/julia", "+1.11.6"])
    run = Mock()
    verify = Mock()
    monkeypatch.setattr(installer, "_run", run)
    monkeypatch.setattr(installer, "verify_julia_environments", verify)
    monkeypatch.setattr(installer, "_install_juliaup", Mock(side_effect=AssertionError))

    installer.install_julia()

    run.assert_called_once_with([
        "/bin/julia", "+1.11.6", f"--project={JULIA_PROJECT}",
        "-e", "using Pkg; Pkg.instantiate(); Pkg.precompile()",
    ])
    verify.assert_called_once_with(["/bin/julia", "+1.11.6"])


@pytest.mark.parametrize("existing_juliaup", [None, "/usr/bin/juliaup"])
def test_install_julia_installs_missing_runtime(monkeypatch, existing_juliaup):
    monkeypatch.setattr(installer, "manifest_julia_version", lambda: "1.11.6")
    find = Mock(side_effect=[FileNotFoundError("missing"), ["/juliaup/bin/julia", "+1.11.6"]])
    monkeypatch.setattr(installer, "find_julia_command", find)
    monkeypatch.setattr(installer, "find_juliaup", lambda: existing_juliaup)
    install_up = Mock(return_value="/juliaup/bin/juliaup")
    monkeypatch.setattr(installer, "_install_juliaup", install_up)
    run = Mock()
    monkeypatch.setattr(installer, "_run", run)
    monkeypatch.setattr(installer, "verify_julia_environments", Mock())

    installer.install_julia()

    if existing_juliaup:
        install_up.assert_not_called()
    else:
        install_up.assert_called_once_with("1.11.6")
    assert run.call_args_list[0] == call([existing_juliaup or "/juliaup/bin/juliaup", "add", "1.11.6"])
    assert run.call_args_list[1].args[0][:2] == ["/juliaup/bin/julia", "+1.11.6"]


def test_install_julia_surfaces_install_errors(monkeypatch):
    monkeypatch.setattr(installer, "manifest_julia_version", lambda: "1.11.6")
    monkeypatch.setattr(installer, "find_julia_command", Mock(side_effect=FileNotFoundError("missing")))
    monkeypatch.setattr(installer, "find_juliaup", lambda: "/usr/bin/juliaup")
    monkeypatch.setattr(installer, "_run", Mock(side_effect=JuliaEnvironmentError("download failed")))
    with pytest.raises(JuliaEnvironmentError, match="download failed"):
        installer.install_julia()


def test_find_julia_uses_explicit_channel_when_default_differs(monkeypatch, tmp_path):
    (tmp_path / "Manifest.toml").write_text('julia_version = "1.11.6"\n')
    monkeypatch.setenv("PATH", "/juliaup/bin")
    monkeypatch.setattr("ECOv003_L2T_STARS.julia_environment.find_juliaup", lambda: "/juliaup/bin/juliaup")
    monkeypatch.setattr("ECOv003_L2T_STARS.julia_environment.shutil.which",
                        lambda name, path=None: "/juliaup/bin/julia")

    def run(command, **kwargs):
        version = "1.11.6" if "+1.11.6" in command else "1.12.3"
        return subprocess.CompletedProcess(command, 0, f"julia version {version}\n", "")

    monkeypatch.setattr("ECOv003_L2T_STARS.julia_environment.subprocess.run", run)
    assert find_julia_command(str(tmp_path)) == ["/juliaup/bin/julia", "+1.11.6"]


def test_find_julia_rejects_broken_launcher(monkeypatch, tmp_path):
    (tmp_path / "Manifest.toml").write_text('julia_version = "1.11.6"\n')
    monkeypatch.setenv("PATH", "/juliaup/bin")
    monkeypatch.setattr("ECOv003_L2T_STARS.julia_environment.find_juliaup", lambda: "/juliaup/bin/juliaup")
    monkeypatch.setattr("ECOv003_L2T_STARS.julia_environment.shutil.which",
                        lambda name, path=None: "/juliaup/bin/julia")
    monkeypatch.setattr(
        "ECOv003_L2T_STARS.julia_environment.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "broken launcher"),
    )
    with pytest.raises(FileNotFoundError, match="broken launcher"):
        find_julia_command(str(tmp_path))


def test_juliaup_installer_uses_manifest_version(monkeypatch):
    monkeypatch.setattr(installer.sys, "platform", "darwin")
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b"installer script"
    monkeypatch.setattr(installer, "urlopen", Mock(return_value=response))
    run = Mock(return_value=subprocess.CompletedProcess([], 0, b"", b""))
    monkeypatch.setattr(installer.subprocess, "run", run)
    monkeypatch.setattr(installer, "find_juliaup", lambda: "/home/user/.juliaup/bin/juliaup")

    assert installer._install_juliaup("1.11.6") == "/home/user/.juliaup/bin/juliaup"
    assert run.call_args.args[0] == [
        "sh", "-s", "--", "--yes", "--default-channel", "1.11.6", "--add-to-path=no"
    ]
    assert run.call_args.kwargs["input"] == b"installer script"


def test_manifest_requires_exact_julia_version(tmp_path):
    (tmp_path / "Manifest.toml").write_text('julia_version = "1.11"\n')
    with pytest.raises(JuliaEnvironmentError, match="invalid julia_version"):
        manifest_julia_version(str(tmp_path))


def test_install_julia_reports_instantiation_failure(monkeypatch):
    monkeypatch.setattr(installer, "manifest_julia_version", lambda: "1.11.6")
    monkeypatch.setattr(installer, "find_julia_command", lambda: ["/bin/julia"])
    monkeypatch.setattr(installer, "_run", Mock(side_effect=JuliaEnvironmentError("Pkg failed")))
    verify = Mock()
    monkeypatch.setattr(installer, "verify_julia_environments", verify)
    with pytest.raises(JuliaEnvironmentError, match="Pkg failed"):
        installer.install_julia()
    verify.assert_not_called()


@pytest.mark.skipif(os.name == "nt", reason="uses a POSIX executable")
def test_install_julia_runs_real_subprocesses(monkeypatch, tmp_path):
    version = manifest_julia_version()
    executable = tmp_path / "julia"
    commands = tmp_path / "commands"
    executable.write_text(
        '#!/bin/sh\n'
        f'if [ "$1" = "--version" ]; then echo "julia version {version}"; exit; fi\n'
        'printf "%s\\n" "$*" >> "$JULIA_TEST_COMMANDS"\n'
    )
    executable.chmod(0o755)

    # Prepend tmp_path so the mock 'julia' is found first without dropping system tools like /bin/sh
    current_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{current_path}")

    monkeypatch.setenv("JULIA_TEST_COMMANDS", str(commands))
    monkeypatch.setattr("ECOv003_L2T_STARS.julia_environment.find_juliaup", lambda: None)

    installer.install_julia()

    invocations = commands.read_text().splitlines()
    assert len(invocations) == 2
    assert f"--project={JULIA_PROJECT}" in invocations[0]
    assert "Pkg.instantiate()" in invocations[0]
    assert "julia_smoke_test.jl" in invocations[1]


def test_julia_scripts_and_manifests_exist():
    for project, scripts in PROJECT_SCRIPTS.items():
        assert os.path.exists(os.path.join(project, "Project.toml"))
        assert os.path.exists(os.path.join(project, "Manifest.toml"))
        for script in scripts:
            assert os.path.exists(script)


# Opt-in: only meaningful where the pinned Julia packages are installed (e.g. the Docker image).
# Run with: CHECK_JULIA_ENV=1 pytest tests/test_julia_environment.py
@pytest.mark.skipif(
    os.environ.get("CHECK_JULIA_ENV") != "1" or shutil.which("julia") is None,
    reason="set CHECK_JULIA_ENV=1 and install julia to check the Julia environment",
)
def test_julia_imports():
    try:
        verify_julia_environments()
    except JuliaEnvironmentError as e:
        pytest.fail(str(e))