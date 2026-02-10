# pyoscomp/scenario/validation/cross_reference.py

"""
Central cross-component reference validation for scenario CSVs.
"""
import pandas as pd
from pathlib import Path

from .reference import validate_column_reference
from .schemas import SchemaError


def validate_scenario(scenario_dir: str) -> None:
    """
    Validate all cross-component references in scenario CSV files.

    Parameters
    ----------
    scenario_dir : str
        Path to scenario directory containing CSV files.

    Raises
    ------
    SchemaError
        If any reference is invalid.
    FileNotFoundError
        If required set files are missing.

    Examples
    --------
    >>> validate_scenario('/path/to/scenario')
    """
    scenario_path = Path(scenario_dir)

    def load_csv(filename: str, optional=False) -> pd.DataFrame:
        path = scenario_path / filename
        if not path.exists():
            if optional:
                return pd.DataFrame()
            else:
                raise FileNotFoundError(f"Required file {filename} not found in {scenario_dir}")
        return pd.read_csv(path)

    # Step 1: Load all set files (REQUIRED)
    try:
        region_df = load_csv('REGION.csv')
        year_df = load_csv('YEAR.csv')
        technology_df = load_csv('TECHNOLOGY.csv')
    except FileNotFoundError as e:
        raise SchemaError(f"Missing required set file: {e}")

    # Optional sets (may not exist in simple scenarios)
    fuel_df = load_csv('FUEL.csv', optional=True)
    mode_df = load_csv('MODE_OF_OPERATION.csv', optional=True)
    timeslice_df = load_csv('TIMESLICE.csv', optional=True)
    season_df = load_csv('SEASON.csv', optional=True)
    daytype_df = load_csv('DAYTYPE.csv', optional=True)
    dailytimebracket_df = load_csv('DAILYTIMEBRACKET.csv', optional=True)

    # Step 2: Validate parameter files against sets
    param_files = {
        # From TimeComponent
        'YearSplit.csv': [('TIMESLICE', timeslice_df, 'VALUE'), ('YEAR', year_df, 'VALUE')],
        'DaySplit.csv': [('DAILYTIMEBRACKET', dailytimebracket_df, 'VALUE'), ('YEAR', year_df, 'VALUE')],
        # From DemandComponent
        'SpecifiedAnnualDemand.csv': [('REGION', region_df, 'VALUE'), ('FUEL', fuel_df, 'VALUE'), ('YEAR', year_df, 'VALUE')],
        'SpecifiedDemandProfile.csv': [('REGION', region_df, 'VALUE'), ('FUEL', fuel_df, 'VALUE'), ('TIMESLICE', timeslice_df, 'VALUE'), ('YEAR', year_df, 'VALUE')],
        # From SupplyComponent
        'CapitalCost.csv': [('REGION', region_df, 'VALUE'), ('TECHNOLOGY', technology_df, 'VALUE'), ('YEAR', year_df, 'VALUE')],
        'VariableCost.csv': [('REGION', region_df, 'VALUE'), ('TECHNOLOGY', technology_df, 'VALUE'), ('MODE_OF_OPERATION', mode_df, 'VALUE'), ('YEAR', year_df, 'VALUE')],
        'FixedCost.csv': [('REGION', region_df, 'VALUE'), ('TECHNOLOGY', technology_df, 'VALUE'), ('YEAR', year_df, 'VALUE')],
        'InputActivityRatio.csv': [('REGION', region_df, 'VALUE'), ('TECHNOLOGY', technology_df, 'VALUE'), ('FUEL', fuel_df, 'VALUE'), ('MODE_OF_OPERATION', mode_df, 'VALUE'), ('YEAR', year_df, 'VALUE')],
        'OutputActivityRatio.csv': [('REGION', region_df, 'VALUE'), ('TECHNOLOGY', technology_df, 'VALUE'), ('FUEL', fuel_df, 'VALUE'), ('MODE_OF_OPERATION', mode_df, 'VALUE'), ('YEAR', year_df, 'VALUE')],
        'OperationalLife.csv': [('REGION', region_df, 'VALUE'), ('TECHNOLOGY', technology_df, 'VALUE')],
        'CapacityFactor.csv': [('REGION', region_df, 'VALUE'), ('TECHNOLOGY', technology_df, 'VALUE'), ('YEAR', year_df, 'VALUE')],
        'AvailabilityFactor.csv': [('REGION', region_df, 'VALUE'), ('TECHNOLOGY', technology_df, 'VALUE'), ('YEAR', year_df, 'VALUE')],
        'ResidualCapacity.csv': [('REGION', region_df, 'VALUE'), ('TECHNOLOGY', technology_df, 'VALUE'), ('YEAR', year_df, 'VALUE')],
    }

    for param_file, checks in param_files.items():
        param_df = load_csv(param_file, optional=True)
        if param_df.empty:
            continue  # Skip validation if file doesn't exist
        for column, ref_df, ref_column in checks:
            if ref_df.empty:
                continue  # Reference set doesn't exist - skip
            if column not in param_df.columns:
                continue  # Column not in this parameter file
            try:
                validate_column_reference(
                    param_df,
                    ref_df,
                    column,
                    ref_column,
                    error_type=f"{param_file}:{column}"
                )
            except SchemaError as e:
                raise SchemaError(f"Validation failed for {param_file}: {e}")

    # TradeRoute.csv (special: REGION appears twice)
    trade_route = load_csv('TradeRoute.csv', optional=True)
    if not trade_route.empty:
        # Validate REGION columns (assume first two columns are REGIONs)
        region_cols = [col for col in trade_route.columns if col.startswith('REGION')]
        for col in region_cols:
            if not region_df.empty and col in trade_route.columns:
                validate_column_reference(trade_route, region_df, col, 'VALUE', error_type='TradeRoute.csv:REGION')
        # FUEL
        if not fuel_df.empty and 'FUEL' in trade_route.columns:
            validate_column_reference(trade_route, fuel_df, 'FUEL', 'VALUE', error_type='TradeRoute.csv:FUEL')
        # YEAR
        if not year_df.empty and 'YEAR' in trade_route.columns:
            validate_column_reference(trade_route, year_df, 'YEAR', 'VALUE', error_type='TradeRoute.csv:YEAR')
