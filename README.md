
# PyPSA-OSeMOSYS Comparison (PyOSComp) Framework

## Overview
The `pyoscomp` package is a framework for direct, scalable, and reproducible comparison of energy system scenarios using PyPSA and OSeMOSYS. It provides scenario building tools, translation logic, standardized output creation, visualizations, and model/optimizer logging.

## Features
Run the same* energy system model scenario on PyPSA (v1.0.0) and OSeMOSYS (latest, otoole v1.1.5) from a single set-up.
_(* create the logic for the translating the scenario as closely as possible between the two models)_

- Build scenarios via
	- `scenario` module
	- bringing your own CSVs / .xlsx (for OSeMOSYS)
	- bringing your own .xlsx / NetCDF / HDF5 (for PyPSA)
- Translation logic for each component
	- `topology`
	- `time`
	- `demand`
	- `supply`
	- `performance`
	- `economics`
	- `storage`
- Standardized output CSVs and translation logs
- Visualization of inputs and outputs with matplotlib and PyPSA tools
- Pytest-based test suite for scenario building and translation
- Extensibility for new scenarios and models

## Quickstart
1. **Set up environment**
	```bash
	python3 -m venv .venv
	source .venv/bin/activate
	uv sync # OR pip install -r requirements.txt
	```
	Requires GPLK (GNU Linear Programming Kit)
	- install with conda, brew, or by downloading the distribution tarball
	- once installed, you should be able to call the `glpsol` command

2. **Run tests**
	```bash
	uv run pytest -v . # OR pytest -v .
	```

3. **Run a scenario**
3.1. *Build from scratch*
3.2. *Bring-your-own OSeMOSYS*
3.3. *Bring-your-own PyPSA*

## Project Structure
```
pyoscomp/
	 scenario/		# Scenario building
	 interfaces/	# Harmonizer
	 translation/ 	# Translation logic
	 runners/       # Model execution

	 # to set-up and run OSeMOSYS
	 OSeMOSYS_config.yaml
	 OSeMOSYS.txt

	 input/         # TODO: Input reading (for bring-your-own)
	 output/        # TODO: Output writing
	 cli/           # TODO: CLI execution logic

tests/         		# Pytest suite

notebooks/			# Examples

docs/				# Documentation
```

## Extending the Framework
- Add translation of new components (e.g. Emissions, Targets) in `translation/`
- Add new model runners in `runners/`
- Document new features in Markdown

## Developer Guide
- Follow PEP8 and use Sphinx docstrings
- Add/modify tests for all new code
- Log all actions and errors

## License
MIT