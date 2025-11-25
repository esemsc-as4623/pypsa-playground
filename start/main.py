from _argparser import parse_args

from add_nodes import add_nodes
from add_demand import add_demand
from add_supply import add_supply
from solve_network import solve_network

import pypsa

if __name__ == "__main__":
    args = parse_args()

    network = add_nodes(args.get('n', 5), args.get('t', 365))
    network = add_demand(network, args.get('d', 'zero'))
    network = add_supply(network, args.get('e', 'oversupply'))
    network = solve_network(network)