import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)
save_directory = Path(__file__).parent

def add_supply(n, s_scenario):
    """
    Add supply (generators) to the network based on the specified scenario.

    Parameters
    ----------
    - n (pypsa.Network): The power system network to which supply is added.
    - s_scenario (str): The supply scenario, either 'nearly-free' or 'oversupply'.

    Returns
    -------
    - pypsa.Network: The updated power system network with added supply.
    """
    buses = n.buses.index
    snapshots = n.snapshots

    # add (nearly) free, fully available energy generators
    if s_scenario == "nearly-free":
        n.add("Generator",
            buses,
            suffix = f" {s_scenario}",
            bus = buses,
            p_nom_extendable = True,
            capital_cost = 1e-8, # optimization does not work with 0 cost
            p_max_pu = np.ones((len(snapshots), len(buses))))

    # add oversupply generators
    elif s_scenario == "oversupply":
        n.add("Generator",
            buses,
            suffix = f" {s_scenario}",
            bus = buses,
            p_nom_extendable = True,
            capital_cost = -1,
            p_max_pu = np.ones((len(snapshots), len(buses))))

    # visualize total generation profile
    plt.figure()
    n.generators_t.p_max_pu.mean(axis=1).plot()
    plt.tight_layout()
    plt.savefig(f"{save_directory}/{s_scenario}-supply-profile.png")

    return n