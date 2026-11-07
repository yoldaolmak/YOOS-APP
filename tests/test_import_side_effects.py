"""Module imports must not create files or folders."""
import os
import subprocess
import sys


def test_demo_module_import_has_no_output_side_effect(tmp_path):
    output = tmp_path / "nonexistent" / "demo"
    env = os.environ.copy()
    env["PENNOVIA_DEMO_OUTPUT_DIR"] = str(output)
    done = subprocess.run(
        [sys.executable, "-c", "import pennovia.demo.__main__"],
        env=env, text=True, capture_output=True, check=False,
    )
    assert done.returncode == 0, done.stderr
    assert not output.exists()
