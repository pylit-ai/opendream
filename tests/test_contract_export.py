from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from opendream.contract_export import build_contract_export, top_level_command_names
from opendream.util import FIXTURE_ROOT
from opendream.validation import validate_document

REPO_ROOT = Path(__file__).resolve().parents[1]


class ContractExportTests(unittest.TestCase):
    def test_export_validates_against_schema(self) -> None:
        payload = build_contract_export(REPO_ROOT)
        validate_document("contract-export.schema.json", payload)

    def test_export_matches_stable_snapshot_excluding_version(self) -> None:
        payload = build_contract_export(REPO_ROOT)
        payload.pop("opendream_version", None)
        snapshot_path = FIXTURE_ROOT / "contracts" / "stable-snapshot.json"
        expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.assertEqual(payload, expected)

    def test_top_level_commands_include_contract(self) -> None:
        names = top_level_command_names()
        self.assertIn("contract", names)

    def test_cli_contract_export_matches_build_function(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "opendream.cli", "contract", "export", "--workspace", str(REPO_ROOT)],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cli_payload = json.loads(completed.stdout)
        direct = build_contract_export(REPO_ROOT)
        self.assertEqual(cli_payload, direct)
