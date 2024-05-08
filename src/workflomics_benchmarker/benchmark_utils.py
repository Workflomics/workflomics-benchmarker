from pathlib import Path
import os

import re
import datetime
from typing import List

from workflomics_benchmarker.scientific_benchmarks import benchmark_gProfiler, benchmark_proteinprophet


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
    workflow_outdir = os.path.join(dir_path, workflow_name.removesuffix(".cwl") + "_output")

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
        "time": "-",
        "memory": "-",
        "warnings": "",
        "errors": "",
        "identified_proteins": "-",
        "go_terms": "-",

    }


success_pattern = re.compile(r"\[job (.+)\] completed success")


def step_success_pattern(line):
    """Check if a line contains the success of a step."""
    return success_pattern.search(line)


fail_pattern = re.compile(
    r"\[job (.+)\] completed permanentFail|ERROR Exception on step '([^']+)'"
)


def step_fail_pattern(line):
    """Check if a line contains the failure of a step."""
    return fail_pattern.search(line)


def set_step_status_to_failed(step_results, failed_tool_name):
    """Set the status of a step as failed."""
    for step_result in step_results:
        if step_result["step"] == failed_tool_name:
            step_result["status"] = "✗"
            break


def benchmark_successful_step_execution(successfully_executed_steps: List[str], cwltool_output_lines: List[str], step_results: List[dict], workflow_outdir:str) -> List[dict]:
    """Benchmark the successful execution of a step and update then

    Parameters
    ----------
    successfully_executed_steps : List[str]
        The list of successfully executed steps.
    cwltool_output_lines : List[str]
        The list of lines from the cwltool output.
    step_results : List[dict]
        The list of benchmark results for each step.
    workflow_outdir : str
        The path to the output directory for the workflow.
    """
    for step in successfully_executed_steps:
        max_memory_step = "-"
        step_start = False
        warnings_step = []
        errors_step = []
        for line in cwltool_output_lines:
            if f"[step {step}] start" in line:
                start_time_step = datetime.datetime.strptime(
                    line[:21], "[%Y-%m-%d %H:%M:%S]"
                )
                step_start = True
            elif f"[job {step}] completed success" in line:
                end_time_step = datetime.datetime.strptime(
                    line[:21], "[%Y-%m-%d %H:%M:%S]"
                )
                break
            elif step_start:
                if f"[job {step}] Max memory used" in line:
                    max_memory_step = int(
                        line.split()[-1].rstrip(line.split()[-1][-3:])
                    )
                    if line.split()[-1].endswith("GiB"):
                        max_memory_step = max_memory_step * 1024
                elif "warning" in line.lower():
                    if not is_line_useless(line):
                        warnings_step.append(line)
                elif "error" in line.lower():
                    if not is_line_useless(line):
                        errors_step.append(line)
        count_goterms = "-"  
        if "gprofiler" in step.lower():
            count_goterms = benchmark_gProfiler(workflow_outdir + "/output.json")

        count_identified_proteins = "-"
        files_with_extension = list(Path(workflow_outdir).glob('*.prot.xml'))
        first_file = files_with_extension[0] if files_with_extension else None
        if "proteinprophet" in step.lower() and first_file:
            count_identified_proteins = benchmark_proteinprophet(workflow_outdir + "/" + first_file.name)

        # set the minimum execution time to 1 second. Decimal values cannot be retrieved from the cwltool output, so the number of seconds is rounded up.
        execution_time_step = int((end_time_step - start_time_step).total_seconds())

        # store the benchmark values for each successfully executed step
        for entry in step_results:
            if entry["step"] == step:
                entry["status"] = "✓"
                entry["time"] = max(1, execution_time_step)
                entry["memory"] = max(1, max_memory_step)
                entry["warnings"] = warnings_step
                entry["errors"] = errors_step
                entry["identified_proteins"] = count_identified_proteins
                entry["go_terms"] = count_goterms
    return step_results

def benchmark_failed_step_execution(failed_steps: List[str], cwltool_output_lines: List[str], step_results: List[dict]) -> List[dict]:
    """Benchmark the failed execution of a step.

    Parameters
    ----------
    failed_steps : List[str]
        The list of steps which failed to execute.
    cwltool_output_lines : List[str]
        The list of lines from the cwltool output.
    step_results : List[dict]
        The list of benchmark results for each step.
    """
    all_errors = []
    all_warnings = []
    for step in failed_steps:
        max_memory_step = "N/A"
        step_start = False
        warnings_step = []
        errors_step = []
        for line in cwltool_output_lines:
            if not step_start and f"[step {step}] start" in line:
                start_time_step = datetime.datetime.strptime(
                    line[:21], "[%Y-%m-%d %H:%M:%S]"
                )
                step_start = True
            elif step_start:
                if f"[job {step}] Max memory used" in line:
                    max_memory_step = int(
                        line.split()[-1].rstrip(line.split()[-1][-3:])
                    )
                    if line.split()[-1].endswith("GiB"):
                        max_memory_step = max_memory_step * 1024
                    max_memory_step = max(1, max_memory_step)
                elif "warning" in line.lower():
                    if not is_line_useless(line):
                        warnings_step.append(line)
                elif "error" in line.lower():
                    if not is_line_useless(line):
                        errors_step.append(line)
                if f"[job {step}] completed permanentFail" in line or f"ERROR [step {step}]" in line:
                    end_time_step = datetime.datetime.strptime(
                        line[:21], "[%Y-%m-%d %H:%M:%S]"
                    )
                    break

        all_errors.extend(errors_step)
        all_warnings.extend(warnings_step)

        # set the minimum execution time to 1 second. Decimal values cannot be retrieved from the cwltool output, so the number of seconds is rounded up.
        execution_time_step = int((end_time_step - start_time_step).total_seconds())

        # store the benchmark values for each successfully executed step
        for entry in step_results:
            if entry["step"] == step:
                entry["status"] = "✗"
                entry["time"] = max(1, execution_time_step)
                entry["memory"] = max_memory_step
                entry["warnings"] = warnings_step
                entry["errors"] = errors_step
    return step_results