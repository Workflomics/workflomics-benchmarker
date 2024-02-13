import subprocess
from pathlib import Path
import os
import re
import datetime
import json
from typing import Dict, Literal

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
        "0-1": 0,
        "2-3": -0.25,
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
            r"\[job (.+)\] completed permanentFail"
        )  # pattern to match the failure of a step
        success_steps = set()
        step_results = [
            {
                "step": step,
                "status": "fail",
                "time": "unknown",
                "memory": "unknown",
                "warnings": "unknown",
                "errors": "unknown",
            }
            for step in steps
        ]
        for (
            line
        ) in (
            output_lines
        ):  # iterate over the output of the workflow and find which steps were executed successfully
            if success_pattern.search(line):
                success_steps.add(success_pattern.search(line).group(1))
            elif fail_pattern.search(line):
                for entry in step_results:
                    if entry["step"] == fail_pattern.search(line).group(1):
                        entry["status"] = "fail"
                        entry["time"] = "unknown"
                        entry["memory"] = "unknown"
                        entry["warnings"] = "unknown"
                        entry["errors"] = "unknown"

        for (
            step
        ) in (
            success_steps
        ):  # iterate over the output of the workflow and find the benchmark values for each step
            max_memory_step = "unknown"
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
                    entry["status"] = "✔"
                    entry["time"] = execution_time_step
                    entry["memory"] = max_memory_step
                    entry["warnings"] = warnings_step
                    entry["errors"] = errors_step

        workflow_status = "✔"
        for entry in step_results:  # check if the workflow was executed successfully
            if entry["status"] == "fail" or entry["status"] == "unknown":
                workflow_status = "fail"
                break

        self.workflow_benchmark_result = {
            "n_steps": len(steps),
            "status": workflow_status,
            "steps": step_results,
        }

    def calculate_benchmark_value(self, benchmark_name) -> int | Literal["fail", "unknown"]:
        """Calculate the benchmark value for the given benchmark.

        Parameters
        ----------
        benchmark_name: str
            The name of the benchmark to calculate.
        
        Returns
        -------
        value: int | Literal["fail", "unknown"]
            The value of the benchmark.
        """
        value: int = 0
        for entry in self.workflow_benchmark_result["steps"]:
            match benchmark_name:
                case "status":
                    if entry[benchmark_name] != "fail":
                        value = value + 1
                    else:
                        return "fail"
                case "time":
                    if entry[benchmark_name] != "unknown":
                        value = value + entry["time"]
                    else:
                        return "unknown"
                case "memory":
                    if entry[benchmark_name] != "unknown":
                        # remove last 3 characters from string (MiB, GiB, etc.)
                        value = max(value, entry["memory"])
                    else:
                        return "unknown"
                case "warnings":
                    if entry[benchmark_name] != "unknown":
                        value = value + len(entry["warnings"])
                    else:
                        return value
                case "errors":
                    if entry[benchmark_name] != "unknown":
                        value = value + len(entry["errors"])
                    else:
                        return value
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
                return 1 if value == "✔" else 0
            case "errors":
                if isinstance(value, list):
                    value = len(value)
                return 0 if value == 0 else -1
            case "time":
                if value == "unknown":
                    return 0
                bins = self.EXECUTION_TIME_DESIRABILITY_BINS
            case "memory":
                if value == "unknown":
                    return 0
                bins = self.MAX_MEMORY_DESIRABILITY_BINS
            case "warnings":
                bins = self.WARNINGS_DESIRABILITY_BINS
                if isinstance(value, list):
                    value = len(value)
        print(value)
        for bin in bins.keys():
            if value <= int(bin.split("-")[1]):
                return bins[bin]
        return 0

    def get_benchmark(self, name) :
        """Get a benchmark from the benchmark data."""
        benchmark = []
        for entry in self.workflow_benchmark_result["steps"]:
            if name == "errors" or name == "warnings":
                tooltip = {"tooltip": entry[name]}
                val = len(entry[name])
            else:
                val = (entry[name])
                tooltip = {}
            step_benchmark = {
                "label": entry["step"].rstrip(
                    "_0123456789"
                ),  # Label the step without the number at the end
                "value": val,
                "desirability": (
                    0
                    if entry["status"] == "fail" or entry["status"] == "unknown"
                    else self.calc_desirability(name, val)
                ),
            }
            step_benchmark.update(tooltip)
            benchmark.append(step_benchmark)
        return benchmark

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
                self.workflow_benchmark_result["status"] == "fail"
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

            all_workflow_data["benchmarks"].append(
                {
                    "description": "Status for each step in the workflow",
                    "title": "Status",
                    "unit": "status or fail",
                    "aggregate_value": {
                        "value": str(self.calculate_benchmark_value("status")),
                        "desirability": self.calc_desirability(
                            "status", self.calculate_benchmark_value("status")
                        ),
                    },
                    "steps": self.get_benchmark("status"),
                }
            )
            all_workflow_data["benchmarks"].append(
                {
                    "description": "Execution time for each step in the workflow",
                    "title": "Execution time",
                    "unit": "seconds",
                    "aggregate_value": {
                        "value": self.calculate_benchmark_value("time"),
                        "desirability": self.calc_desirability(
                            "time", self.calculate_benchmark_value("time")
                        ),
                    },
                    "steps": self.get_benchmark("time"),
                }
            )
            all_workflow_data["benchmarks"].append(
                {
                    "description": "Memory usage for each step in the workflow",
                    "title": "Memory usage",
                    "unit": "MB",
                    "aggregate_value": {
                        "value": self.calculate_benchmark_value("memory"),
                        "desirability": self.calc_desirability(
                            "memory", self.calculate_benchmark_value("memory")
                        ),
                    },
                    "steps": self.get_benchmark("memory"),
                }
            )
            all_workflow_data["benchmarks"].append(
                {
                    "description": "Warnings for each step in the workflow",
                    "title": "Warnings",
                    "unit": "count",
                    "aggregate_value": {
                        "value": self.calculate_benchmark_value("warnings"),
                        "desirability": self.calc_desirability(
                            "warnings", self.calculate_benchmark_value("warnings")
                        ),
                    },
                    "steps": self.get_benchmark("warnings"),
                }
            )
            all_workflow_data["benchmarks"].append(
                {
                    "description": "Errors for each step in the workflow",
                    "title": "Errors",
                    "unit": "count",
                    "aggregate_value": {
                        "value": self.calculate_benchmark_value("errors"),
                        "desirability": self.calc_desirability(
                            "errors", self.calculate_benchmark_value("errors")
                        ),
                    },
                    "steps": self.get_benchmark("errors"),
                }
            )

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
