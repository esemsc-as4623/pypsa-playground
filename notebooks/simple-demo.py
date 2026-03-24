import marimo

__generated_with = "0.21.1"
app = marimo.App()


@app.cell
def _():
    import os
    import shutil
    import sys

    sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..")))
    return os, shutil


@app.cell
def _(os):
    # ---- User-tunable constants (edit this cell first) ----
    REGION = "REGION1"
    YEARS = [2026]
    SEASONS = {"ALLSEASONS": 365}
    DAYTYPES = {"ALLDAYS": 1}
    BRACKETS = {"ALLTIMES": 24}

    DEMAND_FUEL = "ELEC"
    DEMAND_BY_YEAR = {2026: 100}

    INPUT_FUEL = "GAS"
    OUTPUT_FUEL = "ELEC"
    MODE = "MODE1"
    CAPACITY_TO_ACTIVITY = 8760
    MAX_ACTIVITY_PER_YEAR = 1000

    TECHNOLOGIES = [
        {
            "name": "GAS_CCGT",
            "life": 30,
            "efficiency": 0.5,
            "capacity_factor": 0.9,
            "availability": 1.0,
            "capital_cost": 500,
            "variable_cost": 2,
            "fixed_cost": 0,
        },
        {
            "name": "GAS_TURBINE",
            "life": 25,
            "efficiency": 0.4,
            "capacity_factor": 0.8,
            "availability": 1.0,
            "capital_cost": 400,
            "variable_cost": 5,
            "fixed_cost": 0,
        },
    ]

    DISCOUNT_RATE = 0.05
    SOLVER = "glpk"
    SCENARIO_NAME = "scenario1"

    SCENARIO_ROOT = os.path.join("notebooks", "demo_output", SCENARIO_NAME)
    SETUP_DIR = os.path.join(SCENARIO_ROOT, "SETUP")
    RESULTS_DIR = os.path.join(SCENARIO_ROOT, "RESULTS")
    TRANSLATION_DIR = os.path.join(SCENARIO_ROOT, "translation_input")
    PYPSA_EXPORT_DIR = os.path.join(SCENARIO_ROOT, "pypsa_network")
    return (
        BRACKETS,
        CAPACITY_TO_ACTIVITY,
        DAYTYPES,
        DEMAND_BY_YEAR,
        DEMAND_FUEL,
        DISCOUNT_RATE,
        INPUT_FUEL,
        MAX_ACTIVITY_PER_YEAR,
        MODE,
        OUTPUT_FUEL,
        PYPSA_EXPORT_DIR,
        REGION,
        RESULTS_DIR,
        SCENARIO_NAME,
        SCENARIO_ROOT,
        SEASONS,
        SETUP_DIR,
        SOLVER,
        TECHNOLOGIES,
        TRANSLATION_DIR,
        YEARS,
    )


@app.cell
def _():
    from pyoscomp.interfaces import (
        ScenarioData,
        ScenarioDataExporter,
        ScenarioDataLoader,
        compare_npv_to_osemosys,
        divergence_analysis,
        validate_input_harmonization,
        validate_pypsa_translation_harmonization,
    )
    from pyoscomp.interfaces.results import compare
    from pyoscomp.runners.osemosys import OSeMOSYSRunner
    from pyoscomp.runners.pypsa import PyPSARunner
    from pyoscomp.scenario.components import (
        TopologyComponent,
        TimeComponent,
        DemandComponent,
        SupplyComponent,
        PerformanceComponent,
        EconomicsComponent,
    )
    from pyoscomp.translation import OSeMOSYSInputTranslator, PyPSAInputTranslator
    from pyoscomp.translation.osemosys_translator import OSeMOSYSOutputTranslator
    from pyoscomp.visualization import HarmonizationVisualizer

    return (
        DemandComponent,
        EconomicsComponent,
        OSeMOSYSInputTranslator,
        OSeMOSYSOutputTranslator,
        OSeMOSYSRunner,
        PerformanceComponent,
        PyPSAInputTranslator,
        PyPSARunner,
        ScenarioData,
        ScenarioDataExporter,
        ScenarioDataLoader,
        SupplyComponent,
        TimeComponent,
        TopologyComponent,
        HarmonizationVisualizer,
        compare,
        compare_npv_to_osemosys,
        divergence_analysis,
        validate_input_harmonization,
        validate_pypsa_translation_harmonization,
    )


@app.cell
def _(RESULTS_DIR, SCENARIO_ROOT, SETUP_DIR, os, shutil):
    if os.path.exists(SCENARIO_ROOT):
        shutil.rmtree(SCENARIO_ROOT)

    os.makedirs(SCENARIO_ROOT, exist_ok=True)
    os.makedirs(SETUP_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs("results", exist_ok=True)

    # Native scenario initialization: component save() calls create the
    # schema-validated CSV files directly in SETUP_DIR.
    print(f"Initialized scenario directories at: {SCENARIO_ROOT}")
    return


@app.cell
def _(
    BRACKETS,
    CAPACITY_TO_ACTIVITY,
    DAYTYPES,
    DEMAND_BY_YEAR,
    DEMAND_FUEL,
    DISCOUNT_RATE,
    DemandComponent,
    EconomicsComponent,
    INPUT_FUEL,
    MAX_ACTIVITY_PER_YEAR,
    MODE,
    OUTPUT_FUEL,
    PerformanceComponent,
    REGION,
    SEASONS,
    SETUP_DIR,
    ScenarioData,
    SupplyComponent,
    TECHNOLOGIES,
    TimeComponent,
    TopologyComponent,
    YEARS,
):
    topology = TopologyComponent(SETUP_DIR)
    time = TimeComponent(SETUP_DIR)

    topology.add_nodes([REGION])
    topology.save()

    time.add_time_structure(
        years=YEARS,
        seasons=SEASONS,
        daytypes=DAYTYPES,
        brackets=BRACKETS,
    )
    time.save()

    # Instantiate dependent components only after core sets are on disk.
    demand = DemandComponent(SETUP_DIR)
    supply = SupplyComponent(SETUP_DIR)
    economics = EconomicsComponent(SETUP_DIR)

    demand.add_annual_demand(REGION, DEMAND_FUEL, DEMAND_BY_YEAR)
    demand.process()
    demand.save()

    for _tech in TECHNOLOGIES:
        (
            supply.add_technology(REGION, _tech["name"])
            .with_operational_life(_tech["life"])
            .with_residual_capacity(0)
            .as_conversion(input_fuel=INPUT_FUEL, output_fuel=OUTPUT_FUEL)
        )
    supply.save()

    performance = PerformanceComponent(SETUP_DIR)

    _max_capacity = {
        _year: MAX_ACTIVITY_PER_YEAR / CAPACITY_TO_ACTIVITY for _year in YEARS
    }
    for _tech in TECHNOLOGIES:
        _name = _tech["name"]
        performance.set_efficiency(REGION, _name, _tech["efficiency"])
        performance.set_capacity_factor(REGION, _name, _tech["capacity_factor"])
        performance.set_availability_factor(REGION, _name, _tech["availability"])
        performance.set_capacity_to_activity_unit(REGION, _name, CAPACITY_TO_ACTIVITY)
        performance.set_capacity_limits(
            REGION,
            _name,
            max_capacity=_max_capacity,
            min_capacity=0,
        )
    performance.process()
    performance.save()

    economics.set_discount_rate(REGION, DISCOUNT_RATE)
    for _tech in TECHNOLOGIES:
        _name = _tech["name"]
        economics.set_capital_cost(REGION, _name, _tech["capital_cost"])
        economics.set_variable_cost(REGION, _name, MODE, _tech["variable_cost"])
        economics.set_fixed_cost(REGION, _name, _tech["fixed_cost"])
    economics.save()

    data = ScenarioData.from_components(
        topology,
        time,
        demand,
        supply,
        performance,
        economics,
        validate=True,
    )
    return (data,)


@app.cell
def _(
    SCENARIO_ROOT,
    ScenarioDataExporter,
    ScenarioDataLoader,
    data,
    os,
):
    interface_export_dir = os.path.join(SCENARIO_ROOT, "interface_export")
    ScenarioDataExporter.to_directory(data, interface_export_dir)

    data_roundtrip = ScenarioDataLoader.from_directory(
        interface_export_dir,
        validate=True,
    )
    print(f"ScenarioData round-trip export dir: {interface_export_dir}")
    return data_roundtrip, interface_export_dir


@app.cell
def _(data_roundtrip, validate_input_harmonization):
    input_report = validate_input_harmonization(data_roundtrip)
    print("=== Input Harmonization Report ===")
    print(input_report.to_frame())
    return (input_report,)


@app.cell
def _(
    OSeMOSYSInputTranslator,
    PYPSA_EXPORT_DIR,
    PyPSAInputTranslator,
    TRANSLATION_DIR,
    data_roundtrip,
    os,
):
    # Translation interface demo: export both model input views.
    os.makedirs(TRANSLATION_DIR, exist_ok=True)
    osemosys_input = OSeMOSYSInputTranslator(data_roundtrip)
    osemosys_input.export_to_csv(TRANSLATION_DIR)

    pypsa_network_preview = PyPSAInputTranslator(data_roundtrip).translate()
    pypsa_network_preview.export_to_csv_folder(PYPSA_EXPORT_DIR)
    return


@app.cell
def _(OSeMOSYSRunner, SCENARIO_NAME, SCENARIO_ROOT, data_roundtrip):
    # Runners interface demo: run OSeMOSYS from scenario directory.
    _ = data_roundtrip
    osemosys_runner = OSeMOSYSRunner(
        scenario_dir=SCENARIO_ROOT,
        scenario_name=SCENARIO_NAME,
        use_otoole=True,
    )
    osemosys_results_dir = osemosys_runner.run()
    print(f"OSeMOSYS results directory: {osemosys_results_dir}")
    return (osemosys_results_dir,)


@app.cell
def _(PyPSARunner, SOLVER, data_roundtrip):
    # Runners interface demo: run PyPSA directly from ScenarioData.
    pypsa_runner = PyPSARunner(data_roundtrip, solver_name=SOLVER)
    network = pypsa_runner.run()
    pypsa_results = pypsa_runner.get_results()
    return network, pypsa_results


@app.cell
def _(
    OSeMOSYSOutputTranslator,
    compare,
    divergence_analysis,
    osemosys_results_dir,
    pypsa_results,
):
    osemosys_results = OSeMOSYSOutputTranslator(osemosys_results_dir).translate()

    print(pypsa_results)
    print()
    print(osemosys_results)

    tables = compare(pypsa_results, osemosys_results)

    print("=== Topology Comparison ===")
    print(tables["topology"])
    print()
    print("=== Supply Comparison (Installed Capacity) ===")
    print(tables["supply"])
    print()
    print("=== Objective Comparison ===")
    print(tables["objective"])

    flags, _ = divergence_analysis(pypsa_results, osemosys_results)
    print()
    print("=== Divergence Analysis ===")
    if not flags:
        print("No divergence flags detected")
    else:
        for _flag in flags:
            print(_flag)
    return flags, osemosys_results, tables


@app.cell
def _(
    data_roundtrip,
    network,
    validate_pypsa_translation_harmonization,
):
    translation_report = validate_pypsa_translation_harmonization(
        data_roundtrip,
        network,
    )
    print("=== PyPSA Translation Harmonization Report ===")
    print(translation_report.to_frame())
    return (translation_report,)


@app.cell
def _(
    HarmonizationVisualizer,
    SCENARIO_ROOT,
    TECHNOLOGIES,
    data_roundtrip,
    flags,
    network,
    osemosys_results,
    os,
    pypsa_results,
):
    visualizer = HarmonizationVisualizer()
    fig_dir = os.path.join(SCENARIO_ROOT, "figures")
    os.makedirs(fig_dir, exist_ok=True)

    cf_technology = TECHNOLOGIES[0]["name"]
    figures = {
        "input_time_structure": visualizer.plot_time_structure(
            data_roundtrip,
            network,
        ),
        "input_demand_profile": visualizer.plot_demand_profile(
            data_roundtrip,
            network,
        ),
        "input_capacity_factor_profile": visualizer.plot_capacity_factor_profile(
            data_roundtrip,
            network,
            cf_technology,
        ),
        "input_capital_cost": visualizer.plot_capital_cost_comparison(
            data_roundtrip,
            network,
        ),
        "translation_dashboard": visualizer.plot_translation_report(
            data_roundtrip,
            network,
        ),
        "output_capacity": visualizer.plot_capacity_comparison(
            pypsa_results,
            osemosys_results,
        ),
        "output_dispatch": visualizer.plot_dispatch_comparison(
            pypsa_results,
            osemosys_results,
        ),
        "output_cost": visualizer.plot_cost_comparison(
            pypsa_results,
            osemosys_results,
        ),
        "output_divergence": visualizer.plot_divergence_summary(flags),
    }

    figure_paths = {}
    for _name, _fig in figures.items():
        _path = os.path.join(fig_dir, f"{_name}.png")
        _fig.savefig(_path, dpi=150, bbox_inches="tight")
        figure_paths[_name] = _path

    print("=== Harmonization Figures Written ===")
    for _name, _path in figure_paths.items():
        print(f"{_name}: {_path}")
    return figure_paths, figures


@app.cell
def _(RESULTS_DIR, compare_npv_to_osemosys, data_roundtrip, network, os):
    import pandas as pd

    osemosys_cost = pd.read_csv(os.path.join(RESULTS_DIR, "TotalDiscountedCost.csv"))
    metric = compare_npv_to_osemosys(
        scenario_data=data_roundtrip,
        network=network,
        osemosys_results={"TotalDiscountedCost": osemosys_cost},
    )

    print("=== Harmonized NPV Parity ===")
    print(f"passed: {metric.passed}")
    print(f"abs error: {metric.observed:.6f}")
    print("pypsa reconstructed NPV:", metric.details.get("pypsa_npv", float("nan")))
    print(
        "osemosys total discounted cost:",
        metric.details.get("osemosys_total_discounted_cost", float("nan")),
    )
    print("component breakdown:")
    print(metric.details.get("pypsa_components", {}))
    return


if __name__ == "__main__":
    app.run()
