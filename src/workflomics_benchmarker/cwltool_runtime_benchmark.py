import subprocess
from pathlib import Path
import os
import json
from typing import List, Literal

from workflomics_benchmarker.loggingwrapper import LoggingWrapper
from workflomics_benchmarker.cwltool_wrapper import CWLToolWrapper

from workflomics_benchmarker.cwl_utils import extract_steps_from_cwl
from workflomics_benchmarker.benchmark_utils import (
    is_line_useless,
    create_output_dir,
    setup_empty_benchmark_for_step,
    step_success_pattern,
    step_fail_pattern,
    set_step_status_to_failed,
    benchmark_successful_step_execution,
    benchmark_failed_step_execution
)


class CWLToolRuntimeBenchmark(CWLToolWrapper):
    """Runtime benchmarking class  to gather information about the runtime of each step in a workflow."""

    EXECUTION_TIME_DESIRABILITY_BINS = {
        "0-150": 1,
        "151-300": 0.75,
        "301-450": 0.5,
        "451-600": 0.25,
        "601+": 0,
    }
    MAX_MEMORY_DESIRABILITY_BINS = {
        "0-250": 1,
        "251-500": 0.75,
        "501-750": 0.5,
        "751-1000": 0.25,
        "1001+": 0,
    }
    WARNINGS_DESIRABILITY_BINS = {
        "0-0": 0,
        "1-3": -0.25,
        "4-5": -0.5,
        "6-7": -0.75,
        "8+": -1,
    }

    def __init__(self, args):
        super().__init__(args)

    def execute_and_benchmark_workflow(self, workflow) -> dict:
        """
        Execute a single workflow, save the outputs and benchmark each step, i.e., tool, of the workflow.
        TODO: Split into execute and benchmark functions.
        Parameters
        ----------
        workflow: str
            The path to the workflow file.

        Returns
        -------
        dict
            A dictionary containing the benchmark results of the workflow.
        """
        workflow_execution_information = {}
        workflow_name = Path(workflow).name

        command = ["cwltool"]

        if self.container == "singularity":  # use singularity if the flag is set
            LoggingWrapper.warning(
                "Using singularity container, memory usage will not be calculated."
            )
            command.append("--singularity")

        workflow_outdir = create_output_dir(self.outdir, workflow_name)

        command.extend(
            [
                "--on-error",
                "continue",
                "--disable-color",
                "--timestamps",
                "--outdir",
                workflow_outdir,
                workflow,
                self.input_yaml_path,
            ]
        )  # add the required option in cwltool to disable color and timestamps to enable benchmarking
        steps = extract_steps_from_cwl(workflow)

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )  # run the workflow
        if self.verbose:
            print(result.stdout)
        cwltool_output_lines = result.stdout.split("\n")

        # Set of step names that were executed successfully.
        successfully_executed_steps = set()
        failed_steps = set()

        step_results = [setup_empty_benchmark_for_step(tool) for tool in steps]
        # iterate over the output of the workflow and find which steps were executed successfully
        for line in cwltool_output_lines:
            successful_match = step_success_pattern(line)
            if successful_match:
                successfully_executed_steps.add(successful_match.group(1))
            else:
                failed_match = step_fail_pattern(line)
                if failed_match:
                    failed_tool_name = (
                        failed_match.group(1)
                        if failed_match.group(1) is not None
                        else failed_match.group(2)
                    )
                    failed_steps.add(failed_tool_name)

        # iterate over the output of the workflow and find the benchmark values for each step
        step_results = benchmark_successful_step_execution(successfully_executed_steps, cwltool_output_lines, step_results, workflow_outdir)
        step_results = benchmark_failed_step_execution(failed_steps, cwltool_output_lines, step_results)
        workflow_status = "✓"
        for entry in step_results:  # check if the workflow was executed successfully
            if entry["status"] == "✗" or entry["status"] == "-":
                workflow_status = "✗"
                break

        workflow_execution_information = {
            "n_steps": len(steps),
            "status": workflow_status,
            "steps": step_results,
        }

        LoggingWrapper.info(
                "Benchmarking " + workflow_name + " completed.", color="green"
            )

        return workflow_execution_information

    def count_successful_steps(self, all_tools_exe) -> int:
        """Count the number of steps that were executed successfully.

        Parameters
        ----------
        step_results: List[dict]
            The list of step results.

        Returns
        -------
        int
            The number of steps that were executed successfully.
        """
        return len([tool_execution for tool_execution in all_tools_exe if tool_execution["status"] == "✓"])
    

    def aggregate_workflow_benchmark_value(
        self, benchmark_name, workflow_execution_information
    ) -> int | Literal["✗", "N/A"]:
        """Calculate the aggregate benchmark value for the given workflow.

        Parameters
        ----------
        benchmark_name: str
            The name of the benchmark to calculate.

        Returns
        -------
        value: int | Literal["✗", "N/A"]
            The value of the benchmark.
        """
        value: int = 0
        for tool_execution in workflow_execution_information["steps"]:
            match benchmark_name:
                case "status":
                    if tool_execution[benchmark_name] != "✗" and tool_execution[benchmark_name] != "-":
                        value = "✓"
                    else:
                        return f"({self.count_successful_steps(workflow_execution_information['steps'])}/{len(workflow_execution_information['steps'])}) ✗"
                case "time":
                    if tool_execution[benchmark_name] != "-":
                        value = value + tool_execution[benchmark_name]
                case "memory":
                    if tool_execution["memory"] not in ["-", "N/A"]:
                        # remove last 3 characters from string (MiB, GiB, etc.)
                        value = max(value, tool_execution["memory"])
                case "warnings":
                    value = value + len(tool_execution["warnings"])
                case "errors":
                    value = value + len(tool_execution["errors"])
                case "go_terms":
                    if tool_execution[benchmark_name] != "-":
                        value = value + tool_execution[benchmark_name]
                case "identified_proteins":
                    if tool_execution[benchmark_name] != "-":
                        value = value + tool_execution[benchmark_name]
        return value

    def calc_desirability(self, benchmark_name, value, status="✓"):
        """Calculate the desirability for the given benchmark value.

        Parameters
        ----------
        benchmark_name: str
            The name of the benchmark.
        value: int
            The value of the benchmark.

        Returns
        -------
        float
            The desirability of the benchmark value.
        """
        match benchmark_name:
            case "status":
                if value == "✓":
                    return 1
                elif value == "-":
                    return 0
                else:
                    return -1
            case "errors":
                if isinstance(value, list):
                    value = len(value)
                return 0 if value == 0 else -1
            case "time":
                if value == "-":
                    return 0
                elif status == "✗":
                    return -1
                bins = self.EXECUTION_TIME_DESIRABILITY_BINS
            case "memory":
                if value == "-":
                    return 0
                elif status == "✗":
                    return -1
                bins = self.MAX_MEMORY_DESIRABILITY_BINS
            case "warnings":
                bins = self.WARNINGS_DESIRABILITY_BINS
                if isinstance(value, list):
                    value = len(value)
            case "go_terms":
                if value == "-":
                    return 0
                if value == 0 or value > 1000:
                    return -1
                return 1
            case "identified_proteins":
                if value == "-":
                    return 0
                if value == 0 or value > 1000:
                    return -1
                return 1

        for key, value in bins.items():
            if "-" in key:
                if value <= int(key.split("-")[1]):
                    return bins[key]
            else:
                return bins[key]
        return 0

    def get_step_benchmarks(self, name, workflow_execution_information) -> List[dict]:
        """Get benchmark data for all the steps of the workflow for the given benchmark.

        Parameters
        ----------
        name: str
            The name of the benchmark.

        Returns
        -------
        List[dict]
            The list of benchmark data for all the steps of the workflow.
        """
        benchmark = []
        # iterate over the steps and store the benchmark values for each step
        for entry in workflow_execution_information["steps"]:
            # each step 'entry' is either having a numeric value, or is "N/A" in case it was not executed. Special case are the status entries, which are either "✓", "✗" or "-" (when not reached).
            val = entry[name]
            tooltip = {}
            if name == "errors" or name == "warnings":
                if (val) != "N/A" and len(entry[name]) > 0:
                    tooltip = {"tooltip": entry[name]}
                    val = len(entry[name])
                else:
                    val = 0

            step_benchmark = {
                "label": entry["step"].rstrip(
                    "_0123456789"
                ),  # Label the step without the number at the end
                "value": val,
                "desirability": (
                    -1 if entry["status"] == "✗" else self.calc_desirability(name, val)
                ),
            }
            step_benchmark.update(tooltip)
            benchmark.append(step_benchmark)
        return benchmark

    def create_benchmark(self, description, title, unit, key, workflow_execution_information) -> dict:
        """
        Create a benchmark json entry.

        Parameters
        ----------
        benchmarks : list
            A list to which the benchmark data will be appended.
        description : str
            A description of the benchmark.
        title : str
            The title of the benchmark.
        unit : str
            The unit of measurement for the benchmark data.
        key : str
            The key used to fetch and calculate benchmark values from the workflow.
        
        Returns
        -------
        dict
            A dictionary containing the benchmark data.

        """
        return {
                "description": description,
                "title": title,
                "unit": unit,
                "aggregate_value": {
                    "value": self.aggregate_workflow_benchmark_value(key, workflow_execution_information),
                    "desirability": self.calc_desirability(
                        key, self.aggregate_workflow_benchmark_value(key, workflow_execution_information), workflow_execution_information["status"]
                    ),
                },
                "steps": self.get_step_benchmarks(key, workflow_execution_information),
            }
        

    def compute_technical_benchmarks(self,workflow_execution_information) -> List[dict]:
        """
        Compute the technical benchmarks for the workflow.

        Returns:
        - List[dict]: A list of technical benchmarks.
        """
        technical_benchmarks = []  # Define the "benchmarks" variable
        technical_benchmarks.append(self.create_benchmark(
            "Status for each step in the workflow",
            "Status",
            "✓ or ✗",
            "status",
        workflow_execution_information))

        technical_benchmarks.append(self.create_benchmark(
            "Execution time for each step in the workflow",
            "Execution time",
            "seconds",
            "time",
        workflow_execution_information))
        
        technical_benchmarks.append(self.create_benchmark(
            "Memory usage for each step in the workflow",
            "Memory usage",
            "MB",
            "memory",
        workflow_execution_information))

        technical_benchmarks.append(self.create_benchmark(
            "Warnings for each step in the workflow",
            "Warnings",
            "count",
            "warnings",
        workflow_execution_information))

        technical_benchmarks.append(self.create_benchmark(
            "Errors for each step in the workflow",
            "Errors",
            "count",
            "errors",
        workflow_execution_information))

        technical_benchmarks.append(self.create_benchmark(
            "The number of identified proteins.",
            "Proteins",
            "count",
            "identified_proteins",
        workflow_execution_information))

        technical_benchmarks.append(self.create_benchmark(
            "The number of identified significantly enriched unique GO-terms.",
            "GO-terms",
            "count",
            "go_terms",
        workflow_execution_information))

        return technical_benchmarks


    def run_workflows(self) -> None:
        """Run the workflows in the given directory and store the results in a json file."""
        success_workflows = []
        failed_workflows = []
        workflows_benchmarks = []

        for (
            workflow_path
        ) in self.workflows:  # iterate over the workflows and execute them
            workflow_name = Path(workflow_path).name
            LoggingWrapper.info("Benchmarking " + workflow_name + "...", color="green")
            workflow_execution_information = self.execute_and_benchmark_workflow(workflow_path)
            
            if (workflow_execution_information["status"] == "✗"): 
                LoggingWrapper.error(workflow_name + " failed")
                failed_workflows.append(workflow_name)
            else:
                LoggingWrapper.info(
                    workflow_name + " finished successfully.", color="green"
                )
                success_workflows.append(workflow_name)
            
            # store the benchmark results for each workflow in a json file
            all_workflow_data = {
                "workflowName": workflow_name,
                "executor": "cwltool " + self.version,
                "runID": "39eddf71ea1700672984653",
                "inputs": {
                    key: {"filename": self.input[key]["filename"]} for key in self.input
                },
                "benchmarks": self.compute_technical_benchmarks(workflow_execution_information),
            }

            workflows_benchmarks.append(all_workflow_data)

        with open(os.path.join(self.outdir, "benchmarks.json"), "w") as f:
            json.dump(workflows_benchmarks, f, indent=3)
            LoggingWrapper.info(
                "Benchmark results stored in "
                + os.path.join(self.outdir, "benchmarks.json"),
                color="green",
            )
        LoggingWrapper.info("Benchmarking completed.", color="green", bold=True)
        LoggingWrapper.info(
            "Total number of workflows benchmarked: " + str(len(self.workflows))
        )
        LoggingWrapper.info("Number of workflows failed: " + str(len(failed_workflows)))
        LoggingWrapper.info(
            "Number of workflows finished successfully: " + str(len(success_workflows))
        )
        LoggingWrapper.info("Successful workflows: " + ", ".join(success_workflows))
        LoggingWrapper.info("Failed workflows: " + ", ".join(failed_workflows))
