"""Pytest bootstrap: make the repository root importable.

`tests/test_curve_state.py` does `from scripts.build_curve_state import ...`,
which only resolves when the repo root is on `sys.path`. That happens
incidentally under `python -m pytest` (which prepends the cwd) but NOT under the
bare `pytest` console script -- which is exactly how CI invokes it:

    pytest -q tests/

So the I-21 curve-state gates passed locally and failed in CI with
`ModuleNotFoundError: No module named 'scripts'`, aborting collection of the
whole suite. Adding the root explicitly here makes the import work under every
invocation, so local runs and CI cannot diverge again.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))