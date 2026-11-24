"""
Docker smoke test for ECOv003-L2T-STARS package installation.

Validates that the package, compiled _stars_rust extension, GDAL NetCDF/HDF5
drivers, and upstream VCD43NRT/HLS interfaces are functional inside the container.
"""

import importlib
import inspect
import sys


class TestPackageImport:
    def test_main_package_import(self):
        import ECOv003_L2T_STARS
        assert hasattr(ECOv003_L2T_STARS, "__version__")

    def test_core_modules_import(self):
        core_modules = [
            "ECOv003_L2T_STARS.L2T_STARS",
            "ECOv003_L2T_STARS.L2TSTARSConfig",
            "ECOv003_L2T_STARS.constants",
            "ECOv003_L2T_STARS.generate_L2T_STARS_runconfig",
            "ECOv003_L2T_STARS.generate_STARS_inputs",
            "ECOv003_L2T_STARS.load_prior",
            "ECOv003_L2T_STARS.process_rust_data_fusion",
            "ECOv003_L2T_STARS.process_julia_data_fusion",
            "ECOv003_L2T_STARS.process_STARS_product",
            "ECOv003_L2T_STARS.retrieve_STARS_sources",
            "ECOv003_L2T_STARS.ECOv003_DL",
        ]
        for module_name in core_modules:
            module = importlib.import_module(module_name)
            assert module is not None, f"Failed to import {module_name}"


class TestCriticalDependencies:
    def test_rust_extension_active(self):
        from ECOv003_L2T_STARS import _stars_rust
        assert "_stars_rust active" in _stars_rust.smoke_test()

    def test_gdal_netcdf_or_hdf5_driver_available(self):
        import rasterio
        with rasterio.Env() as env:
            drivers = env.drivers()
            assert "netCDF" in drivers or "HDF5" in drivers

    def test_vcd43nrt_and_hls_api_contract(self):
        from VCD43NRT import VCD43NRT
        from harmonized_landsat_sentinel import HLS2Connection

        vcd_sig = inspect.signature(VCD43NRT.__init__)
        for param in ("VCD43NRT_staging_directory", "fallback_mode", "mission_priority"):
            assert param in vcd_sig.parameters

        assert callable(getattr(VCD43NRT, "prefetch_VNP09GA", None))
        assert callable(getattr(HLS2Connection, "listing", None))


class TestEntryPoint:
    def test_entry_point_callable(self):
        from ECOv003_L2T_STARS.L2T_STARS import build_parser, main
        assert callable(main)
        assert callable(build_parser)

    def test_python_version(self):
        assert sys.version_info >= (3, 12)
