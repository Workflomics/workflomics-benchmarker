import subprocess
from pathlib import Path
import os
import re
import datetime
import json
from typing import Dict

from workflomics_benchmarker.loggingwrapper import LoggingWrapper
from workflomics_benchmarker.cwltool_wrapper import CWLToolWrapper

class CWLToolRuntimeBenchmark(CWLToolWrapper):
    """Runtime benchmarking class  to gather information about the runtime of each step in a workflow."""

    KNOWN_USELESS_WARNINGS_ERRORS = ["WARNING: The requested image's platform", " 0 errors", "Calculating sensitivity...and error tables...", " 0 warnings"]
    EXECUTION_TIME_DESIRABILITY_BINS = {"0-150":1, "151-300":0.75, "301-450":0.5, "451-600":0.25, "601+":0}
    MAX_MEMORY_DESIRABILITY_BINS = {"0-250":1, "251-500":0.75, "501-750":0.5, "751-1000":0.25, "1001+":0}
    WARNINGS_DESIRABILITY_BINS = {"0-1":1, "2-3":0.75, "4-5":0.5, "6-7":0.25, "8+":0}

    def __init__(self, args):
        super().__init__(args)
        self.workflow_benchmark_result = {}
       

    def is_line_useless(self,line):
        """Check if a line is useless for the benchmarking."""
        for useless in self.KNOWN_USELESS_WARNINGS_ERRORS:
            if useless in line:
                return True
        return False

    def run_workflow(self, workflow):

        """Run a workflow and gather information about the runtime of each step."""
        command = ['cwltool']

        
        if  self.container == "singularity": #use singularity if the flag is set
            LoggingWrapper.warning("Using singularity container, memory usage will not be calculated.")
            command.append('--singularity')

        self.workflow_outdir = os.path.join(self.outdir, Path(workflow).name + "_output") #create the output directory for the workflow
        Path(self.workflow_outdir).mkdir(exist_ok=True) #create the output directory for the workflow
        command.extend(['--disable-color', '--timestamps', '--outdir', self.workflow_outdir, workflow, self.input_yaml_path])  #add the required option in cwltool to disable color and timestamps to enable benchmarking
        steps = self.extract_steps_from_cwl(workflow)
       
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')  #run the workflow
        if (self.verbose):
            print(result.stdout)
        output_lines = result.stdout.split('\n')
        success_pattern = re.compile(r'\[job (.+)\] completed success') #pattern to match the success of a step
        fail_pattern = re.compile(r'\[job (.+)\] completed permanentFail') #pattern to match the failure of a step
        success_steps = set()
        step_results = [{"step": step, "status": "fail", "time": "unknown", "memory": "unknown", "warnings": "unknown", "errors": "unknown"} for step in steps]
        for line in output_lines: # iterate over the output of the workflow and find which steps were executed successfully
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

    
        for step in success_steps: # iterate over the output of the workflow and find the benchmark values for each step
            max_memory_step = "unknown"
            step_start = False
            warnings_step = []
            errors_step = []
            for line in output_lines:
                if f'[step {step}] start' in line:
                    start_time_step = datetime.datetime.strptime(line[:21], '[%Y-%m-%d %H:%M:%S]')
                    step_start = True
                elif f'[job {step}] completed success' in line:
                    end_time_step = datetime.datetime.strptime(line[:21], '[%Y-%m-%d %H:%M:%S]')
                    break
                elif step_start:
                    if f'[job {step}] Max memory used' in line:
                        max_memory_step = int(line.split()[-1].rstrip(line.split()[-1][-3:]))
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
                execution_time_step = 1
            for entry in step_results: # store the benchmark values for each successfully executed step
                if entry["step"] == step:
                    entry["status"] = "success"
                    entry["time"] = execution_time_step
                    entry["memory"] = max_memory_step
                    entry["warnings"] = warnings_step
                    entry["errors"] = errors_step

        workflow_status  =  "success"
        for entry in step_results: # check if the workflow was executed successfully
            if entry["status"] == "fail" or entry["status"] == "unknown":
                workflow_status = "fail"
                break

        self.workflow_benchmark_result = {
            "n_steps": len(steps),
            "status": workflow_status,
            "steps": step_results,
        }

    def calc_value(self, name):
        """Calculate the benchmark values for the given benchmark."""
        if name == "status":
            value = 0
            for entry in self.workflow_benchmark_result["steps"]:
                if entry[name] != "fail":
                    value = value + 1
                else:
                    return "fail"
        elif name == "time":
            value = 0
            for entry in self.workflow_benchmark_result["steps"]:
                if entry[name] != "unknown":
                    value = value + entry["time"]
                else:
                    return "unknown"
        elif name == "memory":
            value = 0
            for entry in self.workflow_benchmark_result["steps"]:
                if entry[name] != "unknown":
                    # remove last 3 characters from string (MiB, GiB, etc.)
                    value = max(value, entry["memory"])
                else:
                    return "unknown"
        elif name == "warnings":
            value = 0
            for entry in self.workflow_benchmark_result["steps"]:
                if entry[name] != "unknown":
                    value = value + len(entry["warnings"])
                else:
                    return value
        elif name == "errors":
            value = 0
            for entry in self.workflow_benchmark_result["steps"]:
                if entry[name] != "unknown":
                    value = value + len(entry["errors"])
                else:
                    return value
        return value
    
    def calc_desirability(self, name, value):
        """Calculate the desirability for the given benchmark value."""
        if name == "status":
            if value == "success":
                return 1
            else:
                return 0
        elif name == "errors":
            if(isinstance(value, list)):
                count = len(value)
            else:
                count = value
            if count == 0:
                return 0
            else:
                return -1
        elif name == "time":
            if value == "unknown":
                return 0
            bins = self.EXECUTION_TIME_DESIRABILITY_BINS
            count = value
        elif name == "memory":
            if value == "unknown":
                return 0
            bins = self.MAX_MEMORY_DESIRABILITY_BINS
            count = value
        elif name == "warnings":
            bins = self.WARNINGS_DESIRABILITY_BINS
            if(isinstance(value, list)):
                count = len(value)
            else:
                count = value
           
        for bin in bins.keys():
            if "-" in bin:
                if count <= int(bin.split("-")[1]):
                    return bins[bin]
        return 0

    
    def get_benchmark(self, name):
        """Get a benchmark from the benchmark data."""
        benchmark = []
        for entry in self.workflow_benchmark_result["steps"]:
                step_benchmark = {
                    "label": entry["step"].rstrip('0123456789'), # Label the step without the number at the end
                    "value": entry[name],
                    "desirability": 0 if entry["status"] == "fail" or entry["status"] == "unknown" else self.calc_desirability(name, entry[name])
                }
                benchmark.append(step_benchmark)
        return benchmark

    def run_workflows(self):
        """Run the workflows in the given directory and store the results in a json file."""
        success_workflows = []
        failed_workflows = []
        workflows_benchmarks = []
       
        for workflow_path in self.workflows:  # iterate over the workflows and execute them
            workflow_name = Path(workflow_path).name
            LoggingWrapper.info("Benchmarking " + workflow_name + "...", color="green")
            self.run_workflow(workflow_path)
            if self.workflow_benchmark_result["status"] == "fail": # check if the workflow was executed successfully
                LoggingWrapper.error(workflow_name + " failed")
                failed_workflows.append(workflow_name)
            else:
                LoggingWrapper.info(workflow_name + " finished successfully.", color="green")
                success_workflows.append(workflow_name)
            LoggingWrapper.info(f"Output of {workflow_name} is stored in {self.workflow_outdir}. It may be empty if the workflow failed.")
            LoggingWrapper.info("Benchmarking " + workflow_name + " completed.", color="green")
            # store the benchmark results for each workflow in a json file
            all_workflow_data = {
            "workflowName": "",
            "executor": "cwltool " + self.version,
            "runID": "39eddf71ea1700672984653",
            "inputs":{key: {"filename": self.input[key]["filename"]} for key in self.input},
            "benchmarks": []
            }
           
            all_workflow_data["workflowName"] = workflow_name

            all_workflow_data["benchmarks"].append({
                                                    "description": "Status for each step in the workflow",
                                                    "title": "Status",
                                                    "unit": "status",
                                                    "aggregate_value": {
                                                        "value": str(self.calc_value("status")),
                                                        "desirability": self.calc_desirability("status", self.calc_value("status"))
                                                    },
                                                    "steps": self.get_benchmark("status"),
                                                    })
            all_workflow_data["benchmarks"].append({
                                                    "description": "Execution time for each step in the workflow",
                                                    "title": "Execution time",
                                                    "unit": "seconds",
                                                    "aggregate_value": {
                                                        "value": self.calc_value("time"),
                                                        "desirability": self.calc_desirability("time", self.calc_value("time"))
                                                    },
                                                    "steps": self.get_benchmark("time"),
                                                    })
            all_workflow_data["benchmarks"].append({
                                                    "description": "Memory usage for each step in the workflow",
                                                    "title": "Memory usage",
                                                    "unit": "MB",
                                                    "aggregate_value": {
                                                        "value": self.calc_value("memory"),
                                                        "desirability": self.calc_desirability("memory", self.calc_value("memory"))
                                                    },
                                                    "steps": self.get_benchmark("memory"),
                                                    })
            all_workflow_data["benchmarks"].append({
                                                    "description": "Warnings for each step in the workflow",
                                                    "title": "Warnings",
                                                    "unit": "warning count",
                                                    "aggregate_value": {
                                                        "value": self.calc_value("warnings"),
                                                        "desirability": self.calc_desirability("warnings", self.calc_value("warnings"))
                                                    },
                                                    "steps": self.get_benchmark("warnings"),
                                                    })
            all_workflow_data["benchmarks"].append({
                                                    "description": "Errors for each step in the workflow",
                                                    "title": "Errors",
                                                    "unit": "error count",
                                                    "aggregate_value": {
                                                        "value": self.calc_value("errors"),
                                                        "desirability": self.calc_desirability("errors", self.calc_value("errors"))
                                                    },
                                                    "steps": self.get_benchmark("errors"),
                                                    })

            workflows_benchmarks.append(all_workflow_data)


        with open(os.path.join(self.outdir, "benchmarks.json"), 'w') as f:
            json.dump(workflows_benchmarks, f, indent=3)
            LoggingWrapper.info("Benchmark results stored in " + os.path.join(self.outdir, "benchmarks.json"), color="green")    
        LoggingWrapper.info("Benchmarking completed.", color="green", bold=True)
        LoggingWrapper.info("Total number of workflows benchmarked: " + str(len(self.workflows)))
        LoggingWrapper.info("Number of workflows failed: " + str(len(failed_workflows)))
        LoggingWrapper.info("Number of workflows finished successfully: " + str(len(success_workflows)))
        LoggingWrapper.info("Successful workflows: " + ", ".join(success_workflows))
        LoggingWrapper.info("Failed workflows: " + ", ".join(failed_workflows))
            