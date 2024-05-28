import os
import subprocess
from pathlib import Path

from workflomics_benchmarker.cwltool_wrapper import CWLToolWrapper
from workflomics_benchmarker.loggingwrapper import LoggingWrapper

class CWLToolRunner(CWLToolWrapper):
    """
    Class to manage and run CWL (Common Workflow Language) workflows.
    """
    success_workflows : list = []
    failed_workflows : list = []

    def __init__(self, args):
        """
        Constructs all the necessary attributes for the CWLToolRunner object.

        Parameters
        ----------
        args : dict
            Arguments necessary for initializing the CWLToolWrapper parent class.
        """
        super().__init__(args)

    def _construct_command(self, workflow_path):
        """
        Constructs the command to run the workflow using cwltool.

        Parameters
        ----------
        workflow_path : str
            Path to the CWL workflow file.

        Returns
        -------
        list
            A list of command segments to execute the workflow.
        """
        base_command = ['cwltool --on-error continue']
        if self.container == "singularity":
            base_command.append('--singularity')

        workflow_name = Path(workflow_path).stem
        output_directory = os.path.join(self.outdir, f"{workflow_name}_output")
        Path(output_directory).mkdir(exist_ok=True)

        return base_command + ['--outdir', output_directory, workflow_path, self.input_yaml_path], output_directory

    def _execute_command(self, command, workflow_name):
        """
        Executes the constructed command and processes the output.

        Parameters
        ----------
        command : list
            The command to run as a list of arguments.
        workflow_name : str
            The name of the workflow being executed.

        Returns
        -------
        bool
            True if the workflow executed successfully, False otherwise.
        """
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(result.stdout)

        if result.returncode == 0:
            LoggingWrapper.info(f"Workflow {workflow_name} finished successfully.", color="green")
            return True
        else:
            LoggingWrapper.error(f"Workflow {workflow_name} failed.", color="red")
            return False

    def execute_workflow(self, workflow_path):
        """
        Execute a single workflow using specified parameters and log the result.

        Parameters
        ----------
        workflow_path : str
            The path to the workflow file.
        """
        command, output_directory = self._construct_command(workflow_path)
        workflow_name = Path(workflow_path).stem
        if self._execute_command(command, workflow_name):
            self.success_workflows.append(workflow_name)
        else:
            self.failed_workflows.append(workflow_name)
        LoggingWrapper.info(f"Output is stored in {output_directory}.")

    def run_workflows(self):
        """
        Execute all specified workflows and summarize the results.
        """
        for workflow_path in self.workflows:
            self.execute_workflow(workflow_path)
        total_workflows = len(self.success_workflows) + len(self.failed_workflows)
        LoggingWrapper.info(f"Execution summary: {total_workflows} total, {len(self.success_workflows)} succeeded, {len(self.failed_workflows)} failed.")
