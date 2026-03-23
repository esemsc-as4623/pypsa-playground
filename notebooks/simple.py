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
    sys.path.append(os.path.abspath(os.path.join(os.pardir)))
    return (os,)


@app.cell
def _(os):
    import shutil

    # Set up a clean test output directory
    TEST_DIR = "test"
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)
    return (TEST_DIR,)


@app.cell
def _(TEST_DIR, os, subprocess):
    import pandas as pd
    import numpy as np

    # Define the scenario directory
    SCENARIO_PATH = os.path.join(TEST_DIR, "scenario1")
    os.makedirs(SCENARIO_PATH, exist_ok=True)

    # Define the results directory
    RESULTS_DIR = "results"
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Helper function to create and display a CSV file from a DataFrame
    def create_csv(df, filename):
        path = os.path.join(SCENARIO_PATH, filename)
        df.to_csv(path, index=False)

    # Use otoole to initialize the scenario structure
    subprocess.call(['otoole', 'setup', 'csv', 'test/scenario1/', '--overwrite'])
    return RESULTS_DIR, create_csv, np, pd


@app.cell
def _(np):
    # User Settings
    HOURS_PER_YEAR = 8760

    # TIME
    years = np.linspace(2026, 2027, num=1, dtype=int)
    seasons = ['ALLSEASONS']
    daytypes = ['ALLDAYS']
    timebrackets = ['ALLTIMES']

    # TOPOLOGY
    regions = ['REGION1']

    # DEMAND
    demand = np.tile([100], len(years)) # MWh per year

    # SUPPLY
    technologies = ['GAS_CCGT', 'GAS_TURBINE']
    residual_capacity = [0, 0] # MW
    max_capacity = [1000/HOURS_PER_YEAR, 1000/HOURS_PER_YEAR] # MW
    min_capacity = [0, 0] # MW

    # PERFORMANCE
    operating_life = [30, 25] # years
    efficiency = [0.5, 0.4] # fraction of input energy converted to output energy
    capacity_factors = [0.9, 0.8] # fraction of max capacity
    availability = [1.0, 1.0] # fraction of year

    # ECONOMICS
    discount_rate = 0.05 
    capital_costs = [500, 400] # $ / MW ($ per unit of extended capacity)
    fixed_costs = [0, 0] # $ / MW / year ($ per unit of installed capacity per year)
    variable_costs = [2, 5] # $ / MWh ($ per unit of activity)

    # STORAGE (NOT IMPLEMENTED IN THIS EXAMPLE)

    # EMISSIONS (NOT IMPLEMENTED IN THIS EXAMPLE)

    # TARGETS (NOT IMPLEMENTED IN THIS EXAMPLE)
    return (
        HOURS_PER_YEAR,
        availability,
        capacity_factors,
        capital_costs,
        daytypes,
        demand,
        discount_rate,
        efficiency,
        fixed_costs,
        max_capacity,
        min_capacity,
        operating_life,
        regions,
        residual_capacity,
        seasons,
        technologies,
        timebrackets,
        variable_costs,
        years,
    )


@app.cell
def _(
    create_csv,
    daytypes,
    pd,
    regions,
    seasons,
    technologies,
    timebrackets,
    years,
):
    # YEAR
    year_df = pd.DataFrame({'VALUE': years})
    create_csv(year_df, 'YEAR.csv')

    # REGION
    region_df = pd.DataFrame({'VALUE': regions})
    create_csv(region_df, 'REGION.csv')

    # TECHNOLOGY
    tech_df = pd.DataFrame({'VALUE': technologies})
    create_csv(tech_df, 'TECHNOLOGY.csv')

    # FUEL
    fuel_df = pd.DataFrame({'VALUE': ['ELEC', 'GAS']})
    create_csv(fuel_df, 'FUEL.csv')

    # MODE_OF_OPERATION
    mode_df = pd.DataFrame({'VALUE': [1]})
    create_csv(mode_df, 'MODE_OF_OPERATION.csv')

    # SEASON
    season_df = pd.DataFrame({'VALUE': seasons})
    create_csv(season_df, 'SEASON.csv')

    # DAYTYPE
    daytype_df = pd.DataFrame({'VALUE': daytypes})
    create_csv(daytype_df, 'DAYTYPE.csv')

    # DAILYTIMEBRACKET
    dailytimebracket_df = pd.DataFrame({'VALUE': timebrackets})
    create_csv(dailytimebracket_df, 'DAILYTIMEBRACKET.csv')

    # TIMESLICE
    timeslices = [f"{s}_{d}_{t}" for s in seasons for d in daytypes for t in timebrackets]
    timeslice_df = pd.DataFrame({'VALUE': timeslices})
    create_csv(timeslice_df, 'TIMESLICE.csv')
    return region_df, timeslice_df, timeslices, year_df


@app.cell
def _(
    HOURS_PER_YEAR,
    availability,
    capacity_factors,
    capital_costs,
    create_csv,
    demand,
    efficiency,
    fixed_costs,
    np,
    pd,
    regions,
    technologies,
    timeslices,
    variable_costs,
    years,
):
    # SpecifiedAnnualDemand
    demand_df = pd.DataFrame({
        'REGION': regions * len(years),
        'FUEL': ['ELEC'] * len(years),
        'YEAR': years,
        'VALUE': demand
    })
    create_csv(demand_df, 'SpecifiedAnnualDemand.csv')

    # SpecifiedDemandProfile
    demand_profile_df = pd.DataFrame({
        'REGION': np.repeat(regions, len(years)*len(timeslices)),
        'FUEL': ['ELEC'] * len(years) * len(timeslices),
        'TIMESLICE': np.tile(timeslices, len(years)),
        'YEAR': np.repeat(years, len(timeslices)),
        'VALUE': [1.0/len(timeslices)] * (len(years) * len(timeslices))
        # Proportion (%) of annual demand
        # CURRENTLY EVENLY DISTRIBUTED ACROSS TIMESLICES
    })
    create_csv(demand_profile_df, 'SpecifiedDemandProfile.csv')

    # CapacityFactor
    capacity_factor_df = pd.DataFrame({
        'REGION': np.repeat(regions, len(technologies)*len(years)*len(timeslices)),
        'TECHNOLOGY': np.repeat(technologies, len(years)*len(timeslices)),
        'TIMESLICE': np.tile(timeslices, len(technologies) * len(years)),
        'YEAR': np.tile(np.repeat(years, len(timeslices)), len(technologies)),
        'VALUE': np.repeat(capacity_factors, len(years)*len(timeslices))
        # Capacity factors (%) for each technology across all timeslices and years
        # CURRENTLY ONE VALUE PER TECHNOLOGY
    })
    create_csv(capacity_factor_df, 'CapacityFactor.csv')

    # AvailabilityFactor
    availability_factor_df = pd.DataFrame({
        'REGION': np.repeat(regions, len(technologies)*len(years)),
        'TECHNOLOGY': np.repeat(technologies, len(years)),
        'YEAR': np.array([years] * len(technologies)).flatten(),
        'VALUE': np.repeat(availability, len(years))
        # Availability factors (%) for each technology and year
        # CURRENTLY ONE VALUE PER TECHNOLOGY
    })
    create_csv(availability_factor_df, 'AvailabilityFactor.csv')

    # CapitalCost
    capital_cost_df = pd.DataFrame({
        'REGION': np.repeat(regions, len(technologies)*len(years)),
        'TECHNOLOGY': np.repeat(technologies, len(years)),
        'YEAR': np.array([years] * len(technologies)).flatten(),
        'VALUE': np.repeat(capital_costs, len(years))
        # Capital cost [$ per MWh]
        # CURRENTLY ONE VALUE PER TECHNOLOGY
    })
    create_csv(capital_cost_df, 'CapitalCost.csv')

    # FixedCost
    fixed_cost_df = pd.DataFrame({
        'REGION': np.repeat(regions, len(technologies)*len(years)),
        'TECHNOLOGY': np.repeat(technologies, len(years)),
        'YEAR': np.array([years] * len(technologies)).flatten(),
        'VALUE': np.repeat(fixed_costs, len(years))
        # Fixed cost [$ per MWh per year]
        # CURRENTLY ONE VALUE PER TECHNOLOGY
    })
    create_csv(fixed_cost_df, 'FixedCost.csv')

    # CapacityToActivityUnit
    capacity_to_activity_df = pd.DataFrame({
        'REGION': np.repeat(regions, len(technologies)),
        'TECHNOLOGY': technologies,
        'VALUE': [HOURS_PER_YEAR] * len(technologies)
        # Energy that would be produced when one unit of capacity is fully used in one year
        # (MWh / capacity unit) * 8760 hours per year
        # CURRENTLY ONE VALUE PER TECHNOLOGY
        # (this explicitly sets 1 capacity unit = 1 MW, 1 activity unit = 1 hour at full capacity)
    })
    create_csv(capacity_to_activity_df, 'CapacityToActivityUnit.csv')

    # VariableCost
    variable_cost_df = pd.DataFrame({
        'REGION': np.repeat(regions, len(technologies)*len(years)),
        'TECHNOLOGY': np.repeat(technologies, len(years)),
        'MODE_OF_OPERATION': [1] * len(technologies)*len(years),
        'YEAR': np.array([years] * len(technologies)).flatten(),
        'VALUE': np.repeat(variable_costs, len(years))
        # Variable cost [$ per activity unit]
        # (since 1 activity unit = 1 hour at full capacity, this is $ / hour)
        # CURRENTLY ONE VALUE PER TECHNOLOGY
    })
    create_csv(variable_cost_df, 'VariableCost.csv')

    # InputActivityRatio
    input_ratio_df = pd.DataFrame({
        'REGION': np.repeat(regions, len(technologies)*len(years)),
        'TECHNOLOGY': np.repeat(technologies, len(years)),
        'FUEL': np.repeat(['GAS'], len(technologies)*len(years)),
        'MODE_OF_OPERATION': [1] * len(technologies)*len(years),
        'YEAR': np.array([years] * len(technologies)).flatten(),
        'VALUE': np.repeat([1.0]/np.array(efficiency), len(years))
        # MWh fuel / MWh electricity
        # CURRENTLY ONE VALUE PER TECHNOLOGY
    })
    create_csv(input_ratio_df, 'InputActivityRatio.csv')

    # OutputActivityRatio
    output_ratio_df = pd.DataFrame({
        'REGION': np.repeat(regions, len(technologies)*len(years)),
        'TECHNOLOGY': np.repeat(technologies, len(years)),
        'FUEL': np.repeat(['ELEC'], len(technologies)*len(years)),
        'MODE_OF_OPERATION': [1] * len(technologies)*len(years),
        'YEAR': np.array([years] * len(technologies)).flatten(),
        'VALUE': np.repeat([1.0]*len(technologies), len(years))
        # MWh electricity / MWh electricity
        # CURRENTLY ONE VALUE PER TECHNOLOGY
    })
    create_csv(output_ratio_df, 'OutputActivityRatio.csv')
    return demand_df, demand_profile_df


@app.cell
def _(create_csv, daytypes, np, pd, seasons, timebrackets, timeslices, years):
    # Conversionls - maps timeslices to seasons
    conv_ls_rows = []
    for ts in timeslices:
        for s in seasons:
            conv_ls_rows.append({
                'TIMESLICE': ts,
                'SEASON': s,
                'VALUE': 1 if ts.startswith(s) else 0
            })
    conv_ls_df = pd.DataFrame(conv_ls_rows)
    create_csv(conv_ls_df, 'Conversionls.csv')

    # Conversionld - maps timeslices to daytypes
    conv_ld_rows = []
    for ts in timeslices:
        for d in daytypes:
            conv_ld_rows.append({
                'TIMESLICE': ts,
                'DAYTYPE': d,
                'VALUE': 1 if f"_{d}_" in ts else 0
            })
    conv_ld_df = pd.DataFrame(conv_ld_rows)
    create_csv(conv_ld_df, 'Conversionld.csv')

    # Conversionlh - maps timeslices to dailytimebrackets
    conv_lh_rows = []
    for ts in timeslices:
        for h in timebrackets:
            conv_lh_rows.append({
                'TIMESLICE': ts,
                'DAILYTIMEBRACKET': h,
                'VALUE': 1 if ts.endswith(h) else 0
            })
    conv_lh_df = pd.DataFrame(conv_lh_rows)
    create_csv(conv_lh_df, 'Conversionlh.csv')

    # DaysInDayType - days per season/daytype/year combination
    days_in_day_type_df = pd.DataFrame({
        'SEASON': np.tile(np.repeat(seasons, len(daytypes)), len(years)),
        'DAYTYPE': np.tile(daytypes, len(seasons) * len(years)),
        'YEAR': np.repeat(years, len(seasons) * len(daytypes)),
        'VALUE': [365 / len(daytypes) / len(seasons)] * (len(years) * len(seasons) * len(daytypes))
        # LEAP YEARS?
        # np.array([365] * len(years)) + (years % 4 == 0)
    })
    create_csv(days_in_day_type_df, 'DaysInDayType.csv')

    # DaySplit - fraction of year for each timebracket per year
    day_split_df = pd.DataFrame({
        'DAILYTIMEBRACKET': np.tile(timebrackets, len(years)),
        'YEAR': np.repeat(years, len(timebrackets)),
        'VALUE': [1 / (len(timebrackets) * 365)] * (len(years) * len(timebrackets))
        # Length of one timebracket in one specific day as a fraction of the year
    })
    create_csv(day_split_df, 'DaySplit.csv')

    # YearSplit - fraction of year for each timeslice per year
    year_split_df = pd.DataFrame({
        'TIMESLICE': np.tile(timeslices, len(years)),
        'YEAR': np.repeat(years, len(timeslices)),
        'VALUE': [1 / len(timeslices)] * (len(years) * len(timeslices))
        # Duration of a modelled timeslice as a fraction of the year
    })
    create_csv(year_split_df, 'YearSplit.csv')
    return (year_split_df,)


@app.cell
def _(
    create_csv,
    discount_rate,
    max_capacity,
    min_capacity,
    np,
    operating_life,
    pd,
    regions,
    residual_capacity,
    technologies,
    years,
):
    # OperationalLife
    op_life_df = pd.DataFrame({
        'REGION': regions * len(technologies),
        'TECHNOLOGY': technologies,
        'VALUE': operating_life
    })
    create_csv(op_life_df, 'OperationalLife.csv')

    # ResidualCapacity
    residual_cap_df = pd.DataFrame({
        'REGION': regions * len(technologies)*len(years),
        'TECHNOLOGY': np.repeat(technologies, len(years)),
        'YEAR': np.array([years] * len(technologies)).flatten(),
        'VALUE': np.repeat(residual_capacity, len(years))
    })
    create_csv(residual_cap_df, 'ResidualCapacity.csv')

    # TotalAnnualMaxCapacity
    total_max_cap_df = pd.DataFrame({
        'REGION': regions * len(technologies) * len(years),
        'TECHNOLOGY': np.repeat(technologies, len(years)),
        'YEAR': np.array([years] * len(technologies)).flatten(),
        'VALUE': np.repeat(max_capacity, len(years))
    })
    create_csv(total_max_cap_df, 'TotalAnnualMaxCapacity.csv')

    # TotalAnnualMinCapacity
    total_min_cap_df = pd.DataFrame({
        'REGION': regions * len(technologies)*len(years),
        'TECHNOLOGY': np.repeat(technologies, len(years)),
        'YEAR': np.array([years] * len(technologies)).flatten(),
        'VALUE': np.repeat(min_capacity, len(years))
    })
    create_csv(total_min_cap_df, 'TotalAnnualMinCapacity.csv')

    # Discount Rate
    discount = pd.DataFrame({
        'REGION': regions,
        'VALUE': [discount_rate] * len(regions)
        # CURRENTLY ONE VALUE PER REGION
    })
    create_csv(discount, 'DiscountRate.csv')
    return


@app.cell
def _(subprocess):
    #! otoole convert csv datafile test/scenario1 test/scenario1.txt pyoscomp/OSeMOSYS_config.yaml
    subprocess.call(['otoole', 'convert', 'csv', 'datafile', 'test/scenario1', 'test/scenario1.txt', 'pyoscomp/OSeMOSYS_config.yaml'])
    return


@app.cell
def _(subprocess):
    from IPython.utils.capture import capture_output

    with capture_output() as cap:
        #! glpsol -m ../pyoscomp/OSeMOSYS.txt -d test/scenario1.txt --wglp test/scenario1.glp --write test/scenario1.sol
        subprocess.call(['glpsol', '-m', 'pyoscomp/OSeMOSYS.txt', '-d', 'test/scenario1.txt', '--wglp', 'test/scenario1.glp', '--write', 'test/scenario1.sol'])

    # Show output only if not successful
    expected_output = "model has been successfully processed"
    if expected_output not in cap.stdout.lower():
        cap.show()
    return


@app.cell
def _(subprocess):
    #! otoole results glpk csv test/scenario1.sol results datafile test/scenario1.txt ../pyoscomp/OSeMOSYS_config.yaml --glpk_model test/scenario1.glp
    subprocess.call(['otoole', 'results', 'glpk', 'csv', 'test/scenario1.sol', 'results', 'datafile', 'test/scenario1.txt', 'pyoscomp/OSeMOSYS_config.yaml', '--glpk_model', 'test/scenario1.glp'])
    return


@app.cell
def _(
    HOURS_PER_YEAR,
    TEST_DIR,
    availability,
    capacity_factors,
    capital_costs,
    demand_df,
    demand_profile_df,
    discount_rate,
    efficiency,
    fixed_costs,
    max_capacity,
    min_capacity,
    np,
    operating_life,
    os,
    pd,
    region_df,
    residual_capacity,
    technologies,
    timeslice_df,
    variable_costs,
    year_df,
    year_split_df,
    years,
):
    # Create the equivalent PyPSA network
    import pypsa
    from pypsa.common import annuity

    # Initialize the network
    n = pypsa.Network()

    # Add carriers
    n.add("Carrier", "GAS")
    n.add("Carrier", "AC") # ELEC

    # Add the buses
    n.add("Bus", region_df['VALUE'].tolist(), carrier="AC")

    # Set investment periods
    periods = year_df['VALUE'].tolist()
    n.set_investment_periods(periods)

    # Set investment period weightings
    # Calculate the duration each period represents
    period_durations = np.diff(years, prepend=years[0])  # Years from start for each period
    investment_period_weightings = pd.DataFrame(index=years)
    investment_period_weightings['years'] = period_durations
    investment_period_weightings['objective'] = [
        1 / ((1 + discount_rate) ** (y - years[0])) for y in years
    ]
    n.investment_period_weightings = investment_period_weightings

    # Set snapshots
    timesteps = timeslice_df['VALUE'].tolist()
    snapshots = pd.MultiIndex.from_product([periods, timesteps], names=['period', 'timestep'])
    n.set_snapshots(snapshots)

    # Set snapshot weightings
    year_split_df_temp = year_split_df.copy()
    year_split_df_temp['period'] = year_split_df_temp['YEAR']
    year_split_df_temp['timestep'] = year_split_df_temp['TIMESLICE']
    hours_per_snapshot = year_split_df_temp.set_index(['period', 'timestep'])['VALUE'] * HOURS_PER_YEAR
    hours_per_snapshot = hours_per_snapshot.reindex(snapshots)
    n.snapshot_weightings['objective'] = hours_per_snapshot
    n.snapshot_weightings['generators'] = hours_per_snapshot

    # Set up demand
    demand_pypsa = pd.merge(
        demand_df,
        demand_profile_df,
        on=['REGION', 'FUEL', 'YEAR'],
        suffixes=('_annual', '_profile')
    )
    # Energy per snapshot = Annual Demand × Demand Profile
    demand_pypsa['energy_MWh'] = demand_pypsa['VALUE_annual'] * demand_pypsa['VALUE_profile']
    demand_pypsa['period'] = demand_pypsa['YEAR']
    demand_pypsa['timestep'] = demand_pypsa['TIMESLICE']

    # Power = Energy / Hours
    energy_series = demand_pypsa.set_index(['period', 'timestep'])['energy_MWh']
    power = energy_series.divide(hours_per_snapshot).reindex(snapshots)

    n.add("Load",
          "demand",
          bus="REGION1",
          p_set=power)  # MW

    # Add generators
    p_max_pu = pd.DataFrame(index=snapshots)

    for idx, tech in enumerate(technologies):
        # Calculate annualized capital cost (matching OSeMOSYS CapitalCost + FixedCost)
        annualized_capital_cost = capital_costs[idx] * annuity(discount_rate, operating_life[idx]) + fixed_costs[idx]

        # For PyPSA multi-investment periods, capital_cost should be annualized
        n.add("Generator",
              tech,
              bus="REGION1",
              carrier="GAS",
              p_nom=residual_capacity[idx],  # Existing capacity (MW)
              p_nom_max=max_capacity[idx],   # Maximum total capacity (MW)
              p_nom_min=min_capacity[idx],   # Minimum total capacity (MW)
              p_nom_extendable=True,         # Allow capacity expansion
              capital_cost=annualized_capital_cost,  # Annualized capital + fixed cost ($/MW/year)
              marginal_cost=variable_costs[idx],     # Variable cost ($/MWh)
              efficiency=efficiency[idx],            # Conversion efficiency
              lifetime=operating_life[idx],          # Asset lifetime (years)
              build_year=years[0]                    # First period when new capacity can be built
              )

        # Set capacity factor × availability factor for time-dependent availability
        # In OSeMOSYS: TotalActivityUpperLimit = TotalCapacity × CapacityFactor × AvailabilityFactor
        p_max_pu[tech] = capacity_factors[idx] * availability[idx]

    n.generators_t.p_max_pu = p_max_pu

    # Print network components to verify
    print("--- PyPSA Network Components ---")
    print("\nGenerators:\n", n.generators[['p_nom', 'p_nom_min', 'p_nom_max', 'capital_cost', 'marginal_cost', 'efficiency', 'lifetime']])
    print("\nInvestment Period Weightings:\n", n.investment_period_weightings)
    print("\nTime-varying load (first 5 snapshots):\n", n.loads_t.p_set.head())
    print("\nTime-varying generator availability (first 5 snapshots):\n", n.generators_t.p_max_pu.head())
    print("\nSnapshot Weightings (first 5):\n", n.snapshot_weightings.head())

    n.export_to_csv_folder(os.path.join(TEST_DIR, 'scenario1'))
    return (n,)


@app.cell
def _(n):
    # Run the PyPSA optimization
    status = n.optimize(solver_name='glpk', compute_infeasibilities=True, multi_investment_periods=True)
    return


@app.cell
def _(RESULTS_DIR, os, pd):
    # Load and Display OSeMOSYS Results
    print("\n--- OSeMOSYS Optimization Results ---")
    osemosys_objective = pd.read_csv(os.path.join(RESULTS_DIR, 'TotalDiscountedCost.csv'))
    print("\nObjective:", osemosys_objective)
    osemosys_total_capacity = pd.read_csv(os.path.join(RESULTS_DIR, 'TotalCapacityAnnual.csv'))
    print("\nOptimal Capacities (p_nom_opt):\n", osemosys_total_capacity)
    osemosys_total_production = pd.read_csv(os.path.join(RESULTS_DIR, 'TotalTechnologyAnnualActivity.csv'))
    print("\nTotal Production:\n", osemosys_total_production)
    return


@app.cell
def _(HOURS_PER_YEAR, n):
    # Display PyPSA Results
    print("\n--- PyPSA Optimization Results ---")
    print("\nObjective:", n.objective)
    print("\nOptimal Capacities (p_nom_opt):\n", n.generators.p_nom_opt)
    print("\nTotal Production (p * HOURS_PER_YEAR):\n", n.generators_t.p * HOURS_PER_YEAR)
    return


@app.cell
def _(
    RESULTS_DIR,
    capital_costs,
    demand,
    discount_rate,
    operating_life,
    os,
    pd,
    technologies,
    variable_costs,
    years,
):
    from IPython.display import Markdown, display

    # Read OSeMOSYS results
    new_capacity = pd.read_csv(os.path.join(RESULTS_DIR, 'NewCapacity.csv'))
    capital_investment = pd.read_csv(os.path.join(RESULTS_DIR, 'CapitalInvestment.csv'))
    discounted_capital = pd.read_csv(os.path.join(RESULTS_DIR, 'DiscountedCapitalInvestment.csv'))
    salvage_value = pd.read_csv(os.path.join(RESULTS_DIR, 'SalvageValue.csv'))
    discounted_salvage = pd.read_csv(os.path.join(RESULTS_DIR, 'DiscountedSalvageValue.csv'))
    annual_var_cost = pd.read_csv(os.path.join(RESULTS_DIR, 'AnnualVariableOperatingCost.csv'))
    discounted_op_cost = pd.read_csv(os.path.join(RESULTS_DIR, 'DiscountedOperationalCost.csv'))
    total_cost = pd.read_csv(os.path.join(RESULTS_DIR, 'TotalDiscountedCost.csv'))

    # Get values for first technology (cheapest one selected)
    tech_new_cap = new_capacity[new_capacity['VALUE'] > 0].iloc[0] if len(new_capacity[new_capacity['VALUE'] > 0]) > 0 else new_capacity.iloc[0]
    tech_name = tech_new_cap['TECHNOLOGY']
    new_cap_value = tech_new_cap['VALUE']

    tech_capital_inv = capital_investment[capital_investment['TECHNOLOGY'] == tech_name]['VALUE'].iloc[0]
    tech_disc_capital = discounted_capital[discounted_capital['TECHNOLOGY'] == tech_name]['VALUE'].iloc[0]
    tech_salvage = salvage_value[salvage_value['TECHNOLOGY'] == tech_name]['VALUE'].iloc[0] if len(salvage_value[salvage_value['TECHNOLOGY'] == tech_name]) > 0 else 0
    tech_disc_salvage = discounted_salvage[discounted_salvage['TECHNOLOGY'] == tech_name]['VALUE'].iloc[0] if len(discounted_salvage[discounted_salvage['TECHNOLOGY'] == tech_name]) > 0 else 0
    tech_var_cost = annual_var_cost[annual_var_cost['TECHNOLOGY'] == tech_name]['VALUE'].iloc[0] if len(annual_var_cost[annual_var_cost['TECHNOLOGY'] == tech_name]) > 0 else 0
    tech_disc_op_cost = discounted_op_cost[discounted_op_cost['TECHNOLOGY'] == tech_name]['VALUE'].iloc[0]
    total_disc_cost = total_cost['VALUE'].iloc[0]

    # Get technology parameters
    tech_idx = technologies.index(tech_name)
    tech_cap_cost = capital_costs[tech_idx]
    tech_var_cost_unit = variable_costs[tech_idx]
    tech_op_life = operating_life[tech_idx]

    # Calculate salvage value formula components
    if tech_op_life > len(years):
        salvage_numerator = ((1 + discount_rate)**len(years) - 1)
        salvage_denominator = ((1 + discount_rate)**tech_op_life - 1)
        salvage_fraction = 1 - (salvage_numerator / salvage_denominator)
    else:
        salvage_fraction = 0

    markdown_text = f"""### OSeMOSYS: NPV with Salvage Value

    OSeMOSYS computes Net Present Value of all costs, crediting back the residual value of assets that outlive the model horizon.

    **Inputs:**
    - Technology: {tech_name}
    - NewCapacity = {new_cap_value:.6f} MW
    - CapitalCost = {tech_cap_cost} $/MW
    - VariableCost = {tech_var_cost_unit} $/MWh
    - OperationalLife = {tech_op_life} years
    - DiscountRate = {discount_rate}
    - Model Period = {len(years)} year(s) ({years[0]} to {years[-1]})
    - Annual Demand = {demand[0]} MWh

    **1. Capital Investment:**
    - CapitalInvestment = {tech_cap_cost} × {new_cap_value:.6f} = ${tech_capital_inv:.2f}
    - DiscountedCapitalInvestment = ${tech_capital_inv:.2f} / (1.05)^0 = ${tech_disc_capital:.2f}

    **2. Salvage Value (asset life extends beyond model):**
    - Since ({years[0]} + {tech_op_life} - 1) = {years[0] + tech_op_life - 1} > {years[-1]}, salvage applies.
    - SV = {tech_capital_inv:.2f} × (1 - [{salvage_numerator:.4f}] / [{salvage_denominator:.4f}])
    - SV = {tech_capital_inv:.2f} × {salvage_fraction:.6f} = ${tech_salvage:.2f}
    - DiscountedSalvageValue = {tech_salvage:.2f} / (1.05)^{len(years)} = ${tech_disc_salvage:.2f}

    **3. Operating Cost:**
    - OperatingCost = {demand[0]} MWh × {tech_var_cost_unit} $/MWh = ${tech_var_cost:.2f}
    - DiscountedOperatingCost = ${tech_disc_op_cost:.2f} (mid-year discounting)

    **4. Total Discounted Cost:**
    - = DiscountedCapital + DiscountedOperating - DiscountedSalvage
    - = ${tech_disc_capital:.2f} + ${tech_disc_op_cost:.2f} - ${tech_disc_salvage:.2f}
    - = **${total_disc_cost:.2f}**
    """

    display(Markdown(markdown_text))
    return (
        Markdown,
        display,
        tech_disc_capital,
        tech_disc_op_cost,
        tech_disc_salvage,
        tech_name,
        total_disc_cost,
    )


@app.cell
def _(Markdown, display, n, tech_name, years):
    pypsa_gen = n.generators.loc[tech_name]
    pypsa_new_cap = pypsa_gen['p_nom_opt'] - pypsa_gen['p_nom']
    # Get PyPSA results for the same technology
    pypsa_capital_cost = pypsa_gen['capital_cost']
    pypsa_marginal_cost = pypsa_gen['marginal_cost']
    pypsa_production = (n.generators_t.p[tech_name] * n.snapshot_weightings['generators']).sum()
    invest_weight = n.investment_period_weightings['objective'].iloc[0]
    pypsa_op_cost = pypsa_marginal_cost * pypsa_production
    # Calculate production for this generator
    pypsa_capital_inv = pypsa_capital_cost * pypsa_new_cap * invest_weight
    pypsa_total_cost = pypsa_capital_inv + pypsa_op_cost
    # Investment period weighting for first year
    markdown_text_1 = f"### PyPSA: Multi-investment Period Cost Accounting\n\nWhen using `multi_investment_periods=True` with annualized capital costs, PyPSA computes costs as follows:\n\n**Inputs:**\n- Technology: {tech_name}\n- NewCapacity = {pypsa_new_cap:.6f} MW\n- AnnualizedCapitalCost = {pypsa_capital_cost:.2f} $/MW/year\n- MarginalCost = {pypsa_marginal_cost} $/MWh\n- Production = {pypsa_production:.2f} MWh\n- investment_period_weightings['objective'] = {invest_weight:.2f} (for {years[0]})\n\n**1. Annualized Capital Investment:**\n- AnnualizedCapitalCost × NewCapacity × InvestmentPeriodWeight\n- = {pypsa_capital_cost:.2f} × {pypsa_new_cap:.6f} × {invest_weight:.2f}\n- = **${pypsa_capital_inv:.2f}**\n\n**2. Operating Cost:**\n- MarginalCost × Energy × InvestmentPeriodWeight\n- = {pypsa_marginal_cost} × {pypsa_production:.2f} × {invest_weight:.2f}\n- = **${pypsa_op_cost:.2f}**\n\n**3. Total:**\n- = ${pypsa_capital_inv:.2f} + ${pypsa_op_cost:.2f}\n- = **${pypsa_total_cost:.2f}**\n"
    # Calculate costs
    display(Markdown(markdown_text_1))
    return pypsa_capital_inv, pypsa_op_cost, pypsa_total_cost


@app.cell
def _(
    Markdown,
    display,
    pypsa_capital_inv,
    pypsa_op_cost,
    pypsa_total_cost,
    tech_disc_capital,
    tech_disc_op_cost,
    tech_disc_salvage,
    total_disc_cost,
):
    capital_diff = pypsa_capital_inv - tech_disc_capital
    salvage_diff = 0 - tech_disc_salvage
    # Calculate differences
    op_cost_diff = pypsa_op_cost - tech_disc_op_cost
    total_diff = pypsa_total_cost - total_disc_cost  # PyPSA has no salvage
    markdown_text_2 = f'### Reconciling the Difference\n\n| Component | PyPSA | OSeMOSYS | Difference |\n| --------- | ----: | -------: | ---------: |\n| Capital Investment | ${pypsa_capital_inv:.2f} | ${tech_disc_capital:.2f} | ${capital_diff:+.2f} |\n| Salvage Value Credit | $0.00 | −${tech_disc_salvage:.2f} | ${salvage_diff:+.2f} |\n| Operating Cost | ${pypsa_op_cost:.2f} | ${tech_disc_op_cost:.2f} | ${op_cost_diff:+.2f} |\n| **Total** | **${pypsa_total_cost:.2f}** | **${total_disc_cost:.2f}** | **${total_diff:+.2f}** |\n\n**Key Differences:**\n1. **Capital Cost Treatment:** \n   - OSeMOSYS: One-time capital investment (${tech_disc_capital:.2f}) with salvage value credit (−${tech_disc_salvage:.2f})\n   - PyPSA: Annualized capital cost (${pypsa_capital_inv:.2f}/year) with no salvage value\n\n2. **Discounting:**\n   - OSeMOSYS: Applies present value discounting throughout\n   - PyPSA: Uses investment period weightings for multi-year models\n\n3. **Net Effect:** The difference of ${total_diff:.2f} reflects the different cost accounting methodologies.\n'
    display(Markdown(markdown_text_2))
    return


@app.cell
def _(Markdown, display, n, tech_name):
    gen_capacity = n.generators.loc[tech_name, 'p_nom_opt']
    gen_p_max_pu = n.generators_t.p_max_pu[tech_name].iloc[0]
    # Calculate curtailment for the selected technology
    total_hours = n.snapshot_weightings['generators'].sum()
    max_available = gen_capacity * gen_p_max_pu * total_hours  # Assuming constant across snapshots
    actual_generation = (n.generators_t.p[tech_name] * n.snapshot_weightings['generators']).sum()
    curtailment = max_available - actual_generation
    # Maximum available generation
    total_load = (n.loads_t.p_set['demand'] * n.snapshot_weightings['generators']).sum()
    markdown_text_3 = f'### PyPSA: Curtailment Analysis\n\n**Technology: {tech_name}**\n\n| Metric | Value |\n| ------ | ----: |\n| Optimal Capacity | {gen_capacity:.6f} MW |\n| Capacity Factor (p_max_pu) | {gen_p_max_pu:.2f} |\n| Total Hours | {total_hours:.0f} |\n| Maximum Available Generation | {gen_capacity:.6f} × {gen_p_max_pu:.2f} × {total_hours:.0f} = {max_available:.5f} MWh |\n| Actual Supply | {actual_generation:.5f} MWh |\n| Curtailment | {curtailment:.5f} MWh |\n| Total Load | {total_load:.5f} MWh |\n\n**Curtailment Definition:**\n```\nCurtailment = Available Generation − Actual Generation\n            = p_nom_opt × p_max_pu × hours − actual_generation\n            = {curtailment:.6f} MWh\n```\n\n**Analysis:**\n- Curtailment percentage: {curtailment / max_available * 100:.4f}%\n- Supply-demand balance: {actual_generation / total_load * 100:.4f}%\n\n**Notes:**\n- Small curtailment values (< 0.001 MWh) are typically artifacts of:\n  - Floating-point arithmetic precision\n  - LP solver convergence tolerances\n  - Numerical rounding in optimization\n- Larger curtailment values may indicate genuine operational constraints\n'
    # Actual generation
    # Curtailment
    # Total load
    display(Markdown(markdown_text_3))
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
