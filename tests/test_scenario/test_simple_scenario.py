"""
Integration test: Reproduce simple-demo.ipynb scenario using pyoscomp API.
"""
import pytest
import pandas as pd
import os

from pyoscomp.scenario.components.topology import TopologyComponent
from pyoscomp.scenario.components.time import TimeComponent
from pyoscomp.scenario.components.demand import DemandComponent
from pyoscomp.scenario.components.supply import SupplyComponent
from pyoscomp.scenario.components.performance import PerformanceComponent
from pyoscomp.scenario.components.economics import EconomicsComponent


class TestSimpleScenario:
    """Test building the scenario from simple-demo.ipynb using pyoscomp."""

    @pytest.fixture
    def scenario_dir(self, tmp_path):
        """Create temporary scenario directory."""
        return str(tmp_path / "test_simple")

    def test_build_simple_scenario(self, scenario_dir):
        """Build simple-demo.ipynb scenario using component APIs."""

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
        assert len(df) == 1

        # Verify YearSplit sums to 1.0
        df = pd.read_csv(os.path.join(scenario_dir, 'YearSplit.csv'))
        assert abs(df['VALUE'].sum() - 1.0) < 1e-6

        # 3. DEMAND
        demand = DemandComponent(scenario_dir)
        demand.add_annual_demand('REGION1', 'ELEC', {2026: 100})
        demand.process()
        demand.save()

        # Verify SpecifiedAnnualDemand.csv
        df = pd.read_csv(os.path.join(
            scenario_dir, 'SpecifiedAnnualDemand.csv'
        ))
        assert len(df) == 1
        assert df.loc[0, 'VALUE'] == 100
        assert df.loc[0, 'FUEL'] == 'ELEC'

        # 4. SUPPLY (technology registry)
        supply = SupplyComponent(scenario_dir)

        supply.add_technology('REGION1', 'GAS_CCGT') \
            .with_operational_life(30) \
            .with_residual_capacity(0) \
            .as_conversion(input_fuel='GAS', output_fuel='ELEC')

        supply.add_technology('REGION1', 'GAS_TURBINE') \
            .with_operational_life(25) \
            .with_residual_capacity(0) \
            .as_conversion(input_fuel='GAS', output_fuel='ELEC')

        supply.save()

        # Verify TECHNOLOGY.csv
        df = pd.read_csv(os.path.join(scenario_dir, 'TECHNOLOGY.csv'))
        assert set(df['VALUE'].tolist()) == {'GAS_CCGT', 'GAS_TURBINE'}

        # Verify OperationalLife.csv (now supply-owned)
        df = pd.read_csv(os.path.join(
            scenario_dir, 'OperationalLife.csv'
        ))
        assert len(df) == 2
        ccgt = df[df['TECHNOLOGY'] == 'GAS_CCGT']
        assert ccgt['VALUE'].iloc[0] == 30

        # 5. PERFORMANCE (operational characteristics)
        performance = PerformanceComponent(scenario_dir)

        performance.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        performance.set_capacity_factor('REGION1', 'GAS_CCGT', 0.9)
        performance.set_availability_factor(
            'REGION1', 'GAS_CCGT', 1.0
        )
        performance.set_capacity_to_activity_unit(
            'REGION1', 'GAS_CCGT', 8760
        )
        performance.set_capacity_limits(
            'REGION1', 'GAS_CCGT',
            max_capacity={2026: 1000 / 8760}, min_capacity=0,
        )

        performance.set_efficiency('REGION1', 'GAS_TURBINE', 0.4)
        performance.set_capacity_factor(
            'REGION1', 'GAS_TURBINE', 0.8
        )
        performance.set_availability_factor(
            'REGION1', 'GAS_TURBINE', 1.0
        )
        performance.set_capacity_to_activity_unit(
            'REGION1', 'GAS_TURBINE', 8760
        )
        performance.set_capacity_limits(
            'REGION1', 'GAS_TURBINE',
            max_capacity={2026: 1000 / 8760}, min_capacity=0,
        )

        performance.process()
        performance.save()

        # Verify InputActivityRatio.csv
        df = pd.read_csv(os.path.join(
            scenario_dir, 'InputActivityRatio.csv'
        ))
        assert len(df) > 0
        ccgt_iar = df[df['TECHNOLOGY'] == 'GAS_CCGT']
        assert abs(ccgt_iar['VALUE'].iloc[0] - 2.0) < 1e-6

        # Verify CapacityFactor.csv
        df = pd.read_csv(os.path.join(
            scenario_dir, 'CapacityFactor.csv'
        ))
        assert len(df) > 0

        # 6. ECONOMICS
        econ = EconomicsComponent(scenario_dir)
        econ.set_discount_rate('REGION1', 0.05)
        econ.set_capital_cost('REGION1', 'GAS_CCGT', 500)
        econ.set_capital_cost('REGION1', 'GAS_TURBINE', 400)
        econ.set_variable_cost('REGION1', 'GAS_CCGT', 'MODE1', 2)
        econ.set_variable_cost('REGION1', 'GAS_TURBINE', 'MODE1', 5)
        econ.set_fixed_cost('REGION1', 'GAS_CCGT', 0)
        econ.set_fixed_cost('REGION1', 'GAS_TURBINE', 0)
        econ.save()

        # Verify DiscountRate.csv
        df = pd.read_csv(os.path.join(
            scenario_dir, 'DiscountRate.csv'
        ))
        assert df.loc[0, 'VALUE'] == 0.05

        # Verify CapitalCost.csv
        df = pd.read_csv(os.path.join(
            scenario_dir, 'CapitalCost.csv'
        ))
        assert len(df) == 2
        ccgt_cost = df[
            df['TECHNOLOGY'] == 'GAS_CCGT'
        ]['VALUE'].iloc[0]
        assert ccgt_cost == 500

        print(f"\u2713 All CSVs created successfully in {scenario_dir}")
