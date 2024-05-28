import json
import jsonpath_ng.ext
import re
import os

import pandas as pd
from lxml import etree



def benchmark_gProfiler(path_to_output: str) -> int:
    """
    Count the number of significantly enriched unique GO-terms with a p-value < 0.001.

    Parameters
    ----------
    pethia_output : str
        The path to the g:Profiler output JSON file.
    
    Returns
    -------
    int
        The number of significantly enriched unique GO-terms.
    """

    # Load the g:Profiler output JSON:
    data = json.load(open(path_to_output))

    # Definte jsonpath for terms enriched with a p-value < 0.001:
    jsonpath_expr = jsonpath_ng.ext.parse('$.result[?(@.p_value < 0.001)].native')

    # Define regular expression for GO-terms:
    regex = re.compile(r'GO:')

    # Extract significantly enriched GO-terms:
    all_terms = [match.value for match in jsonpath_expr.find(data)]
    go_terms = [item for item in all_terms if regex.search(str(item))]

    # Return the number of significantly enriched unique GO-terms:
    try:
        return len(list(set(go_terms)))
    except (IndexError, TypeError) as e:
        print(f"Warning: {e}")
        return 0


def benchmark_goenrichment(path_to_output: str) -> int:
    """
    Benchmark the GOEnrichment output. It currently reads the three TSV files from the GOEnrichment output, 
    however, our implementation will only output one TSV file.
    """ 
    # Read and merge the three TSV files from the GOEnrichment output:
    df_BP = pd.read_csv("BP_result.txt", sep='\t')
    df_CC = pd.read_csv("CC_result.txt", sep='\t')
    df_MF = pd.read_csv("MF_result.txt", sep='\t')
    merged_df = pd.concat([df_BP, df_CC, df_MF])

    """Extract GO terms enriched with a p-value < 0.001:"""

    go_terms = merged_df["GO Term"]
    go_terms = merged_df.loc[merged_df['p-value'] < 0.001]["GO Term"]

    """Count the number of significantly enriched unique GO-terms:"""
    try:
        return len(list(set(go_terms)))
    except (IndexError, TypeError) as e:
        print(f"Warning: {e}")
        return 0
    



def benchmark_peptideprophet(path_to_output: str) -> int:
    tree = etree.parse(path_to_output) # the PeptideProphet output, regardless of search engine (Comet, X!Tandem), e.g., 'interact.pep.xml'
    root = tree.getroot()
    namespaces = {'pepxml': 'http://regis-web.systemsbiology.net/pepXML'}
    benchmark = root.xpath('//pepxml:msms_pipeline_analysis/pepxml:analysis_summary/pepxml:peptideprophet_summary/pepxml:roc_error_data[@charge="all"]//pepxml:error_point[@error<=0.01]/@num_corr', namespaces=namespaces)
    try:
        return int(benchmark[len(benchmark)-1])
    except (IndexError, TypeError) as e:
        print(f"Warning: {e}")
        return 0

    
def benchmark_proteinprophet(path_to_output: str) -> int:
    """ProteinProphet ProtXML benchmark"""

    tree = etree.parse(path_to_output) # the ProteinProphet output, regardless of search engine (Comet, X!Tandem), e.g., 'interact.prot.xml'
    root = tree.getroot()
    namespaces = {'protxml': 'http://regis-web.systemsbiology.net/protXML'}
    benchmark = root.xpath('//protxml:protein_summary/protxml:protein_summary_header/protxml:program_details/protxml:proteinprophet_details//protxml:error_point[@error<=0.01]/@num_corr', namespaces=namespaces)
    try:
        return int(benchmark[len(benchmark)-1])
    except (IndexError, TypeError) as e:
        print(f"Warning: {e}")
        return 0



def calculate_output_file(dir_path, workflow_name, output_name):
    """
    Calculate the path to the output file for a given workflow.
    """
    return os.path.join(dir_path, workflow_name + "_output", output_name)