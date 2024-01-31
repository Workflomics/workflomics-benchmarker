from cwltool_wrapper import CWLToolWrapper
import subprocess
from pathlib import Path
import re
import datetime
import json
from loggingwrapper import LoggingWrapper
import os

class CWLToolRunner(CWLToolWrapper):

    def __init__(self, args):
       
        super().__init__(args)
        self.success_workflows = []
        self.failed_workflows = []


    def run_workflow(self, workflow):
        command = ['cwltool']

        if  self.container == "singularity":
            command.append('--singularity')
        workflow_name = Path(workflow).name
        workflow_outdir = os.path.join(self.outdir, Path(workflow).name + "_output") #create the output directory for the workflow
        Path(workflow_outdir).mkdir(exist_ok=True) #create the output directory for the workflow
        command.extend([ '--outdir', workflow_outdir, workflow, self.input_yaml_path])
        LoggingWrapper.info(f"Running {workflow_name}...", color="green")
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')  #run the workflow 
        if (self.verbose):
            print(result.stdout)
        if result.returncode != 0:
            self.success_workflows.append(workflow_name)
            LoggingWrapper.error(f"Workflow {workflow_name} failed.", color="red")
        else:
            self.success_workflows.append(workflow_name)
            LoggingWrapper.info(f"Workflow {workflow_name} finished successfully.", color="green")
        
        LoggingWrapper.info(f"Output of {workflow_name} is stored in {workflow_outdir}. It may be empty if the workflow failed.")


    def run_workflows(self):
        """Run the workflows in the given directory"""

        for workflow_path in self.workflows:
            self.run_workflow(workflow_path)
        LoggingWrapper.info("Execution completed.", color="green", bold=True)
        LoggingWrapper.info("Total number of workflows executed: " + str(len(self.workflows)))
        LoggingWrapper.info("Number of workflows failed: " + str(len(self.failed_workflows)))
        LoggingWrapper.info("Number of workflows finished successfully: " + str(len(self.success_workflows)))
        LoggingWrapper.info("Successful workflows: " + ", ".join(self.success_workflows))
        LoggingWrapper.info("Failed workflows: " + ", ".join(self.failed_workflows))