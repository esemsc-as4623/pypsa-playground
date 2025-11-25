import argparse

def create_argparser():
    """
    Create and configure the argument parser.
    Returns configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(description='Command line argument parser')
    
    # add_nodes.py specific arguments
    parser.add_argument('-n', type=int, help='Number of nodes in the network')
    parser.add_argument('-t', type=int, help='Number of time snapshots')
    
    # add_demand.py / add_supply.py specific arguments
    parser.add_argument('-d', type=str, choices=['random', 'zero'], help='Demand scenario')
    parser.add_argument('-e', type=str, choices=['nearly-free', 'oversupply'], help='Energy generation scenario')

    return parser

def parse_args():
    """
    Parse command line arguments and return as dictionary.
    Returns dict with argument names as keys and values as parsed values.
    """

    parser = create_argparser()
    args = parser.parse_args()
    
    args_dict = {k: v for k, v in vars(args).items() if v is not None}

    return args_dict