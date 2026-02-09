# tests/test_scenario/test_validation/test_reference.py

import pytest
import pandas as pd
from pyoscomp.scenario.validation.schemas import SchemaError
from pyoscomp.scenario.validation.reference import validate_column_reference, validate_multi_column_reference

def test_valid_column_reference():
    df = pd.DataFrame({'TECHNOLOGY': ['T1', 'T2', 'T3']})
    ref_df = pd.DataFrame({'TECHNOLOGY': ['T1', 'T2', 'T3', 'T4']})
    # Should not raise
    validate_column_reference(df, ref_df, 'TECHNOLOGY', 'TECHNOLOGY')

def test_missing_column_reference():
    df = pd.DataFrame({'TECHNOLOGY': ['T1', 'T2', 'T5']})
    ref_df = pd.DataFrame({'TECHNOLOGY': ['T1', 'T2', 'T3', 'T4']})
    with pytest.raises(SchemaError) as e:
        validate_column_reference(df, ref_df, 'TECHNOLOGY', 'TECHNOLOGY')
    assert 'missing from' in str(e.value)
    assert 'T5' in str(e.value)

def test_valid_multi_column_reference():
    df = pd.DataFrame({'REGION': ['A', 'B'], 'TECHNOLOGY': ['T1', 'T2']})
    ref_df = pd.DataFrame({'REGION': ['A', 'B', 'C'], 'TECHNOLOGY': ['T1', 'T2', 'T3']})
    # All tuples in df exist in ref_df
    ref_tuples = pd.DataFrame({
        'REGION': ['A', 'B', 'C'],
        'TECHNOLOGY': ['T1', 'T2', 'T3']
    })
    validate_multi_column_reference(df, ref_tuples, ['REGION', 'TECHNOLOGY'], ['REGION', 'TECHNOLOGY'])

def test_missing_multi_column_reference():
    df = pd.DataFrame({'REGION': ['A', 'B'], 'TECHNOLOGY': ['T1', 'T5']})
    ref_df = pd.DataFrame({'REGION': ['A', 'B', 'C'], 'TECHNOLOGY': ['T1', 'T2', 'T3']})
    ref_tuples = pd.DataFrame({
        'REGION': ['A', 'B', 'C'],
        'TECHNOLOGY': ['T1', 'T2', 'T3']
    })
    with pytest.raises(SchemaError) as e:
        validate_multi_column_reference(df, ref_tuples, ['REGION', 'TECHNOLOGY'], ['REGION', 'TECHNOLOGY'])
    assert 'missing from' in str(e.value)
    assert "('B', 'T5')" in str(e.value)

def test_empty_df_column_reference():
    df = pd.DataFrame({'TECHNOLOGY': []})
    ref_df = pd.DataFrame({'TECHNOLOGY': ['T1', 'T2']})
    # Should not raise (nothing to check)
    validate_column_reference(df, ref_df, 'TECHNOLOGY', 'TECHNOLOGY')

def test_empty_ref_column_reference():
    df = pd.DataFrame({'TECHNOLOGY': ['T1']})
    ref_df = pd.DataFrame({'TECHNOLOGY': []})
    with pytest.raises(SchemaError) as e:
        validate_column_reference(df, ref_df, 'TECHNOLOGY', 'TECHNOLOGY')
    assert 'missing from' in str(e.value)
    assert 'T1' in str(e.value)

def test_empty_df_multi_column_reference():
    df = pd.DataFrame({'REGION': [], 'TECHNOLOGY': []})
    ref_df = pd.DataFrame({'REGION': ['A'], 'TECHNOLOGY': ['T1']})
    # Should not raise
    validate_multi_column_reference(df, ref_df, ['REGION', 'TECHNOLOGY'], ['REGION', 'TECHNOLOGY'])

def test_empty_ref_multi_column_reference():
    df = pd.DataFrame({'REGION': ['A'], 'TECHNOLOGY': ['T1']})
    ref_df = pd.DataFrame({'REGION': [], 'TECHNOLOGY': []})
    with pytest.raises(SchemaError) as e:
        validate_multi_column_reference(df, ref_df, ['REGION', 'TECHNOLOGY'], ['REGION', 'TECHNOLOGY'])
    assert 'missing from' in str(e.value)
    assert "('A', 'T1')" in str(e.value)

def test_duplicate_values_column_reference():
    df = pd.DataFrame({'TECHNOLOGY': ['T1', 'T1', 'T2']})
    ref_df = pd.DataFrame({'TECHNOLOGY': ['T1', 'T2']})
    # Should not raise (duplicates are ignored)
    validate_column_reference(df, ref_df, 'TECHNOLOGY', 'TECHNOLOGY')

def test_duplicate_tuples_multi_column_reference():
    df = pd.DataFrame({'REGION': ['A', 'A', 'B'], 'TECHNOLOGY': ['T1', 'T1', 'T2']})
    ref_df = pd.DataFrame({'REGION': ['A', 'B'], 'TECHNOLOGY': ['T1', 'T2']})
    # Should not raise (duplicates are ignored)
    validate_multi_column_reference(df, ref_df, ['REGION', 'TECHNOLOGY'], ['REGION', 'TECHNOLOGY'])

def test_custom_error_type_column_reference():
    df = pd.DataFrame({'FUEL': ['gas', 'oil']})
    ref_df = pd.DataFrame({'FUEL': ['gas']})
    with pytest.raises(SchemaError) as e:
        validate_column_reference(df, ref_df, 'FUEL', 'FUEL', error_type="FUEL ReferenceError")
    assert 'FUEL ReferenceError' in str(e.value)
    assert 'oil' in str(e.value)

def test_custom_error_type_multi_column_reference():
    df = pd.DataFrame({'REGION': ['A'], 'TECHNOLOGY': ['T1']})
    ref_df = pd.DataFrame({'REGION': ['A'], 'TECHNOLOGY': ['T2']})
    with pytest.raises(SchemaError) as e:
        validate_multi_column_reference(df, ref_df, ['REGION', 'TECHNOLOGY'], ['REGION', 'TECHNOLOGY'], error_type="REGION-TECH ReferenceError")
    assert 'REGION-TECH ReferenceError' in str(e.value)
    assert "('A', 'T1')" in str(e.value)
