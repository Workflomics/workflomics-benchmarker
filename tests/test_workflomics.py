import sys
from benchmarker.workflomics import main


def test_becnhmark_run(shared_datadir):
    """Test whether the benchmark run works. """
    # Simulate 'benchmark' command
    test_args = ['src/benchmarker/workflomics.py', 'benchmark', 'tests/data/']
    sys.argv = test_args
    main()
    assert True