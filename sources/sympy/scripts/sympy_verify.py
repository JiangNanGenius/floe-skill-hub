#!/usr/bin/env python3
"""Floe first-party SymPy environment verifier (guest-pending proof).

Purpose: before any SymPy workload, confirm the resolved Linux environment
actually provides the pinned SymPy 1.14 line with working core features.
Runs under exec.shell inside the task's Linux guest ONLY. No network, no
writes, no side effects. Prints a JSON result; exit 0 only when every
check passes. Written for the Floe Skill Hub by the Floe project (MIT,
see references/licenses); not upstream content.
"""
import json
import sys

FAILURES = []
RESULTS = {}

def check(name, fn):
    try:
        result = fn()
        RESULTS[name] = str(result)
        if result is not True:
            FAILURES.append(f"{name}: expected True, got {result!r}")
    except Exception as exc:  # noqa: BLE001 - report, never crash silently
        FAILURES.append(f"{name}: {type(exc).__name__}: {exc}")

try:
    import sympy
except ImportError:
    print(json.dumps({"ok": False, "failures": ["import sympy failed: SymPy is not installed in this environment"]}))
    sys.exit(2)

RESULTS["version"] = sympy.__version__
if sympy.__version__ != "1.14.0":
    FAILURES.append(f"version {sympy.__version__} does not match the pinned 1.14.0")

from sympy import (Matrix, Rational, Symbol, diff, dsolve, integrate,
                   latex, simplify, solveset, symbols)

x, y = symbols("x y", real=True)
check("exact_rational", lambda: Rational(1, 2) + Rational(1, 3) == Rational(5, 6))
check("simplify", lambda: simplify((x + y) ** 2 - x ** 2 - 2 * x * y - y ** 2) == 0)
check("derivative", lambda: simplify(diff(sympy.sin(x) * x ** 2, x) - (2 * x * sympy.sin(x) + x ** 2 * sympy.cos(x))) == 0)
check("integral", lambda: integrate(x ** 2, (x, 0, 1)) == Rational(1, 3))
check("solve", lambda: solveset(x ** 2 - 2, x, domain=sympy.S.Reals) == sympy.FiniteSet(-sympy.sqrt(2), sympy.sqrt(2)))
def verify_ode():
    f = sympy.Function("f")(x)
    solution = dsolve(sympy.Eq(f.diff(x), f))
    return solution.lhs == f and simplify(diff(solution.rhs, x) - solution.rhs) == 0

check("ode", verify_ode)
check("matrix_det", lambda: Matrix([[1, 2], [3, 4]]).det() == -2)
check("latex", lambda: "$" in latex(sympy.sqrt(x)) or "sqrt" in latex(sympy.sqrt(x)))

out = {"ok": not FAILURES, "results": RESULTS, "failures": FAILURES}
print(json.dumps(out, indent=2, sort_keys=True))
sys.exit(0 if not FAILURES else 1)
