from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class PackageBoundaryManifestTests(unittest.TestCase):
    def test_manifest_is_valid_json(self) -> None:
        manifest_path = REPO_ROOT / "opendream" / "package_boundaries.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertIn("public_contract", manifest["surfaces"])

    def test_package_boundary_checker_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/check_package_boundaries.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
