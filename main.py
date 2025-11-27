from start import parse_args, add_nodes, add_demand, add_supply, solve_network

if __name__ == "__main__":
    args = parse_args()

    network = add_nodes(args.get('n', 5), args.get('t', 365))
    network = add_demand(network, args.get('d', 'zero'))
    network = add_supply(network, args.get('e', 'oversupply'))
    network = solve_network(network)