from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from opendream.util import CANONICAL_SCHEMA_ROOT, OPEN_SPEC_ROOT, SCHEMA_ROOT
from opendream.validation import required_schema_files

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = "2026-03-26T12:00:00Z"


class ReleaseArtifactTests(unittest.TestCase):
    def test_schema_assets_are_present_and_consistent(self) -> None:
        openspec_schema_root = OPEN_SPEC_ROOT / "schema"
        for schema_name in required_schema_files():
            package_schema = SCHEMA_ROOT / schema_name
            canonical_schema = CANONICAL_SCHEMA_ROOT / schema_name
            proposal_schema = openspec_schema_root / schema_name
            self.assertTrue(package_schema.exists(), schema_name)
            self.assertTrue(canonical_schema.exists(), schema_name)
            self.assertTrue(proposal_schema.exists(), schema_name)

            package_payload = json.loads(package_schema.read_text(encoding="utf-8"))
            canonical_payload = json.loads(canonical_schema.read_text(encoding="utf-8"))
            proposal_payload = json.loads(proposal_schema.read_text(encoding="utf-8"))
            self.assertEqual(package_payload, canonical_payload, schema_name)
            self.assertEqual(package_payload, proposal_payload, schema_name)

    def test_clean_venv_install_and_demo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            venv_dir = temp_path / "venv"
            workspace = temp_path / "demo-workspace"
            dream_workspace = temp_path / "dream-workspace"
            eval_workspace = temp_path / "eval-workspace"
            transcript_fixture = temp_path / "transcript.jsonl"
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            scripts_dir = "Scripts" if os.name == "nt" else "bin"
            venv_python = venv_dir / scripts_dir / "python"
            entrypoint = venv_dir / scripts_dir / "opendream"
            transcript_fixture.write_text(
                (
                    '{"timestamp":"2026-03-26T09:00:00Z","speaker":"user","text":"Use pnpm in this repo."}\n'
                    '{"timestamp":"2026-03-26T09:15:00Z","speaker":"assistant","text":"Schema migration workflow: '
                    'generate the SQL first, then apply it after review."}\n'
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "--no-deps", str(REPO_ROOT)],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            help_run = subprocess.run(
                [str(entrypoint), "--help"],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("opendream", help_run.stdout)

            demo_run = subprocess.run(
                [str(entrypoint), "demo", "--workspace", str(workspace), "--now", FIXED_NOW],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"events_appended": 20', demo_run.stdout)
            self.assertTrue((workspace / "memory" / "MEMORY.md").exists())

            dream_run = subprocess.run(
                [
                    str(entrypoint),
                    "dream",
                    "run",
                    "--workspace",
                    str(dream_workspace),
                    "--episodes",
                    str(transcript_fixture),
                    "--now",
                    FIXED_NOW,
                    "--compat-mode",
                    "autodream",
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "completed"', dream_run.stdout)

            fidelity_eval = subprocess.run(
                [
                    str(entrypoint),
                    "eval",
                    "dream-fidelity",
                    "--workspace",
                    str(eval_workspace),
                    "--now",
                    FIXED_NOW,
                    "--compat-mode",
                    "autodream",
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "passed"', fidelity_eval.stdout)


if __name__ == "__main__":
    unittest.main()
