import numpy as np
import pypsa

# Marginal costs in EUR/MWh
MARGINAL_COSTS = {
    "Wind": 0,
    "Hydro": 0,
    "Coal": 30,
    "Gas": 60,
    "Oil": 80
}

# Power plant capacities (nominal power in MW)
PLANT_P_NOM = {
    "South Africa": {
        "Coal": 35000,
        "Wind": 3000,
        "Gas": 8000,
        "Oil": 2000
    },
    "Mozambique": {
        "Hydro": 1200,
    },
    "Eswatini": {
        "Hydro": 600,
    }
}

# Transmission capacities in MW
TRANSMISSION = {
    "South Africa": {"Mozambique": 500, "Eswatini": 250},
    "Mozambique": {"Eswatini": 100},
}

# Electrical loads in MW
LOADS = {
    "South Africa": 42000,
    "Mozambique": 650,
    "Eswatini": 250
}

# Single market bidding zone: South Africa
# inelastic load has infinite marginal utility (higher than marginal cost of any generator)
country = "South Africa"
n = pypsa.Network()
n.add("Bus", country)

for tech in PLANT_P_NOM[country]:
    n.add("Generator",
          f"{country} {tech}",
          bus=country,
          p_nom=PLANT_P_NOM[country][tech],
          marginal_cost=MARGINAL_COSTS[tech]
    )

n.add("Load", f"{country} Load", bus=country, p_set=LOADS[country])

n.optimize()

print(n.loads_t.p)

print(n.generators_t.p)

print(n.buses_t.marginal_price)

# Bidding zones connected by transmission line
# bidirectional lossless transmission capacity
# in the physical grid, power would flow passively according to network impedances
countries = ["South Africa", "Mozambique", "Eswatini"]
n = pypsa.Network()

for country in countries:
    n.add("Bus", country)

    for tech in PLANT_P_NOM[country]:
        n.add("Generator",
              f"{country} {tech}",
              bus=country,
              p_nom=PLANT_P_NOM[country][tech],
              marginal_cost=MARGINAL_COSTS[tech]
        )

    n.add("Load", f"{country} Load", bus=country, p_set=LOADS[country])

    if country not in TRANSMISSION:
        continue

    for neighbor in countries:
        if neighbor not in TRANSMISSION[country]:
            continue

        n.add("Link",
              f"{country}-{neighbor} Link",
              bus0=country,
              bus1=neighbor,
              p_nom=TRANSMISSION[country][neighbor],
              p_min_pu=-1 # to allow bidirectional flow
        )

n.optimize()

print(n.loads_t.p)

# dispatched generation of generators
print(n.generators_t.p)

# nodal marginal prices
print(n.buses_t.marginal_price)
# if two buses have the same marginal price, interconnector is not congested
# if different, interconnector is congested and there is a binding transmission constraint

# power flow from bus0 to bus1
print(n.links_t.p0)

print(n.links_t.mu_lower)