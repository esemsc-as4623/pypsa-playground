"""
tests/test_input_reader.py

Unit tests for ScenarioInputReader.
"""
import os
import pandas as pd
import pytest
from pyoscomp.input.reader import ScenarioInputReader

def test_read_all_csvs(tmp_path):
    # Create a sample CSV
    csv_path = tmp_path / "test.csv"
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    df.to_csv(csv_path, index=False)
    reader = ScenarioInputReader(str(tmp_path))
    reader.read_all_csvs()
    assert "test" in reader.csv_data
    pd.testing.assert_frame_equal(reader.csv_data["test"], df)

def test_read_config(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_content = "key: value\n"
    config_path.write_text(config_content)
    reader = ScenarioInputReader(str(tmp_path))
    reader.read_config()
    assert reader.config["key"] == "value"
