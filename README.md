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

```bash
git clone https://github.com/PyPSA/pypsa-eur.git
cd pypsa-eur
conda update conda
conda env create -f envs/environment.yaml
conda activate pypsa-eur
snakemake -call results/test-elec/networks/base_s_6_elec_.nc --configfile config/test/config.electricity.yaml
```