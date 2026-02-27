# tests/test_scenario/test_validation/test_schema.py

import pytest
import pandas as pd
import numpy as np
import importlib.resources
from pyoscomp.scenario.validation.schemas import SchemaRegistry, validate_csv, SchemaError

@pytest.fixture(scope="module")
def schema():
	# Load the schema from the package
	schema_path = importlib.resources.files("pyoscomp").joinpath("OSeMOSYS_config.yaml")
	return SchemaRegistry(str(schema_path))

def test_valid_set_csv(schema):
	df = pd.DataFrame({"VALUE": [2025, 2030, 2035]})
	assert validate_csv("YEAR", df, schema)

def test_valid_param_csv(schema):
	df = pd.DataFrame({
		"REGION": ["A", "B"],
		"TECHNOLOGY": ["T1", "T2"],
		"YEAR": [2025, 2025],
		"VALUE": [1.0, 2.0]
	})
	assert validate_csv("CapitalCost", df, schema)

def test_missing_column_raises(schema):
	df = pd.DataFrame({"VALUE": [1, 2, 3]})
	# CapitalCost expects REGION, TECHNOLOGY, YEAR, VALUE
	with pytest.raises(SchemaError) as e:
		validate_csv("CapitalCost", df, schema)
	assert "missing columns" in str(e.value)

def test_extra_column_raises(schema):
	df = pd.DataFrame({
		"REGION": ["A"],
		"TECHNOLOGY": ["T1"],
		"YEAR": [2025],
		"VALUE": [1.0],
		"EXTRA": [42]
	})
	with pytest.raises(SchemaError) as e:
		validate_csv("CapitalCost", df, schema)
	assert "unexpected columns" in str(e.value)

def test_wrong_dtype_raises(schema):
	df = pd.DataFrame({"VALUE": ["not_an_int", "still_not"]})
	with pytest.raises(SchemaError) as e:
		validate_csv("YEAR", df, schema)
	assert "integer type" in str(e.value)

def test_nan_in_required_column_raises(schema):
	df = pd.DataFrame({
		"REGION": ["A", None],
		"TECHNOLOGY": ["T1", "T2"],
		"YEAR": [2025, 2025],
		"VALUE": [1.0, 2.0]
		})
	with pytest.raises(SchemaError) as e:
		validate_csv("CapitalCost", df, schema)
	assert "missing values" in str(e.value)

def test_duplicate_set_value_raises(schema):
	df = pd.DataFrame({"VALUE": [2025, 2025]})
	with pytest.raises(SchemaError) as e:
		validate_csv("YEAR", df, schema)
	assert "duplicate values" in str(e.value)

def test_duplicate_param_index_raises(schema):
	df = pd.DataFrame({
		"REGION": ["A", "A"],
		"TECHNOLOGY": ["T1", "T1"],
		"YEAR": [2025, 2025],
		"VALUE": [1.0, 2.0]
	})
	with pytest.raises(SchemaError) as e:
		validate_csv("CapitalCost", df, schema)
	assert "duplicate index rows" in str(e.value)

def test_valid_result_csv(schema):
	df = pd.DataFrame({
		"REGION": ["A"],
		"TECHNOLOGY": ["T1"],
		"YEAR": [2025],
		"VALUE": [0.0]
	})
	assert validate_csv("AnnualFixedOperatingCost", df, schema)

def test_param_wrong_value_dtype_raises(schema):
	df = pd.DataFrame({
		"REGION": ["A"],
		"TECHNOLOGY": ["T1"],
		"YEAR": [2025],
		"VALUE": ["not_a_float"]
	})
	with pytest.raises(SchemaError) as e:
		validate_csv("CapitalCost", df, schema)
	assert "float type" in str(e.value)

def test_set_wrong_value_dtype_raises(schema):
	df = pd.DataFrame({"VALUE": [1.0, 2.0]})
	# YEAR expects int, not float
	with pytest.raises(SchemaError) as e:
		validate_csv("YEAR", df, schema)
	assert "integer type" in str(e.value)

def test_param_string_value(schema):
	# FUEL is a set of str, but test a param with str VALUE
	df = pd.DataFrame({
		"REGION": ["A"],
		"FUEL": ["gas"],
		"YEAR": [2025],
		"VALUE": ["foo"]
	})
	# SpecifiedAnnualDemand expects float VALUE, so this should fail
	with pytest.raises(SchemaError) as e:
		validate_csv("SpecifiedAnnualDemand", df, schema)
	assert "float type" in str(e.value)

def test_set_string_value(schema):
	df = pd.DataFrame({"VALUE": ["A", "B"]})
	assert validate_csv("REGION", df, schema)

def test_param_with_nan_index_raises(schema):
	df = pd.DataFrame({
		"REGION": ["A", None],
		"TECHNOLOGY": ["T1", "T2"],
		"YEAR": [2025, 2025],
		"VALUE": [1.0, 2.0]
	})
	with pytest.raises(SchemaError) as e:
		validate_csv("CapitalCost", df, schema)
	assert "missing values" in str(e.value)
	
def test_param_nan_in_required_column_raises(schema):
	df = pd.DataFrame({
		"REGION": ["A", "B"],
		"TECHNOLOGY": ["T1", "T2"],
		"YEAR": [2025, 2025],
		"VALUE": [1.0, np.nan]
    })
	with pytest.raises(SchemaError) as e:
		validate_csv("CapitalCost", df, schema)
	assert "missing values" in str(e.value)

def test_schema_error_on_unknown_name(schema):
	df = pd.DataFrame({"VALUE": [1, 2, 3]})
	with pytest.raises(SchemaError) as e:
		validate_csv("NOT_A_PARAM", df, schema)
	assert "No schema entry" in str(e.value)
