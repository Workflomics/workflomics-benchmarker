from pathlib import Path
from typing import List
import yaml
import subprocess
import sys
import os


def create_output_dir(dir_path: str, workflow_name: str) -> str:
    """
    Create the output directory for a given workflow in the specified directory and return the path to it.

    Parameters
    ----------
    dir_path : str
        The path to the directory where the output directory will be created.
    workflow_name : str
        The name of the workflow.

    Returns
    -------
    str
        The path to the output directory.
    """
    # create the output directory for the workflow
    workflow_outdir = os.path.join(dir_path, workflow_name + "_output")

    Path(workflow_outdir).mkdir(exist_ok=True)

    return workflow_outdir


KNOWN_USELESS_WARNINGS_ERRORS = [
    "WARNING: The requested image's platform",
    " 0 errors",
    "Calculating sensitivity...and error tables...",
    " 0 warnings",
]


def is_line_useless(line):
    """Check if a line is useless for the benchmarking.

    Parameters
    ----------
    line: str
        The line to check.

    Returns
    -------
    bool
        True if the line is useless, False otherwise.

    """
    for useless in KNOWN_USELESS_WARNINGS_ERRORS:
        if useless in line:
            return True
    return False


def setup_empty_benchmark_for_step(step_name: str) -> dict:
    return {
        "step": step_name,
        "status": "-",
        "time": "N/A",
        "memory": "N/A",
        "warnings": "N/A",
        "errors": "N/A",
    }
