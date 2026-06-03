from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import release_check

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "semantic_release_proof.json"


class SemanticReleaseProofTests(unittest.TestCase):
    def test_fixture_covers_required_scenarios(self) -> None:
        fixture = release_check.load_semantic_release_proof_fixture(FIXTURE_PATH)

        self.assertEqual(
            sorted(fixture["scenarios"].keys()),
            ["degraded_semantic_first", "semantic_ready_progressive", "unpruned_baseline"],
        )

    def test_release_gate_accepts_truthful_progressive_fixture(self) -> None:
        fixture = release_check.load_semantic_release_proof_fixture(FIXTURE_PATH)

        stage = release_check.semantic_release_proof_stage(fixture)

        self.assertEqual(stage["name"], "semantic-release-proof")
        self.assertEqual(stage["status"], "PASS")
        self.assertTrue(stage["checks"]["truthful_degraded_labeling"])
        self.assertTrue(stage["checks"]["pruning_advantage"])
        self.assertTrue(stage["checks"]["repeated_task_benefit"])
        self.assertIn("success_rate_delta", stage["evidence"]["repeated_task_improvements"])

    def test_release_gate_fails_when_ready_mode_only_shrinks_context(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        fixture["scenarios"]["semantic_ready_progressive"]["repeated_task"]["success_rate"] = fixture["scenarios"][
            "unpruned_baseline"
        ]["repeated_task"]["success_rate"]
        fixture["scenarios"]["semantic_ready_progressive"]["repeated_task"]["procedural_reuse_hits"] = fixture[
            "scenarios"
        ]["unpruned_baseline"]["repeated_task"]["procedural_reuse_hits"]
        fixture["scenarios"]["semantic_ready_progressive"]["repeated_task"]["resolution_latency_ms"] = fixture[
            "scenarios"
        ]["unpruned_baseline"]["repeated_task"]["resolution_latency_ms"]

        stage = release_check.semantic_release_proof_stage(fixture)

        self.assertEqual(stage["status"], "FAIL")
        self.assertFalse(stage["checks"]["repeated_task_benefit"])

    def test_release_gate_fails_when_degraded_label_is_dishonest(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        fixture["scenarios"]["degraded_semantic_first"]["semantic_capability_state"] = "ready"

        stage = release_check.semantic_release_proof_stage(fixture)

        self.assertEqual(stage["status"], "FAIL")
        self.assertFalse(stage["checks"]["truthful_degraded_labeling"])


if __name__ == "__main__":
    unittest.main()
