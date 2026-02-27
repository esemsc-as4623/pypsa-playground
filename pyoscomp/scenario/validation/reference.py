# pyoscomp/scenario/validation/crossreference.py

from .schemas import SchemaError

def validate_column_reference(df, reference_df, column, reference_column, error_type="ReferenceError"):
    """
    Validate that all values in df[column] exist in reference_df[reference_column].

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing the referencing column.
    reference_df : pd.DataFrame
        DataFrame containing the reference column.
    column : str
        Name of the column in df to check.
    reference_column : str
        Name of the column in reference_df to check against.
    error_type : str, optional
        Prefix for the error message (default: "ReferenceError").

    Raises
    ------
    SchemaError
        If any value in df[column] is missing from reference_df[reference_column].

    Examples
    --------
    >>> validate_column_reference(supply_df, tech_df, 'TECHNOLOGY', 'TECHNOLOGY')
    """
    missing = set(df[column].unique()) - set(reference_df[reference_column].unique())
    if missing:
        raise SchemaError(
            f"{error_type}: Values in '{column}' missing from '{reference_column}': {sorted(missing)}"
        )

def validate_multi_column_reference(df, reference_df, columns, reference_columns, error_type="ReferenceError"):
    """
    Validate that all unique tuples in df[columns] exist in reference_df[reference_columns].

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing the referencing columns.
    reference_df : pd.DataFrame
        DataFrame containing the reference columns.
    columns : list of str
        List of column names in df to check as a tuple.
    reference_columns : list of str
        List of column names in reference_df to check against as a tuple.
    error_type : str, optional
        Prefix for the error message (default: "ReferenceError").

    Raises
    ------
    SchemaError
        If any tuple in df[columns] is missing from reference_df[reference_columns].

    Examples
    --------
    >>> validate_multi_column_reference(supply_df, tech_df, ['REGION', 'TECHNOLOGY'], ['REGION', 'TECHNOLOGY'])
    """
    df_tuples = set(tuple(row) for row in df[columns].drop_duplicates().values)
    ref_tuples = set(tuple(row) for row in reference_df[reference_columns].drop_duplicates().values)
    missing = df_tuples - ref_tuples
    if missing:
        raise SchemaError(
            f"{error_type}: Tuples in {columns} missing from {reference_columns}: {sorted(missing)}"
        )

# Example usage:
# validate_column_reference(supply_df, tech_df, 'TECHNOLOGY', 'TECHNOLOGY')
# validate_multi_column_reference(supply_df, tech_df, ['REGION', 'TECHNOLOGY'], ['REGION', 'TECHNOLOGY'])