from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliGoldenTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "opendream.cli", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

    def test_top_level_help_names_launch_critical_commands(self) -> None:
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for phrase in ("init", "status", "demo", "dream", "observe", "eval"):
            self.assertIn(phrase, result.stdout)

    def test_version_is_short_and_parseable(self) -> None:
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout.strip(), r"^opendream \d+\.\d+\.\d+")

    def test_cli_import_does_not_load_observe_webapp(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import opendream.cli; raise SystemExit('opendream.webapp' in sys.modules)",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_command_has_actionable_error(self) -> None:
        result = self.run_cli("does-not-exist")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)
        self.assertIn("opendream", result.stderr)

    def test_readme_quickstart_core_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            init_result = self.run_cli("init", "--workspace", str(workspace))
            status_result = self.run_cli("status", "--workspace", str(workspace))
            demo_result = self.run_cli("demo", "--workspace", str(workspace))
        self.assertEqual(init_result.returncode, 0, init_result.stderr)
        self.assertEqual(status_result.returncode, 0, status_result.stderr)
        self.assertEqual(demo_result.returncode, 0, demo_result.stderr)
        self.assertEqual(json.loads(demo_result.stdout)["consolidate"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
