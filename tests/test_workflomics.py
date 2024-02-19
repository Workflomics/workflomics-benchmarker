from argparse import Namespace
from workflomics_benchmarker.cwltool_runtime_benchmark import CWLToolRuntimeBenchmark


def test_benchmark_run():
    """Test whether the benchmark run works. """
    # Simulate 'benchmark' command
    
    test_args = Namespace(workflows='tests/data/')
    
    runner  = CWLToolRuntimeBenchmark(test_args)
    runner.run_workflows()
    assert True