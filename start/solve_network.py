import pypsa

def solve_network(n: pypsa.Network) -> pypsa.Network:
    """
    Solve the power flow for the given network.

    Parameters
    ----------
    - n (pypsa.Network): The power network to be solved.

    Returns
    -------
    - pypsa.Network: The solved power network.
    """
    n.optimize(solver="highs")
    return n