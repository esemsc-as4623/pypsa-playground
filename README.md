## Startup

### Environment

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Demo 0: `scigrid-de.py`

```bash
python scigrid-de.py`
```

### Demo 1: Benchmarks

Enter the benchmarks subdirectory to view instructions and run

```bash
cd benchmarks
```

### Demo 2: PyPSA-EUR

Set-up Environment

(first time)
```bash
git clone https://github.com/PyPSA/pypsa-eur.git
# update virtual environment with all additional packages
python update_requirements.py -f pypsa-eur/envs/update_environment.yaml --continue-on-error # from environment.yaml
uv pip install -r pypsa-eur/doc/requirements.txt # from requirements.txt
sudo apt-get install gdal-bin libgdal-dev # add system libraries separatelys
# update requirements.txt
uv pip freeze > requirements.txt
```
(subsequently)
```bash
uv pip install -r requirements.txt
```

Run

```bash
snakemake -call results/test-elec/networks/base_s_6_elec_.nc --configfile config/test/config.electricity.yaml
```