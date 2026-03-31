from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PATH_SCOPED_AGENTS = [
    REPO_ROOT / "opendream" / "AGENTS.md",
    REPO_ROOT / "openspec" / "AGENTS.md",
    REPO_ROOT / ".meta" / "spec-adapters" / "AGENTS.md",
    REPO_ROOT / "tests" / "AGENTS.md",
]


class AgentReadyGuidanceTests(unittest.TestCase):
    def test_path_scoped_agents_files_exist(self) -> None:
        missing = [str(p.relative_to(REPO_ROOT)) for p in PATH_SCOPED_AGENTS if not p.is_file()]
        self.assertEqual(missing, [], f"missing AGENTS.md: {missing}")

    def test_root_agents_references_path_scoped_files(self) -> None:
        root = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("opendream/AGENTS.md", root)
        self.assertIn("openspec/AGENTS.md", root)
        self.assertIn(".meta/spec-adapters/AGENTS.md", root)
        self.assertIn("tests/AGENTS.md", root)
