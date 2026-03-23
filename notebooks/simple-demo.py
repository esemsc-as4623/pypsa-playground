import marimo

__generated_with = "0.21.1"
app = marimo.App()


@app.cell
def _():
    import subprocess

    return (subprocess,)


@app.cell
def _():
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), '..')))
    return (os,)


@app.cell
def _():
    from pyoscomp.scenario.components import (
        TopologyComponent,
        TimeComponent,
        DemandComponent,
        SupplyComponent,
        PerformanceComponent,
        EconomicsComponent
    )

    return (
        DemandComponent,
        EconomicsComponent,
        PerformanceComponent,
        SupplyComponent,
        TimeComponent,
        TopologyComponent,
    )


@app.cell
def _(os, subprocess):
    scenario_dir = 'notebooks/demo_output/scenario1'
    os.makedirs(scenario_dir, exist_ok=True)
    setup_dir = os.path.join(scenario_dir, 'setup')
    results_dir = os.path.join(scenario_dir, 'results')
    os.makedirs(setup_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)

    # Use otoole to initialize scenario structure
    subprocess.call(['otoole', 'setup', 'csv', 'notebooks/demo_output/scenario1/setup', '--overwrite'])
    return results_dir, scenario_dir, setup_dir


@app.cell
def _(TopologyComponent, setup_dir):
    topology = TopologyComponent(setup_dir)
    topology.add_nodes(['REGION1'])
    topology.save()
    return (topology,)


@app.cell
def _(TimeComponent, setup_dir):
    time = TimeComponent(setup_dir)
    time.add_time_structure(
        years=[2026],
        seasons={'ALLSEASONS': 365},
        daytypes={'ALLDAYS': 1},
        brackets={'ALLTIMES': 24},
    )
    time.save()
    return (time,)


@app.cell
def _(DemandComponent, setup_dir):
    demand = DemandComponent(setup_dir)
    demand.add_annual_demand('REGION1', 'ELEC', {2026: 100})
    demand.process()
    demand.save()
    return (demand,)


@app.cell
def _(SupplyComponent, setup_dir):
    supply = SupplyComponent(setup_dir)

    supply.add_technology('REGION1', 'GAS_CCGT') \
        .with_operational_life(30) \
        .with_residual_capacity(0) \
        .as_conversion(input_fuel='GAS', output_fuel='ELEC')

    supply.add_technology('REGION1', 'GAS_TURBINE') \
        .with_operational_life(25) \
        .with_residual_capacity(0) \
        .as_conversion(input_fuel='GAS', output_fuel='ELEC')

    supply.save()
    return (supply,)


@app.cell
def _(PerformanceComponent, setup_dir):
    performance = PerformanceComponent(setup_dir)

    performance.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
    performance.set_capacity_factor('REGION1', 'GAS_CCGT', 0.9)
    performance.set_availability_factor('REGION1', 'GAS_CCGT', 1.0)
    performance.set_capacity_to_activity_unit('REGION1', 'GAS_CCGT', 8760)
    performance.set_capacity_limits('REGION1', 'GAS_CCGT',
        max_capacity={2026: 1000 / 8760}, min_capacity=0)

    performance.set_efficiency('REGION1', 'GAS_TURBINE', 0.4)
    performance.set_capacity_factor('REGION1', 'GAS_TURBINE', 0.8)
    performance.set_availability_factor('REGION1', 'GAS_TURBINE', 1.0)
    performance.set_capacity_to_activity_unit('REGION1', 'GAS_TURBINE', 8760)
    performance.set_capacity_limits('REGION1', 'GAS_TURBINE',
        max_capacity={2026: 1000 / 8760}, min_capacity=0)

    performance.process()
    performance.save()
    return (performance,)


@app.cell
def _(EconomicsComponent, setup_dir):
    economics = EconomicsComponent(setup_dir)
    economics.set_discount_rate('REGION1', 0.05)
    economics.set_capital_cost('REGION1', 'GAS_CCGT', 500)
    economics.set_variable_cost('REGION1', 'GAS_CCGT','MODE1', 2)
    economics.set_fixed_cost('REGION1', 'GAS_CCGT', 0)
    economics.set_capital_cost('REGION1', 'GAS_TURBINE', 400)
    economics.set_variable_cost('REGION1', 'GAS_TURBINE', 'MODE1', 5)
    economics.set_fixed_cost('REGION1', 'GAS_TURBINE', 0)
    economics.save()
    return (economics,)


@app.cell
def _(demand, economics, performance, setup_dir, supply, time, topology):
    from pyoscomp.interfaces import ScenarioData

    data = ScenarioData.from_directory(setup_dir, validate=True)
    # Alternatively: 
    data = ScenarioData.from_components(
        topology,
        time,
        demand,
        supply,
        performance,
        economics, validate=True)
    return (data,)


@app.cell
def _():
    # %%capture
    # from pyoscomp.runners.osemosys import OSeMOSYSRunner

    # osm = OSeMOSYSRunner(scenario_dir=scenario_dir,
    #                      use_otoole=True)
    # osm.run()
    return


@app.cell
def _(subprocess):
    #! otoole convert csv datafile demo_output/scenario1/setup demo_output/scenario1/scenario1.txt ../pyoscomp/OSeMOSYS_config.yaml
    subprocess.call(['otoole', 'convert', 'csv', 'datafile', 'notebooks/demo_output/scenario1/setup', 'notebooks/demo_output/scenario1/scenario1.txt', 'pyoscomp/OSeMOSYS_config.yaml'])
    return


@app.cell
def _(subprocess):
    from IPython.utils.capture import capture_output

    with capture_output() as cap:
        #! glpsol -m ../pyoscomp/OSeMOSYS.txt -d demo_output/scenario1/scenario1.txt --wglp demo_output/scenario1/scenario1.glp --write demo_output/scenario1/scenario1.sol
        subprocess.call(['glpsol', '-m', 'pyoscomp/OSeMOSYS.txt', '-d', 'notebooks/demo_output/scenario1/scenario1.txt', '--wglp', 'notebooks/demo_output/scenario1/scenario1.glp', '--write', 'notebooks/demo_output/scenario1/scenario1.sol'])

    # Show output only if not successful
    expected_output = "model has been successfully processed"
    if expected_output not in cap.stdout.lower():
        cap.show()
    return


@app.cell
def _(subprocess):
    #! otoole results glpk csv demo_output/scenario1/scenario1.sol demo_output/scenario1/results datafile demo_output/scenario1/scenario1.txt ../pyoscomp/OSeMOSYS_config.yaml --glpk_model demo_output/scenario1/scenario1.glp
    subprocess.call(['otoole', 'results', 'glpk', 'csv', 'notebooks/demo_output/scenario1/scenario1.sol', 'notebooks/demo_output/scenario1/results', 'datafile', 'notebooks/demo_output/scenario1/scenario1.txt', 'pyoscomp/OSeMOSYS_config.yaml', '--glpk_model', 'notebooks/demo_output/scenario1/scenario1.glp'])
    return


@app.cell
def _(os, results_dir):
    import pandas as pd

    # Load and Display OSeMOSYS Results
    print("\n--- OSeMOSYS Optimization Results ---")
    osemosys_objective = pd.read_csv(os.path.join(results_dir, 'TotalDiscountedCost.csv'))
    print("\nObjective:", osemosys_objective)
    osemosys_total_capacity = pd.read_csv(os.path.join(results_dir, 'TotalCapacityAnnual.csv'))
    print("\nOptimal Capacities (p_nom_opt):\n", osemosys_total_capacity)
    osemosys_total_production = pd.read_csv(os.path.join(results_dir, 'TotalTechnologyAnnualActivity.csv'))
    print("\nTotal Production:\n", osemosys_total_production)
    return


@app.cell
def _(data, os, scenario_dir):
    from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator

    # --- Path B: PyPSA ---
    translator = PyPSAInputTranslator(data)
    network = translator.translate()
    network.export_to_csv_folder(os.path.join(scenario_dir, 'pypsa_network'))
    return (network,)


@app.cell
def _(network):
    # Run PyPSA optimization
    network.optimize(
        solver_name='glpk',
        multi_investment_periods=True
    )
    return


@app.cell
def _(network, results_dir):
    from pyoscomp.translation.pypsa_translator import PyPSAOutputTranslator
    from pyoscomp.translation.osemosys_translator import OSeMOSYSOutputTranslator
    from pyoscomp.interfaces.results import compare

    # --- PyPSA results → ModelResults ---
    pypsa_results = PyPSAOutputTranslator(network).translate()
    print(pypsa_results)
    print()

    # --- OSeMOSYS results → ModelResults ---
    osemosys_results = OSeMOSYSOutputTranslator(results_dir).translate()
    print(osemosys_results)
    return compare, osemosys_results, pypsa_results


@app.cell
def _(compare, osemosys_results, pypsa_results):
    # --- Cross-model comparison ---
    tables = compare(pypsa_results, osemosys_results)

    print("=== Topology Comparison ===")
    print(tables["topology"])
    print()
    print("=== Supply Comparison (Installed Capacity) ===")
    print(tables["supply"])
    print()
    print("=== Objective Comparison ===")
    print(tables["objective"])
    return


if __name__ == "__main__":
    app.run()
