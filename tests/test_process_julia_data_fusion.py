import logging
import subprocess
from datetime import date
from unittest.mock import patch

import pytest

from ECOv003_L2T_STARS.process_julia_data_fusion import process_julia_data_fusion


def test_logs_julia_stderr_and_stdout_on_failure(tmp_path, caplog):
    """Issue #95: Julia subprocess stderr/stdout must be logged when exit code != 0."""
    caplog.set_level(logging.INFO)
    fake_proc = subprocess.CompletedProcess(
        args=["julia"],
        returncode=1,
        stdout="starting 4 workers\nloading inputs",
        stderr="ERROR: LoadError: OutOfMemoryError()\nStacktrace:\n [1] top-level scope",
    )

    with (
        patch("ECOv003_L2T_STARS.process_julia_data_fusion.find_julia_command", return_value=["julia"]),
        patch("ECOv003_L2T_STARS.process_julia_data_fusion.subprocess.run", return_value=fake_proc) as mock_run,
    ):
        with pytest.raises(RuntimeError, match="Julia data fusion failed for NDVI at tile 29UPT with exit code 1"):
            process_julia_data_fusion(
                tile="29UPT",
                coarse_cell_size=490,
                fine_cell_size=70,
                VIIRS_start_date=date(2026, 8, 19),
                VIIRS_end_date=date(2026, 8, 26),
                HLS_start_date=date(2026, 8, 19),
                HLS_end_date=date(2026, 8, 26),
                downsampled_directory=str(tmp_path / "downsampled"),
                product_name="NDVI",
                posterior_filename=str(tmp_path / "post.tif"),
                posterior_UQ_filename=str(tmp_path / "post.UQ.tif"),
                posterior_flag_filename=str(tmp_path / "post.flag.tif"),
                posterior_bias_filename=str(tmp_path / "post.bias.tif"),
                posterior_bias_UQ_filename=str(tmp_path / "post.bias.UQ.tif"),
            )

    assert mock_run.call_args.kwargs["capture_output"] is True
    assert mock_run.call_args.kwargs["text"] is True
    assert "OutOfMemoryError()" in caplog.text
    assert "starting 4 workers" in caplog.text
