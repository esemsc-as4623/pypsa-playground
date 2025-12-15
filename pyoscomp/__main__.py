"""
pyoscomp/__main__.py

Entry point for the PyPSA-OSeMOSYS comparison framework CLI.
"""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(
        description="PyPSA-OSeMOSYS Comparison Framework CLI"
    )
    parser.add_argument("--setup", action="store_true", help="Set up the project environment.")
    parser.add_argument("--run", choices=["pypsa", "osemosys", "both"], help="Run the selected model(s).")
    parser.add_argument("--input", type=str, help="Path to input scenario folder.")
    parser.add_argument("--output", type=str, help="Path to output directory.")
    parser.add_argument("--test", action="store_true", help="Run tests.")
    parser.add_argument("--clean", action="store_true", help="Clean outputs and logs.")
    parser.add_argument("--loglevel", type=str, default="INFO", help="Set logging level.")
    args = parser.parse_args()

    # Placeholder: CLI logic dispatch
    if args.setup:
        print("[SETUP] Project environment setup not yet implemented.")
    elif args.run:
        print(f"[RUN] Model(s) to run: {args.run}")
    elif args.test:
        print("[TEST] Running tests...")
    elif args.clean:
        print("[CLEAN] Cleaning outputs and logs...")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
