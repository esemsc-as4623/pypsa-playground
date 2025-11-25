import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)
save_directory = Path(__file__).parent

def add_demand(n, d_scenario):
    """
    Add demand profiles to the network based on the specified scenario.

    Parameters
    ----------
    - n (pypsa.Network): The power system network to which supply is added.
    - d_scenario (str): The demand scenario, either 'random' or 'zero'.
    
    Returns
    -------
    - pypsa.Network: The updated power system network with added demand.
    """

    buses = n.buses.index
    snapshots = n.snapshots

    # add random load (demand) profile
    if d_scenario == "random":
        n.add("Load",
              n.buses.index + " load",
              bus=buses,
              p_set=np.random.rand(len(snapshots), len(buses)))
    elif d_scenario == "zero":
        n.add("Load",
              n.buses.index + " load",
              bus=buses,
              p_set=np.zeros((len(snapshots), len(buses))))
    
    # visualize demand profile
    plt.figure()
    n.loads_t.p_set.sum(axis=1).plot()
    plt.tight_layout()
    plt.savefig(f"{save_directory}/{d_scenario}-demand-profile.png")

    return n