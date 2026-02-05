"""
Integration test: Reproduce simple.ipynb scenario using pyoscomp API.
"""
import pytest
import pandas as pd
import os

from pyoscomp.scenario.components.topology import TopologyComponent
from pyoscomp.scenario.components.time import TimeComponent
from pyoscomp.scenario.components.demand import DemandComponent
from pyoscomp.scenario.components.supply import SupplyComponent
from pyoscomp.scenario.components.economics import EconomicsComponent


class TestSimpleScenario:
    """Test building the scenario from simple.ipynb using pyoscomp."""
    
    @pytest.fixture
    def scenario_dir(self, tmp_path):
        """Create temporary scenario directory."""
        return str(tmp_path / "test_simple")
    
    def test_build_simple_scenario(self, scenario_dir):
        """Build simple.ipynb scenario using component APIs."""
        
        os.makedirs(scenario_dir, exist_ok=True)
        
        # 1. TOPOLOGY
        topology = TopologyComponent(scenario_dir)
        topology.add_nodes(['REGION1'])
        topology.save()
        
        # Verify REGION.csv
        df = pd.read_csv(os.path.join(scenario_dir, 'REGION.csv'))
        assert df['VALUE'].tolist() == ['REGION1']
        
        # 2. TIME
        time = TimeComponent(scenario_dir)
        years = [2026]
        seasons = {'ALLSEASONS': 365}
        daytypes = {'ALLDAYS': 1}
        brackets = {'ALLTIMES': 24}
        time.add_time_structure(years, seasons, daytypes, brackets)
        time.save()
        
        # Verify YEAR.csv
        df = pd.read_csv(os.path.join(scenario_dir, 'YEAR.csv'))
        assert df['VALUE'].tolist() == [2026]
        
        # Verify TIMESLICE.csv
        df = pd.read_csv(os.path.join(scenario_dir, 'TIMESLICE.csv'))
        assert len(df) == 1  # One timeslice
        assert 'ALLSEASONS' in df['VALUE'].iloc[0]
        
        # Verify YearSplit sums to 1.0
        df = pd.read_csv(os.path.join(scenario_dir, 'YearSplit.csv'))
        assert abs(df['VALUE'].sum() - 1.0) < 1e-6
        
        # 3. DEMAND
        demand = DemandComponent(scenario_dir)
        demand.add_annual_demand('REGION1', 'ELEC', {2026: 100})
        demand.process()  # Generate profiles
        demand.save()
        
        # Verify SpecifiedAnnualDemand.csv
        df = pd.read_csv(os.path.join(scenario_dir, 'SpecifiedAnnualDemand.csv'))
        assert len(df) == 1
        assert df.loc[0, 'VALUE'] == 100
        assert df.loc[0, 'FUEL'] == 'ELEC'
        
        # 4. SUPPLY
        supply = SupplyComponent(scenario_dir)
        
        # Add technologies
        supply.add_technology('REGION1', 'GAS_CCGT', operational_life=30, 
                              capacity_to_activity_unit=8760)
        supply.add_technology('REGION1', 'GAS_TURBINE', operational_life=25,
                              capacity_to_activity_unit=8760)
        
        # Set conversion (efficiency)
        supply.set_conversion_technology('REGION1', 'GAS_CCGT',
                                         input_fuel='GAS', output_fuel='ELEC',
                                         efficiency=0.5, mode='1', year=2026)
        supply.set_conversion_technology('REGION1', 'GAS_TURBINE',
                                         input_fuel='GAS', output_fuel='ELEC',
                                         efficiency=0.4, mode='1', year=2026)
        
        supply.save()
        
        # Verify TECHNOLOGY.csv was created by supply (via FUEL auto-creation)
        # Note: Supply component may auto-create FUEL.csv from defined_fuels
        
        # Verify OperationalLife.csv
        df = pd.read_csv(os.path.join(scenario_dir, 'OperationalLife.csv'))
        assert len(df) == 2
        ccgt = df[df['TECHNOLOGY'] == 'GAS_CCGT']
        assert ccgt['VALUE'].iloc[0] == 30
        
        # 5. ECONOMICS
        econ = EconomicsComponent(scenario_dir)
        econ.set_discount_rate('REGION1', 0.05)
        econ.set_capital_cost('REGION1', 'GAS_CCGT', 500)
        econ.set_capital_cost('REGION1', 'GAS_TURBINE', 400)
        econ.set_variable_cost('REGION1', 'GAS_CCGT', '1', 2)
        econ.set_variable_cost('REGION1', 'GAS_TURBINE', '1', 5)
        econ.set_fixed_cost('REGION1', 'GAS_CCGT', 0)
        econ.set_fixed_cost('REGION1', 'GAS_TURBINE', 0)
        econ.save()
        
        # Verify DiscountRate.csv
        df = pd.read_csv(os.path.join(scenario_dir, 'DiscountRate.csv'))
        assert df.loc[0, 'VALUE'] == 0.05
        
        # Verify CapitalCost.csv
        df = pd.read_csv(os.path.join(scenario_dir, 'CapitalCost.csv'))
        assert len(df) == 2
        ccgt_cost = df[df['TECHNOLOGY'] == 'GAS_CCGT']['VALUE'].iloc[0]
        assert ccgt_cost == 500
        
        print(f"\u2713 All CSVs created successfully in {scenario_dir}")
    
    def test_csv_column_names(self, scenario_dir):
        """Verify all CSVs use correct column naming convention."""
        
        # Build scenario first
        self.test_build_simple_scenario(scenario_dir)
        
        # Sets should have VALUE column
        set_files = ['YEAR.csv', 'REGION.csv', 'TIMESLICE.csv', 'SEASON.csv', 
                     'DAYTYPE.csv', 'DAILYTIMEBRACKET.csv']
        
        for filename in set_files:
            path = os.path.join(scenario_dir, filename)
            if os.path.exists(path):
                df = pd.read_csv(path)
                assert 'VALUE' in df.columns, f"{filename} missing VALUE column"
        
        # Parameters should have explicit columns
        param_checks = {
            'DiscountRate.csv': ['REGION', 'VALUE'],
            'CapitalCost.csv': ['REGION', 'TECHNOLOGY', 'YEAR', 'VALUE'],
            'VariableCost.csv': ['REGION', 'TECHNOLOGY', 'MODE_OF_OPERATION', 'YEAR', 'VALUE'],
            'SpecifiedAnnualDemand.csv': ['REGION', 'FUEL', 'YEAR', 'VALUE']
        }
        
        for filename, expected_cols in param_checks.items():
            path = os.path.join(scenario_dir, filename)
            if os.path.exists(path):
                df = pd.read_csv(path)
                for col in expected_cols:
                    assert col in df.columns, f"{filename} missing {col} column"
        
        print("\u2713 All CSV column names correct")
