"""The mathematical smoke verifier must fail closed on unsuccessful checks."""
import ast
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[2] / "sources/sympy/scripts/sympy_verify.py"


class TestSympyVerifierDecision(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_text())
        check = next(node for node in tree.body
                     if isinstance(node, ast.FunctionDef) and node.name == "check")
        self.state = {"FAILURES": [], "RESULTS": {}}
        exec(compile(ast.Module(body=[check], type_ignores=[]), str(SOURCE), "exec"), self.state)

    def test_successful_assertion_passes(self):
        self.state["check"]("correct", lambda: True)
        self.assertEqual(self.state["FAILURES"], [])

    def test_false_assertion_is_a_failure(self):
        self.state["check"]("wrong_result", lambda: False)
        self.assertEqual(len(self.state["FAILURES"]), 1)
        self.assertIn("wrong_result", self.state["FAILURES"][0])

    def test_exception_is_a_failure(self):
        def broken():
            raise ArithmeticError("cannot compute")
        self.state["check"]("arithmetic", broken)
        self.assertEqual(len(self.state["FAILURES"]), 1)
        self.assertIn("ArithmeticError", self.state["FAILURES"][0])
