"""Run the shared engine review controller tests in the catalog CI suite."""

from engines.impeccable.workflows.tools.tests import test_engine_review_pr


def load_tests(loader, tests, pattern):
    return loader.loadTestsFromModule(test_engine_review_pr)
