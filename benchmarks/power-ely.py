"""
Simple PyPSA-based single-node gas + wind + solar 
+ electrolyzer infrastructure model for a single 
year-time horizon.
"""

import matplotlib.pyplot as plt
import pandas as pd
import pypsa

plt.style.use('bmh')

# Technology data and costs
# database (https://github.com/PyPSA/technology-data) collects assumptions and projections for energy system technologies
# (e.g., efficiencies, lifetimes, etc.) for given years
# pre-processing: (e.g. converting units, setting defaults, re-arranging dimensions)

year = 2030
url = f"https://raw.githubusercontent.com/PyPSA/technology-data/master/outputs/costs_{year}.csv"
costs = pd.read_csv(url, index_col=[0, 1])

# convert costs to per MW where necessary
costs.loc[costs.unit.str.contains("/kW"), "value"] *= 1e3
costs.unit = costs.unit.str.replace("/kW", "/MW")

defaults = {
    "FOM": 0,
    "VOM": 0,
    "efficiency": 1,
    "fuel": 0,
    "investment": 0,
    "lifetime": 25,
    "CO2 intensity": 0,
    "discount rate": 0.07,
}
# convert to wide format and fill missing values with defaults
costs = costs.value.unstack().fillna(defaults)

# re-assign fuel and CO2 intensity for OCGT
costs.at["OCGT", "fuel"] = costs.at["gas", "fuel"]
costs.at["OCGT", "CO2 intensity"] = costs.at["gas", "CO2 intensity"]

# function to calculate annuity (annualized investment costs)
def calculate_annuity(r, n):
    return r / (1.0 - 1.0 / (1.0 + r) ** n)

costs["marginal_cost"] = costs["VOM"] + costs["fuel"] / costs["efficiency"]
annuity = costs.apply(lambda x: calculate_annuity(x["discount rate"], x["lifetime"]), axis=1)
costs["capital_cost"] = (annuity + costs["FOM"] / 100) * costs["investment"]

# load time series data
url = "https://tubcloud.tu-berlin.de/s/pKttFadrbTKSJKF/download/time-series-lecture-2.csv"
ts = pd.read_csv(url, index_col=0, parse_dates=True)
ts.load *= 1e3

# We are also going to adapt the temporal resolution of the time series:

resolution = 1
ts = ts.resample(f"{resolution}h").first()

# ## Simple capacity expansion planning example

n = pypsa.Network()
n.add("Bus", "electricity")
n.set_snapshots(ts.index)
n.snapshot_weightings.loc[:, :] = resolution