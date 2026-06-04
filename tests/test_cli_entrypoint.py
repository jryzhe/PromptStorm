import os
import subprocess
import sys
import unittest
from pathlib import Path


class CliEntrypointTests(unittest.TestCase):
    def test_main_py_runs_without_pythonpath_or_package_install(self):
        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)

        result = subprocess.run(
            [sys.executable, "main.py", "--stats"],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No debates recorded yet.", result.stdout)


if __name__ == "__main__":
    unittest.main()
