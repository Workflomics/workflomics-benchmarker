# Workflomics Benchmarker

**Workflomics Benchmarker** is a library designed for executing and benchmarking workflows provided in Common Workflow Language (CWL) within the Workflomics ecosystem.

Detailed user documentation is available on [readthedocs](https://workflomics.readthedocs.io/en/latest/workflomics-benchmarker/benchmarker.html).

## Badges

| Description | Badge |
|:------------|:------|
| **Packages and Releases** | ![Latest release](https://img.shields.io/github/release/workflomics/workflomics-benchmarker.svg) [![PyPI](https://img.shields.io/pypi/v/workflomics-benchmarker.svg)](https://pypi.python.org/pypi/workflomics-benchmarker/) |
| **DOI** | [![DOI](https://zenodo.org/badge/749899872.svg)](https://zenodo.org/doi/10.5281/zenodo.10839465) |
| **License** | [![GitHub license](https://img.shields.io/github/license/workflomics/workflomics-benchmarker)](https://github.com/workflomics/workflomics-benchmarker/blob/main/LICENSE) |
| **OS Support** | [![](https://img.shields.io/badge/linux-supported-green.svg)](https://workflomics.readthedocs.io/en/latest/workflomics-benchmarker/benchmarker.html) [![](https://img.shields.io/badge/macos-supported-green.svg)](https://workflomics.readthedocs.io/en/latest/workflomics-benchmarker/benchmarker.html) [![](https://img.shields.io/badge/windows-WSL2_required-yellow.svg)](https://www.python.org/downloads/) |
| **Requirements** | [![](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)|

## Requirements

- Python 3.9 or higher
- Docker or Singularity

> **_NOTE:_**  Workflomics Benchmarker is will run on **Linux** and **macOS** without any additional configuration. However, **Windows** users need to use Windows Subsystem for Linux (WSL) to run the tool (see [MS Windows users](#ms-windows-users)).


**Optional:**

- Poetry (if you want to build the package from source)

## Installation

Create a virtual environment and install the required packages:

```bash
python3 -m venv workflomics-env      # Create a virtual environment named 'env' in the current directory
source workflomics-env/bin/activate  # Activate environment before installing `workflomics`
```

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

### MS Windows users

1. [Install Windows Subsystem for Linux 2 and Docker Desktop](https://docs.docker.com/docker-for-windows/wsl/#prerequisites>). 
2. [Install Debian from the Microsoft Store](https://www.microsoft.com/en-us/p/debian/9msvkqc78pk6).
3. Set Debian as your default WSL 2 distro: `wsl --set-default debian`.
4. Return to the Docker Desktop, choose `Settings` → `Resources` → `WSL Integration` and under "Enable integration with additional distros" select "Debian",
5. Reboot if you have not yet already.
6. Launch Debian and follow the Linux [instructions](#installation) above (`pip install workflomics-benchmarker`)

Network problems from within WSL2? Try `these instructions <https://github.com/microsoft/WSL/issues/4731#issuecomment-702176954>`_ followed by `wsl --shutdown`.

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
