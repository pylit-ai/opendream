from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from opendream.showcase import build_showcase_report, load_showcase_events, run_showcase_demo
from opendream.storage import MemoryStore
from opendream.util import write_json

FIXED_NOW = "2026-05-02T00:00:00Z"


class ShowcaseReportGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="showcase-gate-")
        self.workspace = Path(self.tmp.name) / "workspace"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_showcase_report_has_transition_evidence_and_risk_sections(self) -> None:
        report = run_showcase_demo(MemoryStore(self.workspace), now=FIXED_NOW)

        self.assertEqual(report["status"], "passed")
        self.assertIn("dream_transition_diff", report)
        self.assertIn("evidence_density", report)
        self.assertIn("hallucination_risk", report)
        self.assertIn("why_this_dream_helped", report)
        self.assertIn("reproducibility", report)
        self.assertIn("stability_check", report)
        self.assertIn("agent_observability_trace", report)
        self.assertIn("evidence_drilldown", report)
        self.assertIn("selected_vs_excluded", report)
        self.assertIn("score_visualization", report)
        self.assertIn("claim_verification", report)
        self.assertIn("memory_safety", report)
        self.assertIn("glossary", report)
        self.assertIn("copy_actions", report)
        self.assertTrue(report["hallucination_risk"]["passed"])
        self.assertTrue(report["checks"]["hallucination_risk"]["passed"])
        self.assertTrue(report["stability_check"]["passed"])
        self.assertTrue(report["scenario_scale"]["larger_than_tiny_fixture"])
        self.assertGreaterEqual(len(report["agent_observability_trace"]["spans"]), 5)
        self.assertTrue(report["agent_observability_trace"]["run_id"])
        self.assertTrue(report["agent_observability_trace"]["context_id"])
        self.assertIn(
            "answer_generation",
            {span["operation"] for span in report["agent_observability_trace"]["spans"]},
        )
        self.assertIn(
            "eval_scoring",
            {span["operation"] for span in report["agent_observability_trace"]["spans"]},
        )
        self.assertEqual(
            report["selected_vs_excluded"]["selected_count"],
            len(report["selected_memory_ids"]),
        )
        self.assertEqual(
            report["score_visualization"]["passed_count"],
            report["score_visualization"]["total_count"],
        )
        self.assertEqual(report["claim_verification"]["trust_level"], "strong")
        self.assertTrue(report["claim_verification"]["passed"])
        self.assertTrue(report["memory_safety"]["passed"])
        self.assertEqual(report["memory_safety"]["risk_level"], "low")
        self.assertTrue(all(item["passed"] for item in report["memory_safety"]["risk_categories"]))
        self.assertIn("contested", report["glossary"])
        self.assertIn("command", report["copy_actions"])
        self.assertIn("python_version", report["reproducibility"])
        self.assertIn("opendream_version", report["reproducibility"])
        self.assertIn("git_dirty", report["reproducibility"])
        self.assertEqual(
            [stage["key"] for stage in report["dream_transition_diff"]["stages"]],
            [
                "raw_events",
                "candidate_memories",
                "durable_memories",
                "contested_quarantined_superseded_memories",
                "prompt_context",
            ],
        )
        self.assertGreater(report["evidence_density"]["selected_source_event_count"], 0)
        self.assertTrue(report["why_this_dream_helped"]["passed"])

    def test_selected_memory_without_source_event_evidence_fails_showcase(self) -> None:
        store = MemoryStore(self.workspace)
        report = run_showcase_demo(store, now=FIXED_NOW)
        selected_id = report["selected_memory_ids"][0]
        records = store.load_durable_records()
        for record in records:
            if record["memory_id"] == selected_id:
                record["source_event_ids"] = []
        write_json(store.durable_records_path, records)

        failed = build_showcase_report(
            store,
            events=load_showcase_events(),
            before=report["before"],
            after=report["after"],
            stability_probe=report["after"],
            context=report["context"],
            maintenance=report["maintenance"],
            trace_spans=report["agent_observability_trace"]["spans"],
            timestamp=FIXED_NOW,
        )

        self.assertEqual(failed["status"], "failed")
        self.assertFalse(failed["hallucination_risk"]["passed"])
        self.assertFalse(failed["checks"]["hallucination_risk"]["passed"])
        self.assertIn(
            selected_id,
            failed["hallucination_risk"]["gates"]["selected_memory_source_evidence"][
                "failed_memory_ids"
            ],
        )


if __name__ == "__main__":
    unittest.main()
