import subprocess
from pathlib import Path
import os
import re
import datetime
import json
from typing import Dict, List, Literal

from workflomics_benchmarker.loggingwrapper import LoggingWrapper
from workflomics_benchmarker.cwltool_wrapper import CWLToolWrapper


class CWLToolRuntimeBenchmark(CWLToolWrapper):
    """Runtime benchmarking class  to gather information about the runtime of each step in a workflow."""

    KNOWN_USELESS_WARNINGS_ERRORS = [
        "WARNING: The requested image's platform",
        " 0 errors",
        "Calculating sensitivity...and error tables...",
        " 0 warnings",
    ]
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
        self.workflow_benchmark_result = {}


    def is_line_useless(self, line):
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
        for useless in self.KNOWN_USELESS_WARNINGS_ERRORS:
            if useless in line:
                return True
        return False

    def run_workflow(self, workflow) -> None:
        """Run a workflow and gather information about the runtime of each step.

        Parameters
        ----------
        workflow: str
            The path to the workflow file.
        
        Returns
        -------
        None
        """
        command = ["cwltool"]

        if self.container == "singularity":  # use singularity if the flag is set
            LoggingWrapper.warning(
                "Using singularity container, memory usage will not be calculated."
            )
            command.append("--singularity")

        self.workflow_outdir = os.path.join(
            self.outdir, Path(workflow).name + "_output"
        )  # create the output directory for the workflow
        Path(self.workflow_outdir).mkdir(
            exist_ok=True
        )  # create the output directory for the workflow
        command.extend(
            [
                "--disable-color",
                "--timestamps",
                "--outdir",
                self.workflow_outdir,
                workflow,
                self.input_yaml_path,
            ]
        )  # add the required option in cwltool to disable color and timestamps to enable benchmarking
        steps = self.extract_steps_from_cwl(workflow)
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )  # run the workflow
        if self.verbose:
            print(result.stdout)
        output_lines = result.stdout.split("\n")
        success_pattern = re.compile(
            r"\[job (.+)\] completed success"
        )  # pattern to match the success of a step
        fail_pattern = re.compile(
            r"\[job (.+)\] completed permanentFail|ERROR Exception on step '([^']+)'"
        )  # pattern to match the failure of a step
        success_steps = set()  #Set of step names that were executed successfully.
        step_results = [
            {
                "step": step,
                "status": "-",
                "time": "N/A",
                "memory": "N/A",
                "warnings": "N/A",
                "errors": "N/A",
            }
            for step in steps
        ]

        for (
            line
        ) in (
            output_lines
        ):  # iterate over the output of the workflow and find which steps were executed successfully
            successfull_match = success_pattern.search(line)
            failed_match = fail_pattern.search(line)
            if successfull_match:
                success_steps.add(successfull_match.group(1))
            elif failed_match:
                failed_tool_name = failed_match.group(1) if failed_match.group(1) is not None else failed_match.group(2)
                for entry in step_results:
                    # set the benchmark values for the failed steps to N/A
                    if entry["step"] == failed_tool_name:
                        entry["status"] = "✗"
                        entry["time"] = "N/A"
                        entry["memory"] = "N/A"
                        entry["warnings"] = "N/A"
                        entry["errors"] = "N/A"
        for (
            step
        ) in (
            success_steps
        ):  # iterate over the output of the workflow and find the benchmark values for each step
            max_memory_step = "N/A"
            step_start = False
            warnings_step = []
            errors_step = []
            for line in output_lines:
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
                        if max_memory_step == 0:
                            max_memory_step = 1
                    elif "warning" in line.lower():
                        if not self.is_line_useless(line):
                            warnings_step.append(line)
                    elif "error" in line.lower():
                        if not self.is_line_useless(line):
                            errors_step.append(line)

            execution_time_step = int((end_time_step - start_time_step).total_seconds())
            if execution_time_step == 0:
                execution_time_step = 1 # set the minimum execution time to 1 second. Decimal values cannot be retrieved from the cwltool output, so the number of seconds is rounded up.
            for (
                entry
            ) in (
                step_results
            ):  # store the benchmark values for each successfully executed step
                if entry["step"] == step:
                    entry["status"] = "✓"
                    entry["time"] = execution_time_step
                    entry["memory"] = max_memory_step
                    entry["warnings"] = warnings_step
                    entry["errors"] = errors_step

        workflow_status = "✓"
        for entry in step_results:  # check if the workflow was executed successfully
            if entry["status"] == "✗" or entry["status"] == "-":
                workflow_status = "✗"
                break

        self.workflow_benchmark_result = {
            "n_steps": len(steps),
            "status": workflow_status,
            "steps": step_results,
        }

    def aggregate_workflow_benchmark_value(self, benchmark_name) -> int | Literal["✗", "N/A"]:
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
        for index, entry in enumerate(self.workflow_benchmark_result["steps"], start=1):
            match benchmark_name:
                case "status":
                    if entry[benchmark_name] != "✗" and entry[benchmark_name] != "-":
                        value = "✓"
                    else:
                        return  f"({index-1}/{len(self.workflow_benchmark_result['steps'])}) ✗"
                case "time":
                    if entry[benchmark_name] != "N/A":
                        value = value + entry["time"]
                    else:
                        return "N/A"
                case "memory":
                    if entry[benchmark_name] != "N/A":
                        # remove last 3 characters from string (MiB, GiB, etc.)
                        value = max(value, entry["memory"])
                    else:
                        return "N/A"
                case "warnings":
                    value = value + len(entry["warnings"])
                case "errors":
                    value = value + len(entry["errors"])
        return value

    def calc_desirability(self, benchmark_name, value):
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
                if value == "N/A":
                    return 0
                bins = self.EXECUTION_TIME_DESIRABILITY_BINS
            case "memory":
                if value == "N/A":
                    return 0
                bins = self.MAX_MEMORY_DESIRABILITY_BINS
            case "warnings":
                bins = self.WARNINGS_DESIRABILITY_BINS
                if isinstance(value, list):
                    value = len(value)
        for key, value in bins.items():
            if "-" in key:
                if value <= int(key.split("-")[1]):
                    return bins[key]
            else:
                return bins[key]
        return 0

    def get_step_benchmarks(self, name) -> List[dict]:
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
        for entry in self.workflow_benchmark_result["steps"]:
            # each step 'entry' is either having a numeric value, or is "N/A" in case it was not executed. Special case are the status entries, which are either "✓", "✗" or "-" (when not reached).
            val = (entry[name])
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
                    -1
                    if entry["status"] == "✗"
                    else self.calc_desirability(name, val)
                ),
            }
            step_benchmark.update(tooltip)
            benchmark.append(step_benchmark)
        return benchmark
    
    def add_benchmark(self, benchmarks, description, title, unit, key):
        """
        Adds a benchmark entry to the provided list.

        Parameters:
        - benchmarks (list): A list to which the benchmark data will be appended.
        - description (str): A description of the benchmark.
        - title (str): The title of the benchmark.
        - unit (str): The unit of measurement for the benchmark data.
        - key (str): The key used to fetch and calculate benchmark values from the workflow.

        Example:
        >>> add_benchmark(benchmarks, "Status for each step in the workflow", "Status", "✓ or ✗", "status")
        """
        benchmarks.append({
            "description": description,
            "title": title,
            "unit": unit,
            "aggregate_value": {
                "value": self.aggregate_workflow_benchmark_value(key),
                "desirability": self.calc_desirability(
                    key, self.aggregate_workflow_benchmark_value(key)
                ),
            },
            "steps": self.get_step_benchmarks(key),
        })

    def compute_technical_benchmarks(self) -> List[dict]:
        """
        Compute the technical benchmarks for the workflow.

        Returns:
        - List[dict]: A list of technical benchmarks.
        """
        technical_benchmarks = []  # Define the "benchmarks" variable
        self.add_benchmark(technical_benchmarks, "Status for each step in the workflow", "Status", "✓ or ✗", "status")
        self.add_benchmark(technical_benchmarks, "Execution time for each step in the workflow", "Execution time", "seconds", "time")
        self.add_benchmark(technical_benchmarks, "Memory usage for each step in the workflow", "Memory usage", "MB", "memory")
        self.add_benchmark(technical_benchmarks, "The number of identified significantly enriched unique GO-terms.", "GO-terms identified", "count", "warnings")
        self.add_benchmark(technical_benchmarks, "Warnings for each step in the workflow", "Warnings", "count", "warnings")
        self.add_benchmark(technical_benchmarks, "Errors for each step in the workflow", "Errors", "count", "errors")
            
        return technical_benchmarks
    
    def compute_scientific_benchmarks(self) -> List[dict]:
        """
        Compute the scientific benchmarks for the workflow.

        Returns:
        - List[dict]: A list of scientific benchmarks.
        """
        benchmarks = []

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
            self.run_workflow(workflow_path)
            if (
                self.workflow_benchmark_result["status"] == "✗"
            ):  # check if the workflow was executed successfully
                LoggingWrapper.error(workflow_name + " failed")
                failed_workflows.append(workflow_name)
            else:
                LoggingWrapper.info(
                    workflow_name + " finished successfully.", color="green"
                )
                success_workflows.append(workflow_name)
            LoggingWrapper.info(
                f"Output of {workflow_name} is stored in {self.workflow_outdir}. It may be empty if the workflow failed."
            )
            LoggingWrapper.info(
                "Benchmarking " + workflow_name + " completed.", color="green"
            )
            # store the benchmark results for each workflow in a json file
            all_workflow_data = {
                "workflowName": "",
                "executor": "cwltool " + self.version,
                "runID": "39eddf71ea1700672984653",
                "inputs": {
                    key: {"filename": self.input[key]["filename"]} for key in self.input
                },
                "benchmarks": [],
            }

            all_workflow_data["workflowName"] = workflow_name

            all_workflow_data["benchmarks"] = self.compute_technical_benchmarks()
            
            # # TODO: FInish this
            # all_workflow_data["benchmarks"].append(
            #     {
            #         "description": "The number of identified significantly enriched unique GO-terms.",
            #         "title": "GO-terms identified",
            #         "unit": "count",
            #         "aggregate_value": {
            #             "value": self.aggregate_workflow_benchmark_value("warnings"),
            #             "desirability": self.calc_desirability(
            #                 "warnings", self.aggregate_workflow_benchmark_value("warnings")
            #             ),
            #         },
            #         "steps": self.get_step_benchmarks("warnings"),
            #     }
            # )


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
