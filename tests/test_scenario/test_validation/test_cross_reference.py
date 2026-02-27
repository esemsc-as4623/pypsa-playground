# tests/test_scenario/test_validation/test_cross_reference.py

import pytest
import pandas as pd
from pathlib import Path
from pyoscomp.scenario.validation.cross_reference import validate_scenario
from pyoscomp.scenario.validation.schemas import SchemaError

def test_valid_scenario_passes(tmp_path):
    # Create minimal valid scenario
    (tmp_path / 'REGION.csv').write_text('VALUE\nREGION1\n')
    (tmp_path / 'YEAR.csv').write_text('VALUE\n2025\n')
    (tmp_path / 'TECHNOLOGY.csv').write_text('VALUE\nTECH1\n')
    (tmp_path / 'FUEL.csv').write_text('VALUE\nFUEL1\n')
    (tmp_path / 'CapitalCost.csv').write_text('REGION,TECHNOLOGY,YEAR,VALUE\nREGION1,TECH1,2025,100\n')
    # Should not raise
    validate_scenario(str(tmp_path))

def test_invalid_technology_reference_fails(tmp_path):
    (tmp_path / 'REGION.csv').write_text('VALUE\nREGION1\n')
    (tmp_path / 'YEAR.csv').write_text('VALUE\n2025\n')
    (tmp_path / 'TECHNOLOGY.csv').write_text('VALUE\nTECH1\n')
    (tmp_path / 'CapitalCost.csv').write_text('REGION,TECHNOLOGY,YEAR,VALUE\nREGION1,TECH2,2025,100\n')
    with pytest.raises(SchemaError) as exc_info:
        validate_scenario(str(tmp_path))
    assert 'TECH2' in str(exc_info.value)

def test_invalid_fuel_reference_fails(tmp_path):
    (tmp_path / 'REGION.csv').write_text('VALUE\nREGION1\n')
    (tmp_path / 'YEAR.csv').write_text('VALUE\n2025\n')
    (tmp_path / 'TECHNOLOGY.csv').write_text('VALUE\nTECH1\n')
    (tmp_path / 'FUEL.csv').write_text('VALUE\nFUEL1\n')
    (tmp_path / 'InputActivityRatio.csv').write_text('REGION,TECHNOLOGY,FUEL,MODE_OF_OPERATION,YEAR,VALUE\nREGION1,TECH1,FAKE_FUEL,1,2025,1.0\n')
    with pytest.raises(SchemaError) as exc_info:
        validate_scenario(str(tmp_path))
    assert 'FAKE_FUEL' in str(exc_info.value)

def test_missing_required_set_file_fails(tmp_path):
    # Only create YEAR and TECHNOLOGY, omit REGION
    (tmp_path / 'YEAR.csv').write_text('VALUE\n2025\n')
    (tmp_path / 'TECHNOLOGY.csv').write_text('VALUE\nTECH1\n')
    with pytest.raises(SchemaError) as exc_info:
        validate_scenario(str(tmp_path))
    assert 'REGION.csv' in str(exc_info.value)

def test_optional_parameter_file_skipped(tmp_path):
    # Create only required set files, no CapitalCost.csv
    (tmp_path / 'REGION.csv').write_text('VALUE\nREGION1\n')
    (tmp_path / 'YEAR.csv').write_text('VALUE\n2025\n')
    (tmp_path / 'TECHNOLOGY.csv').write_text('VALUE\nTECH1\n')
    (tmp_path / 'FUEL.csv').write_text('VALUE\nFUEL1\n')
    # Should not raise
    validate_scenario(str(tmp_path))
