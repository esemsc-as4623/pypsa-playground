## Startup

### Environment

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Demo 0: `scigrid-de.py`

```bash
python scigrid-de.py`
```

### Demo 1: Benchmarks

Enter the benchmarks subdirectory to view instructions and run

```bash
cd benchmarks
```

### Demo 2: PyPSA-EUR

Set-up Environment

(first time)
```bash
git clone https://github.com/PyPSA/pypsa-eur.git
# update virtual environment with all additional packages
python update_requirements.py -f pypsa-eur/envs/update_environment.yaml --continue-on-error # from environment.yaml
uv pip install -r pypsa-eur/doc/requirements.txt # from requirements.txt
sudo apt-get install gdal-bin libgdal-dev # add system libraries separately
# update requirements.txt
uv pip freeze > requirements.txt
```
(subsequently)
```bash
uv pip install -r requirements.txt
```

Run a demo using snakemake (see examples below).
Visualize the results

```bash
python visualizations.py -n results/{CONFIG}/networks/{NAME_OF_RUN}.nc -o {NAME_OF_OUTPUT_FOLDER}
# e.g. python visualizations.py -n results/test-elec/networks/base_s_6_elec_.nc -o analysis_results/
```

#### 2A

##### Run

```bash
cd pypsa-eur
snakemake -call results/test-elec/networks/base_s_6_elec_.nc --configfile config/test/config.electricity.yaml
```
view logs in `.snakemake/log/{2025-11-13T113052.887075}.snakemake.log`.

##### What just happened?
1. Executed `scripts/build_line_rating.py`, which calculates dynamic line rating for transmission lines in the power grid.
- input: base network (.nc) + weather cutout (.nc)
- process:
  1. Filters overhead lines only (excludes underground cables)
  2. Creates geometric line shapes from bus coordinates for spatial weather mapping
  3. Calculates temperature-dependent resistance using R(T) = R_ref * (1 + α(T - T_ref))
  4. Extracts conductor bundle information from line types (e.g., "4-bundle" → n_bundle = 4)
  5. Uses atlite's line_rating function with heat balance considering:
     - Resistive heating (I²R losses)
     - Solar radiation gain
     - Radiative cooling
     - Forced convection (wind cooling)
     - Natural convection
  6. Converts current limits to power limits using P = √3 * I * V * n_bundle * num_parallel
- output: dynamic line ratings (.nc) containing maximum power (MW) for each line at each timestep
- purpose: provide weather-dependent transmission capacity constraints for grid optimization
- updated params:
  - `D` = conductor diameter (0.0218 m)
  - `Ts` = maximum conductor temperature (353 K / 80°C)
  - `epsilon` = emissivity (0.8)
  - `alpha` = solar absorptivity (0.8)
  - `n_bundle` = number of conductors per bundle (extracted from line type or defaults to 1)
  - `T_ref` = reference temperature for resistance calculation (293 K / 20°C)
  - `alpha_temp` = temperature coefficient of resistance (0.00403 1/K)

2. Executed `scripts/add_transmission_projects_and_dlr.py`, which adds planned transmission infrastructure to the network and applies dynamic ratings to the lines
- input: base network (.nc) + transmission project files (.csv) + dynamic line ratings (.nc)
- process:
  1. Reads CSV files and adds components based on filename patterns:
     - "new_buses" → adds new substations with n.add("Bus")
     - "new_lines" → adds new AC transmission lines with n.add("Line")
     - "new_links" → adds new HVDC connections with n.add("Link")
     - "adjust_lines" → modifies existing line parameters with n.lines.update()
     - "adjust_links" → modifies existing link parameters with n.links.update()
  2. Converts DLR from absolute power to per-unit values: s_max_pu = (rating / s_nom) * correction_factor
  3. Applies voltage difference constraint: calculates reactance-based power limit to prevent excessive voltage drops
  4. Clips capacity factors with safety bounds: lower=1.0 (minimum base capacity), upper=max_line_rating
  5. Applies final scaling with base capacity multiplier
- output: enhanced network (.nc) with new infrastructure and time-varying line capacity constraints
- purpose: integrate planned grid expansion and implement weather-responsive capacity management for optimization
- updated params:
  - `s_max_pu` = base capacity multiplier applied to all dynamic ratings
  - `correction_factor` = safety/uncertainty adjustment factor for DLR calculations
  - `max_voltage_difference` = electrical constraint (degrees) to limit voltage drops via reactance
  - `max_line_rating` = physical constraint (multiple of base rating) to cap unrealistic capacity increases

3. Executed `scripts/simplify_network.py`, which simplifies and reduces the complexity of the transmission network
- input: base network (.nc) + onshore regions (.geojson) + offshore regions (.geojson) + admin shapes (.geojson)
- process: 
  1. Maps all voltage levels to single 380kV layer and removes transformers
  2. Simplifies multi-hop DC links into single representative connections
  3. Removes dead-end lines (stubs) and unused network components
  4. Aggregates buses to electrical substations based on proximity
  5. Clusters regions and updates geographic boundaries
- output: simplified network (.nc) + busmap mapping (.csv) + clustered onshore/offshore regions (.geojson)
- purpose: reduce computational complexity while preserving essential network characteristics for optimization
- updated params:
  - `linetype_380` = standard 380kV line type for voltage level unification
  - `p_max_pu` = maximum capacity factor for simplified DC links
  - `p_min_pu` = minimum capacity factor for simplified DC links
  - `remove_stubs` = flag to enable removal of dead-end network branches
  - `remove_stubs_across_borders` = allow stub removal across country boundaries
  - `to_substations` = flag to aggregate buses to electrical substations
  - `aggregation_strategies` = methods for combining buses/lines during clustering

4. Executed `scripts/build_electricity_demand_base.py`, which builds electricity demand for regions based on population and GDP
- input: base network (.nc) + regions (.geojson) + country load data (.csv) + NUTS3 statistical data (.geojson)
- process:
  1. Maps country-level electricity demand to individual network buses
  2. Uses spatial intersection to determine which NUTS3 regions overlap with each network region
  3. Distributes demand based on weighted combination of GDP (60%) and population (40%) by default
  4. Handles single-bus countries directly, multi-bus countries through spatial disaggregation
  5. Creates time series demand profiles for each bus location
- output: spatially disaggregated electricity demand time series (.nc) with hourly profiles per bus
- purpose: provide realistic spatial distribution of electricity consumption for grid optimization
- updated params:
  - `distribution_key["gdp"]` = weighting factor for GDP-based demand distribution (default: 0.6)
  - `distribution_key["pop"]` = weighting factor for population-based demand distribution (default: 0.4)
  - `substation_lv` = flag identifying low-voltage connection buses for demand allocation
  - `zlib` = compression enabled for output file size reduction
  - `complevel` = compression level (9 = maximum compression)
  - `least_significant_digit` = precision control for floating point storage (5 digits)

5. Executed `scripts/process_cost_data.py`, which prepares and extends cost data with custom modifications
- input: base network (.nc) + default costs (.csv) + custom cost modifications (.csv)
- process:
  1. Loads custom costs and categorizes into raw attributes (pre-preparation) and prepared attributes (post-preparation)
  2. Corrects units from kW/GW to MW standard: multiplies /kW by 1e3, divides /GW by 1e3
  3. Unstacks cost data by technology and sums grouped parameters with fillna for missing values
  4. Applies custom raw cost overwrites and config-based overwrites for investment, lifetime, FOM, VOM, efficiency, fuel, standing losses
  5. Calculates annualized capital costs: capital_cost = (annuity_factor + FOM/100) × investment × nyears
  6. Computes marginal costs: marginal_cost = VOM + fuel/efficiency
  7. Sets fuel and $CO_2$ intensity for gas turbines (OCGT/CCGT) from gas parameters
  8. Calculates storage technology costs combining power and energy components
  9. Applies final custom prepared cost overwrites for marginal_cost and capital_cost
- output: processed cost data (.csv) with standardized units and calculated parameters
- purpose: provide standardized economic parameters for all technologies in grid optimization
- updated params:
  - `fill_values` = default values for missing cost parameters
  - `discount_rate` = financial discount rate for annuity calculations
  - `planning_horizon` = target year for cost projections (e.g., 2050)
  - `max_hours["battery"]` = energy-to-power ratio for battery storage cost calculation
  - `max_hours["H2"]` = energy-to-power ratio for hydrogen storage cost calculation
  - `nyears` = investment period scaling factor based on snapshot weightings
  - `annuity_factor` = calculated from lifetime and discount rate for capital cost annualization

6. Executed `scripts/cluster_network.py`, which clusters the network into a reduced number of zones while preserving essential characteristics
- input: simplified network (.nc) + regions (.geojson) + load profiles (.nc) + optional clustering features (.nc) + admin shapes (.geojson)
- process:
  1. Determines clustering mode: numerical (kmeans/hac/modularity), administrative regions, custom shapes, or custom busmap
  2. For numerical clustering: distributes target cluster count across countries weighted by electrical load
  3. Applies clustering algorithm per country/subnetwork maintaining electrical connectivity
  4. Aggregates buses using strategies: substations combined, loads summed, generators merged by technology
  5. Creates transmission corridors between clusters by aggregating parallel lines
  6. Updates geographic regions by dissolving boundaries according to busmap
  7. Optionally applies copperplate connections within specified regions (infinite capacity)
  8. Maps bus coordinates to cluster centroids or administrative region centers using Pole of Inaccessibility
- output: clustered network (.nc) + busmap (.csv) + linemap (.csv) + clustered onshore/offshore regions (.geojson)
- purpose: reduce computational complexity for optimization while maintaining spatial and electrical realism
- updated params:
  - `mode` = clustering approach: "numerical"/"administrative"/"custom_busshapes"/"custom_busmap"
  - `algorithm` = clustering method: "kmeans"/"hac"/"modularity" for numerical mode
  - `focus_weights` = country-specific weighting to concentrate clusters in certain regions
  - `aggregation_strategies["buses"]` = methods for combining bus attributes during clustering
  - `aggregation_strategies["lines"]` = methods for combining line attributes into corridors
  - `copperplate_regions` = list of regions to connect with infinite capacity links
  - `n_init` = number of k-means initializations (1000)
  - `max_iter` = maximum k-means iterations (30000)
  - `random_state` = random seed for reproducible clustering (0)

7. Executed `scripts/determine_availability_matrix.py` (for each technology: offwind-ac, solar-hsat, offwind-dc, onwind, solar, offwind-float), which determines land/sea availability for renewable energy development
- input: regions (.geojson) + cutout (.nc) + CORINE land cover (.tif) + Natura2000 (.tiff) + GEBCO bathymetry (.nc) + shipping density (.tif) + country/offshore shapes (.geojson)
- process:
  1. Creates ExclusionContainer with 3035 CRS projection and specified resolution (default: 100m)
  2. Adds Natura2000 protected areas as exclusion zones (nodata=0, allow overlap)
  3. Processes CORINE/LUISA land cover data:
     - Excludes specified grid codes (e.g., urban areas, forests for wind)
     - Applies distance buffers around excluded areas if specified
  4. For offshore technologies: applies depth constraints using GEBCO bathymetry
     - max_depth: excludes areas deeper than threshold (e.g., -50m for fixed wind)
     - min_depth: excludes shallow areas (e.g., <-15m to avoid shipping)
  5. Applies shipping density threshold for offshore (excludes high-traffic areas)
  6. Enforces shore distance constraints:
     - min_shore_distance: buffer zone from coastline
     - max_shore_distance: maximum distance from shore
  7. Calculates availability matrix using cutout.availabilitymatrix() with parallel processing
  8. Handles Moldova/Ukraine regions with external availability data overlay
- output: availability matrix (.nc) containing fraction [0-1] of available land per grid cell per region
- purpose: provide spatial constraints for renewable energy potential calculation based on land use, environmental protection, and technical limitations
- updated params (technology-specific):
  - `excluder_resolution` = spatial resolution for exclusion analysis (100m default)
  - `natura` = boolean flag to exclude Natura2000 protected areas
  - `corine.grid_codes` = CORINE land use classes to exclude (e.g., [1,2,3,4,5] for urban/industrial)
  - `corine.distance` = buffer distance around excluded land use classes
  - `max_depth` = maximum water depth for offshore wind (e.g., -50m for fixed, -200m for floating)
  - `min_depth` = minimum water depth to avoid shallow areas (-15m typical)
  - `ship_threshold` = shipping density threshold for offshore exclusion
  - `min_shore_distance` = minimum distance from coastline (km)
  - `max_shore_distance` = maximum distance from coastline (km)

8. Executed `scripts/build_powerplants.py`,  which retrieves and processes conventional powerplant data for the network
- input: simplified network (.nc) + powerplantmatching database (online) + custom powerplants (.csv) + country list
- process:
  1. Downloads powerplant database from powerplantmatching (online data source)
  2. Filters powerplants by fuel type: excludes solar/wind, includes only target countries
  3. Standardizes natural gas technologies: Steam Turbine→CCGT, Combustion Engine→OCGT, default→CCGT
  4. Corrects bioenergy data using OPSD database for available countries
  5. Applies powerplants_filter query to remove/select specific plants (e.g., exclude Germany)
  6. Adds custom powerplants from CSV file based on custom_powerplants query
  7. Creates "everywhere powerplants" with zero capacity at all substations for specified fuel types
  8. Maps powerplant coordinates to nearest network buses using spatial proximity
  9. Handles duplicate names by appending numbers for same fuel type at same bus
  10. Fills missing decommissioning years and converts country codes to alpha2 format
- output: powerplants database (.csv) with bus assignments, coordinates, capacities, and technical parameters
- purpose: provide existing conventional generation capacity and locations for grid optimization baseline
- updated params:
  - `countries` = list of countries to include in powerplant dataset
  - `powerplants_filter` = pandas query string to filter powerplant database (e.g., "Country not in ['Germany']")
  - `custom_powerplants` = pandas query string or boolean to include custom powerplant data
  - `everywhere_powerplants` = list of fuel types to add with zero capacity at all buses (e.g., ['Natural Gas', 'Coal', 'Nuclear', 'OCGT'])
  - `fuel_mapping` = technology standardization: "Solid Biomass"→"Bioenergy", "Biogas"→"Bioenergy"
  - `commissioning_years` = DateIn/DateOut assigned from database min/max for multi-year models

9. Executed `scripts/build_renewable_profiles.py` (for each technology: solar, onwind, offwind-ac, offwind-float, solar-hsat, offwind-dc), which calculates installable capacity, generation time series, and distances for renewable technologies
- input: availability matrix (.nc) + cutout (.nc) + resource regions (.geojson) + distance regions (.geojson) + offshore shapes (.geojson)
- process:
  1. Loads technology-specific resource parameters (turbine/panel models) and correction factors
  2. Creates spatial indicator matrix I mapping cutout grid cells to network regions using cutout.availabilitymatrix()
  3. Calculates average capacity factor per grid cell using atlite resource methods (e.g., cutout.wind(), cutout.pv())
  4. Divides renewable potential into resource classes (bins) based on capacity factor quantiles:
     - cf_min to cf_max range split into configurable number of bins (typically 1)
     - Creates class_masks for each bus-bin combination based on capacity factor thresholds
  5. Computes layout matrix: capacity_factor × area × capacity_per_sqkm for generator distribution
  6. Generates time series profiles using func(matrix=availability×class_masks, layout=layout, per_unit=True)
  7. Calculates p_nom_max: maximum installable capacity = capacity_per_sqkm × availability × class_masks × area
  8. Computes average_distance: weighted distance from generators to bus/shoreline using representative points
  9. Filters buses with minimal capacity factor (min_p_max_pu) and potential (min_p_nom_max)
  10. Optional profile clipping to remove very low generation periods
- output: renewable profiles (.nc) containing time series, capacity limits, distances + class regions (.geojson)
- purpose: provide technology-specific generation profiles and capacity constraints for renewable energy optimization
- updated params (technology-specific):
  - `resource["method"]` = atlite calculation method: "wind"/"pv" for capacity factor computation
  - `resource[turbine/panel]` = technology models with multiple years/variants (e.g., {2019: "Vestas_V112_3MW"})
  - `correction_factor` = global adjustment factor applied to all capacity factors (default: 1.0)
  - `capacity_per_sqkm` = installable density: MW/km² (e.g., 3 MW/km² onwind, 15 MW/km² solar)
  - `resource_classes` = number of capacity factor bins for spatial discretization (default: 1)
  - `min_p_max_pu` = minimum capacity factor threshold for bus inclusion
  - `min_p_nom_max` = minimum installable capacity threshold for bus inclusion (MW)
  - `clip_p_max_pu` = capacity factor below which generation is set to zero

10. Executed `scripts/add_electricity.py`, which ties all data inputs together into a complete PyPSA network for optimization
- input: clustered network (.nc) + renewable profiles (.nc) + powerplants (.csv) + costs (.csv) + load data (.nc) + busmap (.csv) + hydro data (.csv/.nc) + unit commitment data (.csv)
- process:
  1. Sets network snapshots from configuration (hourly time series for optimization period)
  2. Loads and aggregates powerplants with capacity-weighted averaging and efficiency classes
  3. Attaches electricity demand using busmap to distribute country-level load to buses
  4. Sets transmission costs: HVAC overhead for AC lines, HVDC overhead/submarine for DC links with inverter costs
  5. Attaches wind and solar generators:
     - Reads renewable profiles with capacity factors and maximum installable capacity
     - Calculates connection costs for offshore wind (submarine + underground cables)
     - Creates generators with zero initial capacity but extendable up to p_nom_max
  6. Attaches conventional generators from powerplant database:
     - Existing plants get fixed capacity (p_nom_min = p_nom)
     - Extendable technologies get zero initial capacity
     - Applies unit commitment constraints and dynamic fuel pricing if enabled
  7. Attaches hydro generators and storage:
     - Run-of-river: capacity factors from inflow time series
     - Pumped hydro storage: fixed capacity with round-trip efficiency
     - Reservoir hydro: storage units with inflow and capacity constraints
  8. Optionally estimates renewable capacities from IRENASTAT or GEM databases
  9. Attaches storage technologies (H2/battery) as StorageUnits or Store+Link combinations
  10. Sanitizes carriers with colors and nice names, handles location data
- output: complete electricity network (.nc) with all generators, loads, storage, and time series ready for optimization
- purpose: create final network model combining all data sources for capacity expansion and dispatch optimization
- updated params:
  - `snapshots` = time period and resolution for optimization (e.g., "2013-03")
  - `scaling_factor` = demand scaling multiplier for scenarios
  - `line_length_factor` = transmission cost adjustment factor
  - `conventional_carriers` = list of existing thermal technologies (e.g., ["coal", "CCGT", "nuclear"])
  - `extendable_carriers` = technologies that can be built (e.g., {"Generator": ["OCGT", "solar", "onwind"]})
  - `max_hours` = energy-to-power ratios for storage: {"battery": 6, "H2": 168}
  - `consider_efficiency_classes` = split generators into efficiency bins (low/medium/high)
  - `unit_commitment` = enable detailed operational constraints for thermal plants
  - `estimate_renewable_capacities` = match existing renewables to statistical data

11. Executed `scripts/prepare_network.py`, which prepares the complete network for optimization by applying policy constraints and temporal modifications
- input: complete electricity network (.nc) + processed costs (.csv) + optional $CO_2$ price time series (.csv)
- process:
  1. Sets N-1 security margin for transmission lines (s_max_pu) to ensure grid stability
  2. Applies temporal modifications:
     - Time averaging: resamples hourly data to lower resolution (e.g., 4H = 4-hour blocks)
     - Time segmentation: uses tsam package to create representative periods from full time series
  3. Adds policy constraints:
     - $CO_2$ emissions limit: global constraint on total annual emissions
     - Gas consumption limit: constraint on natural gas usage across OCGT/CCGT/CHP
     - Emission pricing: adds CO2 costs to marginal costs (static or dynamic time series)
  4. Configures transmission expansion:
     - Sets existing transmission as minimum capacity (s_nom_min = s_nom)
     - Enables transmission expansion (s_nom_extendable = True)
     - Applies expansion limits by cost or volume if specified
  5. Applies technology cost/potential adjustments by carrier and parameter
  6. Sets maximum expansion limits for lines and links (s_nom_max, p_nom_max)
  7. Optionally enforces autarky by removing cross-border transmission connections
  8. Stores configuration metadata in network for reproducibility
- output: optimization-ready network (.nc) with policy constraints, temporal structure, and expansion settings
- purpose: transform complete network model into constrained optimization problem reflecting policy scenarios
- updated params:
  - `s_max_pu` = N-1 security margin factor for transmission lines (default: 0.7)
  - `time_resolution` = temporal aggregation: hourly string (e.g., "4H") or segments (e.g., "10seg")
  - `co2limit` = annual $CO_2$ emissions limit in Mt (policy constraint)
  - `gaslimit` = annual gas consumption limit in TWh (energy security)
  - `emission_prices["co2"]` = carbon price in €/t$CO_2$ (static or dynamic)
  - `transmission_limit` = expansion constraint: "c" (cost) or "v" (volume) + factor
  - `adjustments` = technology-specific cost/potential modifications by carrier
  - `autarky["enable"]` = remove transmission links for energy independence scenarios

12. Executed `scripts/solve_network.py`, which solves the optimization problem to find optimal capacity expansion and dispatch
- input: optimization-ready network (.nc) with all constraints and policy settings applied
- process:
  1. Prepares network for solving with additional constraints and modifications:
     - Clips very low capacity factors (clip_p_max_pu) to reduce numerical issues
     - Adds load shedding generators at all buses with high marginal cost (emergency supply)
     - Adds curtailment generators for renewable spillage with negative cost
     - Applies noisy costs to break solver degeneracies if enabled
  2. Adds technology-specific constraints based on configuration:
     - Land use constraints: ensures renewable capacity doesn't exceed technical potential per region
     - Solar potential constraints: coordinates solar and solar-hsat deployment within shared land limits
     - CCL constraints: enforces country-carrier limits for minimum/maximum capacity per technology
     - BAU constraints: maintains business-as-usual minimum capacities for specified technologies
     - Operational reserves: adds spinning reserve requirements based on load and VRES uncertainty
  3. Adds sector-coupling constraints if enabled:
     - TES energy-to-power ratio: links thermal storage capacity to charger/discharger sizing
     - Battery charger-discharger synchronization: ensures symmetric charging/discharging capacity
     - CHP constraints: enforces heat-electricity production ratios and fuel consumption limits
     - Gas boiler retrofit: allows conversion of existing gas boilers to hydrogen
  4. Configures solver and optimization settings:
     - Sets solver name (HiGHS, Gurobi, CPLEX, etc.) and solver-specific options
     - Enables transmission expansion iteration or single-shot optimization
     - Applies rolling horizon for operations problems or multi-investment period solving
  5. Solves optimization problem using PyPSA's optimize function with linear programming
  6. Validates solution status and objective value against expected benchmarks
  7. Handles infeasible solutions by computing and reporting constraint violations
- output: solved network (.nc) with optimal capacities, dispatch, prices + configuration metadata (.yaml)
- purpose: determine least-cost capacity expansion and operational dispatch satisfying all technical, policy, and economic constraints
- updated params:
  - `solver_name` = optimization solver: "highs"/"gurobi"/"cplex" etc.
  - `solver_options` = solver-specific settings for performance tuning
  - `skip_iterations` = disable iterative transmission expansion (single-shot solving)
  - `track_iterations` = monitor transmission expansion iterations
  - `max_iterations` = maximum number of transmission expansion iterations
  - `linearized_unit_commitment` = enable detailed thermal plant operational constraints
  - `transmission_losses` = account for resistive losses in transmission lines
  - `assign_all_duals` = compute shadow prices for all constraints
  - `rolling_horizon` = solve operations in chunks for large time series
  - `check_objective["expected_value"]` = benchmark objective value for validation

##### Visualize
Run

```bash
snakemake results/{RUN_NAME}/graphs/costs.svg --cores 'all'
```

Note that the `{RUN_NAME}` is specified in your config file. In the default case (i.e. `config/config.default.yaml`), the run name is an empty string:

```yaml
run:
    name: ""
```