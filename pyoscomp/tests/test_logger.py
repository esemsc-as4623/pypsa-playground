"""
tests/test_logger.py

Unit test for logger setup.
"""
import os
from pyoscomp.logs.logger import get_logger

def test_logger_creates_log_file(tmp_path):
    logger = get_logger(run_name="testrun", scenario="testscen", log_dir=str(tmp_path))
    logger.info("Test log entry")
    log_files = list(tmp_path.glob("*.log"))
    assert len(log_files) == 1
    with open(log_files[0], "r") as f:
        content = f.read()
    assert "Test log entry" in content
