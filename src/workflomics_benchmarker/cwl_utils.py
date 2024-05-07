from pathlib import Path
from typing import List
import yaml
import subprocess
import sys

def extract_steps_from_cwl(workflow_file) -> List[str]:
        """Extract the step (tool) names from the cwl workflow file in the order they are defined.
        
        Parameters
        ----------
        workflow_file : str
            The path to the cwl workflow file.
            
        Returns
        -------
        List[str]
            The list of step names.
        """
        with open(workflow_file, 'r') as file:
            data = yaml.safe_load(file)
        steps = []
        for step_name in data.get('steps', {}):
            steps.append(step_name)
        return steps