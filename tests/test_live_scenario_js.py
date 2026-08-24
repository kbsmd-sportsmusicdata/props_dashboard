import shutil
import subprocess

import pytest


def test_live_scenario_browser_math():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the standalone browser-math test")
    completed = subprocess.run([node, "tests/live_scenario.test.mjs"], text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
