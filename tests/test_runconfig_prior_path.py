from datetime import datetime
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest


@pytest.fixture
def generated_runconfig(tmp_path, monkeypatch):
    generator = import_module("ECOv003_L2T_STARS.generate_L2T_STARS_runconfig")
    config = import_module("ECOv003_L2T_STARS.L2TSTARSConfig")
    granule = SimpleNamespace(
        orbit=1, scene=2, tile="11SPS", time_UTC=datetime(2026, 10, 10)
    )
    monkeypatch.setattr(generator, "L2TLSTE", lambda _: granule)
    monkeypatch.setattr(config, "L2TLSTE", lambda _: granule)
    monkeypatch.setattr(
        generator, "L2TSTARS",
        SimpleNamespace(generate_granule_name=lambda *args, **kwargs: "test"),
    )
    monkeypatch.setattr(config, "L2TSTARS", generator.L2TSTARS)

    def read_config(_, filename):
        root = ElementTree.parse(filename).getroot()
        return {
            group.attrib["name"]: {
                scalar.attrib["name"]: scalar.text or ""
                for scalar in group.findall("scalar")
            }
            for group in root.findall("group")
        }

    monkeypatch.setattr(config.L2TSTARSConfig, "read_runconfig", read_config)
    monkeypatch.setenv("HOME", str(tmp_path))
    prior = tmp_path / "prior"
    prior.mkdir()
    filename = generator.generate_L2T_STARS_runconfig(
        L2T_LSTE_filename="ECOv003_L2T_LSTE_test",
        prior_L2T_STARS_filename="~/prior",
        working_directory=str(tmp_path / "work"),
    )
    return config.L2TSTARSConfig, filename, prior


def test_generated_prior_path_is_absolute(generated_runconfig):
    config_class, filename, prior = generated_runconfig
    assert str(prior) in Path(filename).read_text()
    assert config_class(filename).L2T_STARS_prior_filename == str(prior)


def test_existing_runconfig_expands_prior_home_path(generated_runconfig):
    config_class, filename, prior = generated_runconfig
    path = Path(filename)
    path.write_text(path.read_text().replace(str(prior), "~/prior"))
    assert config_class(filename).L2T_STARS_prior_filename == str(prior)
