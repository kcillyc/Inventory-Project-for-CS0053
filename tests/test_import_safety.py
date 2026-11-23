"""The original SQLite module must not mutate stock merely by being imported."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ImportSafetyTests(unittest.TestCase):
    def test_original_module_import_does_not_create_database_or_seed_stock(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.path.insert(0, sys.argv[1]); import inventory",
                    str(root),
                ],
                cwd=folder,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(list(Path(folder).iterdir()), [])
