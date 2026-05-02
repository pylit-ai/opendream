from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from opendream.evaluation import run_performance_eval
from opendream.storage import MemoryStore
from opendream.util import FIXTURE_ROOT, read_json, write_json


FIXED_NOW = "2026-05-02T00:00:00Z"


class PerformanceEvaluationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="performance-gate-")
        self.workspace = Path(self.tmp.name) / "workspace"
        self.fixture_path = Path(self.tmp.name) / "performance_eval.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _fixture(self) -> dict:
        return copy.deepcopy(read_json(FIXTURE_ROOT / "performance_eval.json", {}))

    def _run(self, fixture: dict) -> dict:
        write_json(self.fixture_path, fixture)
        return run_performance_eval(
            MemoryStore(self.workspace),
            fixture_path=self.fixture_path,
            now=FIXED_NOW,
        )

    def test_expected_answer_is_required_for_match_queries(self) -> None:
        fixture = self._fixture()
        fixture["queries"]["should_match"][0].pop("expected_answer", None)

        result = self._run(fixture)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["scorecard"]["expected_answer_coverage"], 75.0)
        self.assertEqual(
            result["details"]["missing_expected_answer_queries"],
            ["What database should we use for this project?"],
        )

    def test_expected_answer_terms_must_be_covered_by_retrieved_memory(self) -> None:
        fixture = self._fixture()
        fixture["queries"]["should_match"][0]["expected_answer"] = "Use MongoDB for persistence."

        result = self._run(fixture)

        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["retrieval_results"][0]["hit"])
        self.assertFalse(result["retrieval_results"][0]["answer_covered"])
        self.assertIn("mongodb", result["retrieval_results"][0]["missing_answer_terms"])

    def test_expected_answer_terms_must_have_source_event_evidence(self) -> None:
        fixture = self._fixture()
        fixture["queries"]["should_match"][0]["expected_answer_terms"] = ["Decision"]

        result = self._run(fixture)

        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["retrieval_results"][0]["answer_covered"])
        self.assertFalse(result["retrieval_results"][0]["source_answer_covered"])
        self.assertIn("decision", result["retrieval_results"][0]["missing_source_answer_terms"])
        self.assertEqual(result["scorecard"]["hallucination_risk"], 0.0)
        self.assertEqual(
            result["details"]["missing_expected_answer_source_evidence_queries"],
            ["What database should we use for this project?"],
        )

    def test_required_workflow_memory_must_be_active_and_task_shaped(self) -> None:
        fixture = self._fixture()
        fixture["events"]["high_signal"] = [
            event for event in fixture["events"]["high_signal"] if event.get("kind") != "workflow_step"
        ]

        result = self._run(fixture)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["scorecard"]["workflow_memory"], 0.0)
        self.assertEqual(result["details"]["missing_required_workflows"], ["Workflow: deploy"])


if __name__ == "__main__":
    unittest.main()
