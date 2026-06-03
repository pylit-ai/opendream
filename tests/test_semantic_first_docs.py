from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class SemanticFirstDocsTests(unittest.TestCase):
    DOCS = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "FAQ.md",
        REPO_ROOT / "docs" / "automation" / "dream-task-playbook.md",
        REPO_ROOT / "docs" / "benchmarks" / "semantic-mode.md",
    ]

    def test_semantic_docs_do_not_imply_config_equals_readiness(self) -> None:
        forbidden_phrases = [
            "mode=semantic is already ready",
            "mode=semantic means ready",
            "semantic mode is always ready",
            "semantic-first means ready",
        ]
        for doc_path in self.DOCS:
            content = doc_path.read_text(encoding="utf-8").lower()
            for phrase in forbidden_phrases:
                self.assertNotIn(phrase, content, msg=f"{phrase!r} found in {doc_path}")

    def test_semantic_docs_explain_degraded_truthfully(self) -> None:
        for doc_path in self.DOCS:
            content = doc_path.read_text(encoding="utf-8").lower()
            self.assertIn("degraded", content, msg=f"missing degraded wording in {doc_path}")

    def test_semantic_docs_cover_progressive_disclosure_or_pruning(self) -> None:
        for doc_path in self.DOCS:
            content = doc_path.read_text(encoding="utf-8").lower()
            self.assertTrue(
                "progressive disclosure" in content or "pruning evidence" in content,
                msg=f"missing progressive disclosure/pruning wording in {doc_path}",
            )


if __name__ == "__main__":
    unittest.main()
