"""
tests/test_output_writer.py

Unit tests for OutputWriter.
"""
import os
import pandas as pd
from pyoscomp.output.writer import OutputWriter

def test_write_csv(tmp_path):
    writer = OutputWriter(str(tmp_path))
    df = pd.DataFrame({"x": [1, 2]})
    path = writer.write_csv("foo", df)
    assert os.path.exists(path)
    df2 = pd.read_csv(path)
    pd.testing.assert_frame_equal(df, df2)

def test_write_multiple(tmp_path):
    writer = OutputWriter(str(tmp_path))
    dfs = {"a": pd.DataFrame({"y": [3]}), "b": pd.DataFrame({"z": [4]})}
    paths = writer.write_multiple(dfs)
    for name, path in paths.items():
        assert os.path.exists(path)
        pd.testing.assert_frame_equal(dfs[name], pd.read_csv(path))
