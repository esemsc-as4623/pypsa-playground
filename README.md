
# PyPSA-OSeMOSYS Comparison Framework

## Overview
This framework enables direct, reproducible comparison of energy system scenarios using both PyPSA and OSeMOSYS. It provides translation layers, standardized input/output, and a unified CLI for scenario execution, output, and visualization.

## Features
- Run PyPSA (v1.0.0) and OSeMOSYS (latest, otoole v1.1.5) from a single CLI
- Input scenarios via CSV/config folder (no manual scripting)
- Standardized output CSVs and logs
- Translation layers for both models (OOP, extensible)
- Visualization with matplotlib and PyPSA tools
- Robust logging and error handling
- Pytest-based test suite
- Easy extensibility for new scenarios and models

## Quickstart
1. **Set up environment:**
	```bash
	python3 -m venv .venv
	source .venv/bin/activate
	pip install -r requirements.txt
	```
2. **Run a scenario:**
	```bash
	python -m pyoscomp --run both --input path/to/scenario --output path/to/output
	```
3. **Run tests:**
	```bash
	pytest pyoscomp/tests
	```

## Project Structure
```
pyoscomp/
	 cli/           # CLI logic
	 input/         # Input reading
	 output/        # Output writing
	 logs/          # Logging
	 runners/       # Model runners
	 translation/   # Translation layers
	 visualization/ # Plotting
	 tests/         # Pytest suite
```

## Extending the Framework
- Add new translators in `translation/`
- Add new model runners in `runners/`
- Add new CLI commands in `cli/`
- Document new features in Markdown

## Developer Guide
- Follow PEP8 and use docstrings
- Add/modify tests for all new code
- Log all actions and errors
- Use context7 guides for translation logic

## License
MIT

## Startup

### Environment

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

All PyPSA dependencies are in requirements.txt.
OSeMOSYS requires GPLK (GNU Linear Programming Kit)
- install with conda, brew, or by downloading the distribution tarball
- once installed, you should be able to call the `glpsol` command

### Start Configs

```bash
cd start
otoole setup config osemosys_config.yaml # creates osemosys_config.yaml with prepopulated defaults
otoole setup csv sample_data
otoole convert csv datafile sample_data osemosys_demo.txt osemosys_config.yaml
otoole convert datafile excel osemosys_demo.txt sample_data.xlsx osemosys_config.yaml
```

### Demo: `simplicity` (OSeMOSYS)
```bash
otoole convert csv datafile data simplicity.txt config.yaml
otoole convert datafile excel simplicity.txt simplicity.xlsx config.yaml
otoole convert excel csv simplicity.xlsx simplicity config.yaml
glpsol -m OSeMOSYS.txt -d simplicity.txt --wglp simplicity.glp --write simplicity.sol
otoole results glpk csv simplicity.sol results-glpk datafile simplicity.txt config.yaml --glpk_model simplicity.glp
otoole viz res excel simplicity.xlsx res.png config.yaml
```

### Demo: `scigrid-de.py` (PyPSA)

```bash
python scigrid-de.py`
```