# pyoscomp/scenario/validation/schemas.py

"""
CSV schema validation for OSeMOSYS input/output files.

This module defines expected columns, types, and constraints for all OSeMOSYS CSVs
based on the OSeMOSYS_config.yaml file. It provides validation functions to check
DataFrame structure and types on load/save.

Usage:
	from .schemas import SchemaRegistry, validate_csv
	schema = SchemaRegistry("path/to/OSeMOSYS_config.yaml")
	schema.validate_csv("YEAR.csv", df)
"""

import os
import pandas as pd
import yaml
from typing import Dict, List, Any, Optional

class SchemaError(Exception):
	"""Raised when a CSV file does not conform to the schema."""
	pass

class SchemaRegistry:
	"""
	Loads and stores OSeMOSYS CSV schema from OSeMOSYS_config.yaml.
	Provides methods to retrieve expected columns, types, and constraints.
	"""
	def __init__(self, config_path: str):
		if not os.path.exists(config_path):
			raise FileNotFoundError(f"Schema config file not found: {config_path}")
		with open(config_path, "r") as f:
			self.schema = yaml.safe_load(f)

	def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
		"""
		Get schema definition for a given parameter/set/result name.
		E.g., 'YEAR', 'CapacityFactor', etc.
		"""
		return self.schema.get(name)

	def get_csv_columns(self, name: str) -> List[str]:
		"""
		Return the expected columns for a CSV file of this name.
		For sets: ['VALUE']
		For params/results: indices + ['VALUE']
		"""
		entry = self.get_schema(name)
		if entry is None:
			raise SchemaError(f"No schema entry for '{name}'")
		if entry.get('type') == 'set':
			return ['VALUE']
		indices = entry.get('indices', [])
		return list(indices) + ['VALUE']

	def get_dtype(self, name: str) -> str:
		entry = self.get_schema(name)
		if entry is None:
			raise SchemaError(f"No schema entry for '{name}'")
		return entry.get('dtype', 'float')

	def is_set(self, name: str) -> bool:
		entry = self.get_schema(name)
		return entry is not None and entry.get('type') == 'set'

	def is_param(self, name: str) -> bool:
		entry = self.get_schema(name)
		return entry is not None and entry.get('type') == 'param'

	def is_result(self, name: str) -> bool:
		entry = self.get_schema(name)
		return entry is not None and entry.get('type') == 'result'

def validate_csv(name: str, df: pd.DataFrame, schema: SchemaRegistry):
	"""
	Validate a DataFrame against the OSeMOSYS schema for a given parameter/set/result.

	Parameters
	----------
	name : str
		Name of the parameter/set/result (e.g., 'YEAR', 'CapacityFactor')
	df : pd.DataFrame
		DataFrame to validate
	schema : SchemaRegistry
		Loaded schema registry

	Raises
	------
	SchemaError
		If columns, types, or constraints are violated.
	"""
	entry = schema.get_schema(name)
	if entry is None:
		raise SchemaError(f"No schema entry for '{name}'")
	# Check for required columns
	expected_cols = schema.get_csv_columns(name)
	missing = [col for col in expected_cols if col not in df.columns]
	if missing:
		raise SchemaError(f"CSV for '{name}' missing columns: {missing}. Found: {list(df.columns)}")
	# Check for extra columns
	extra = [col for col in df.columns if col not in expected_cols]
	if extra:
		raise SchemaError(f"CSV for '{name}' has unexpected columns: {extra}. Expected: {expected_cols}")
	# Check dtypes (basic check)
	dtype = entry.get('dtype', 'float')
	if schema.is_set(name):
		# Sets: VALUE column only
		if dtype == 'int' and not pd.api.types.is_integer_dtype(df['VALUE']):
			raise SchemaError(f"Set '{name}' VALUE column must be integer type.")
		if dtype == 'str' and not pd.api.types.is_string_dtype(df['VALUE']):
			raise SchemaError(f"Set '{name}' VALUE column must be string type.")
	else:
		# Params/results: VALUE column type
		if dtype == 'int' and not pd.api.types.is_integer_dtype(df['VALUE']):
			raise SchemaError(f"Param/result '{name}' VALUE column must be integer type.")
		if dtype == 'float':
			if pd.api.types.is_integer_dtype(df['VALUE']):
				df['VALUE'] = df['VALUE'].astype('float')
			if not pd.api.types.is_float_dtype(df['VALUE']):
				raise SchemaError(f"Param/result '{name}' VALUE column must be float type.")
		if dtype == 'str' and not pd.api.types.is_string_dtype(df['VALUE']):
			raise SchemaError(f"Param/result '{name}' VALUE column must be string type.")
	# Check for NaNs in required columns
	if df[expected_cols].isnull().any().any():
		raise SchemaError(f"CSV for '{name}' contains missing values in required columns: {expected_cols}")
	# Check uniqueness for sets
	if schema.is_set(name):
		if df['VALUE'].duplicated().any():
			raise SchemaError(f"Set '{name}' contains duplicate values.")
	# Check for duplicate index rows in params/results
	if not schema.is_set(name):
		idx_cols = expected_cols[:-1]
		if not df.empty and df.duplicated(subset=idx_cols).any():
			raise SchemaError(f"Param/result '{name}' contains duplicate index rows: {idx_cols}")
	# TODO: check value ranges (e.g., for splits sum to 1.0) elsewhere
	return True
