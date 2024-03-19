# Workflomics Benchmarker

**Workflomics Benchmarker** is a versatile library designed for executing and benchmarking workflows encapsulated in Common Workflow Language (CWL) within the Workflomics ecosystem.

Detailed user documentation is available on [readthedocs](https://workflomics.readthedocs.io/en/latest/workflomics-benchmarker/benchmarker.html).

## Badges

| Description | Badge |
|:------------|:------|
| **Packages and Releases** | ![Latest release](https://img.shields.io/github/release/workflomics/workflomics-benchmarker.svg) [![PyPI](https://img.shields.io/pypi/v/workflomics-benchmarker.svg)](https://pypi.python.org/pypi/workflomics-benchmarker/) |
| **DOI** | [![DOI](https://zenodo.org/badge/749899872.svg)](https://zenodo.org/doi/10.5281/zenodo.10839465) |
| **License** | [![GitHub license](https://img.shields.io/github/license/workflomics/workflomics-benchmarker)](https://github.com/workflomics/workflomics-benchmarker/blob/main/LICENSE) |


## Requirements

- Python 3.9 or higher
- Docker or Singularity
- Poetry (if you want to build the package from source)

## Installation

Install `workflomics-benchmarker` from PyPI using pip:

```bash
pip install workflomics-benchmarker 
```

Alternatively, you clone the repository and can install it using Poetry by running:

```bash
git clone https://github.com/workflomics/workflomics-benchmarker.git
cd workflomics-benchmarker
poetry install 
```

## Usage

Ensure Docker or Singularity is running before executing workflows. Here are the commands for both services:

### Docker

```bash
workflomics benchmark tests/data/ 
```

Or directly with Python:

```bash
python src/benchmarker/workflomics.py benchmark tests/data/ 
```

The results will be saved in the `./tests/data` directory.

### Singularity

To use Singularity, ensure it's installed and append the `--singularity` flag:

```bash
python src/benchmarker/workflomics.py benchmark tests/data/ --singularity 
```

## Testing

Run the following command to execute tests:

```bash
poetry run pytest -s 
```

This command runs a workflow and benchmarks it, assuming Docker is operational. Results are stored in the `./tests/data` directory.
