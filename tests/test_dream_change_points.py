from __future__ import annotations

import json
import time
import unittest
from pathlib import Path

from opendream.dream_change_points import score_dream_change_points

FIXTURE = Path(__file__).parent / "fixtures" / "dream_change_point_cycles.json"


def _fixture_cycles() -> list[dict[str, object]]:
    return json.loads(FIXTURE.read_text())


def _by_id(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row["run_id"]): row for row in rows}


class DreamChangePointTests(unittest.TestCase):
    def test_scores_material_failure_drift_duration_and_noop_cycles(self) -> None:
        scored = score_dream_change_points(_fixture_cycles(), newest_first=False)
        rows = _by_id(scored)

        material = rows["dream-material"]["change_point"]
        self.assertIsInstance(material, dict)
        assert isinstance(material, dict)
        self.assertEqual(material["kind"], "material")
        self.assertEqual(material["severity"], "high")
        self.assertGreaterEqual(material["score"], 80)
        self.assertIs(material["is_noop"], False)
        self.assertTrue(any(c["key"] == "approved" for c in material["contributors"]))
        self.assertNotIn("selected=", material["label"])
        self.assertIn("created 1 learned-context record", material["label"])

        failure = rows["dream-failure"]["change_point"]
        self.assertIsInstance(failure, dict)
        assert isinstance(failure, dict)
        self.assertEqual(failure["kind"], "failure")
        self.assertEqual(failure["severity"], "high")
        self.assertGreaterEqual(failure["score"], 70)
        self.assertTrue(any(c["key"] == "reason" and c["value"] == "provider-error" for c in failure["contributors"]))

        drift = rows["dream-drift-signal"]["change_point"]
        self.assertIsInstance(drift, dict)
        assert isinstance(drift, dict)
        self.assertEqual(drift["kind"], "drift")
        self.assertEqual(drift["severity"], "medium")
        self.assertIn("120 -> 88", drift["label"])
        self.assertTrue(any(c["key"] == "signal_row_count" for c in drift["contributors"]))

        anomaly = rows["dream-duration-anomaly"]["change_point"]
        self.assertIsInstance(anomaly, dict)
        assert isinstance(anomaly, dict)
        self.assertEqual(anomaly["kind"], "duration_anomaly")
        self.assertEqual(anomaly["severity"], "medium")
        self.assertIn("synthesize", anomaly["label"])
        self.assertTrue(
            any(c["key"] == "phase_duration" and c["phase"] == "synthesize" for c in anomaly["contributors"])
        )

        noop = rows["dream-noop-002"]["change_point"]
        self.assertIsInstance(noop, dict)
        assert isinstance(noop, dict)
        self.assertEqual(noop["kind"], "noop")
        self.assertEqual(noop["score"], 0)
        self.assertIs(noop["is_noop"], True)

    def test_query_family_selection_alone_is_not_material(self) -> None:
        scored = score_dream_change_points(
            [
                {
                    "run_id": "selected-only",
                    "mode": "semantic",
                    "status": "completed",
                    "signal_row_count": 120,
                    "phases": ["orient", "gather_recent_signal", "synthesize", "promote"],
                    "phase_durations": {"orient": 100, "gather_recent_signal": 200, "synthesize": 500, "promote": 200},
                    "funnel": {"considered": 120, "selected": 9, "generated": 0, "approved": 0, "created": 0},
                }
            ],
            newest_first=False,
        )

        change_point = scored[0]["change_point"]
        self.assertIsInstance(change_point, dict)
        assert isinstance(change_point, dict)
        self.assertEqual(change_point["kind"], "noop")
        self.assertEqual(change_point["score"], 0)
        self.assertEqual(change_point["label"], "No observable dream effect.")

    def test_staged_events_are_material_runtime_effects(self) -> None:
        scored = score_dream_change_points(
            [
                {
                    "run_id": "staged-events",
                    "mode": "dream",
                    "status": "completed",
                    "signal_row_count": 88,
                    "phases": ["orient", "gather_recent_signal", "consolidate"],
                    "funnel": {"considered": 88, "selected": 9, "generated": 0, "approved": 0, "created": 0},
                    "appended_events": 9,
                }
            ],
            newest_first=False,
        )

        change_point = scored[0]["change_point"]
        self.assertIsInstance(change_point, dict)
        assert isinstance(change_point, dict)
        self.assertEqual(change_point["kind"], "material")
        self.assertGreaterEqual(change_point["score"], 80)
        self.assertIn("staged 9 memory event", change_point["label"])

    def test_idle_skips_do_not_become_signal_drift(self) -> None:
        scored = score_dream_change_points(
            [
                {
                    "run_id": "baseline",
                    "mode": "dream",
                    "status": "completed",
                    "signal_row_count": 88,
                    "phases": ["orient", "gather_recent_signal"],
                    "funnel": {"considered": 88, "selected": 0, "generated": 0, "approved": 0, "created": 0},
                },
                {
                    "run_id": "no-transcripts",
                    "mode": "dream",
                    "status": "skipped",
                    "reason": "no-episodes",
                    "signal_row_count": 0,
                    "phases": ["orient"],
                    "funnel": {"considered": 0, "selected": 0, "generated": 0, "approved": 0, "created": 0},
                },
            ],
            newest_first=False,
        )

        change_point = scored[1]["change_point"]
        self.assertIsInstance(change_point, dict)
        assert isinstance(change_point, dict)
        self.assertEqual(change_point["kind"], "noop")
        self.assertEqual(change_point["score"], 0)

    def test_scoring_accepts_newest_first_and_preserves_order(self) -> None:
        newest_first = list(reversed(_fixture_cycles()))
        scored = score_dream_change_points(newest_first, newest_first=True)

        self.assertEqual([row["run_id"] for row in scored], [row["run_id"] for row in newest_first])
        rows = _by_id(scored)
        drift = rows["dream-drift-signal"]["change_point"]
        self.assertIsInstance(drift, dict)
        assert isinstance(drift, dict)
        self.assertEqual(drift["kind"], "drift")

    def test_score_schema_is_present_for_single_cycle(self) -> None:
        scored = score_dream_change_points([_fixture_cycles()[0]], newest_first=False)
        change_point = scored[0]["change_point"]

        self.assertEqual(
            change_point,
            {
                "score": 0,
                "severity": "low",
                "kind": "noop",
                "label": "No observable dream effect.",
                "contributors": [],
                "signature": "semantic|completed||120-129|orient>gather_recent_signal>synthesize>promote|",
                "is_noop": True,
            },
        )

    def test_funnel_selected_change_alone_is_not_drift(self) -> None:
        """Two cycles differing only in funnel.selected must stay noop.

        Selection volume is operationally meaningless without downstream
        proposals/approvals/created records, so it must not produce drift
        rows that erode operator trust.
        """
        scored = score_dream_change_points(
            [
                {
                    "run_id": "selected-9",
                    "mode": "semantic",
                    "status": "completed",
                    "signal_row_count": 120,
                    "phases": ["orient", "gather_recent_signal", "synthesize", "promote"],
                    "funnel": {"considered": 120, "selected": 9, "generated": 0, "approved": 0, "created": 0},
                },
                {
                    "run_id": "selected-0",
                    "mode": "semantic",
                    "status": "completed",
                    "signal_row_count": 120,
                    "phases": ["orient", "gather_recent_signal", "synthesize", "promote"],
                    "funnel": {"considered": 120, "selected": 0, "generated": 0, "approved": 0, "created": 0},
                },
            ],
            newest_first=False,
        )

        change_point = scored[1]["change_point"]
        self.assertIsInstance(change_point, dict)
        assert isinstance(change_point, dict)
        self.assertEqual(change_point["kind"], "noop")
        self.assertEqual(change_point["score"], 0)
        self.assertFalse(
            any(c.get("key") == "funnel.selected" for c in change_point["contributors"]),
        )

    def test_duration_anomaly_skipped_when_baseline_variance_is_high(self) -> None:
        """A 3x spike on a chaotic baseline is noise, not an anomaly."""
        history = [
            {
                "run_id": f"hist-{i}",
                "mode": "dream",
                "status": "completed",
                "signal_row_count": 88,
                "phases": ["orient", "synthesize"],
                "phase_durations": {"orient": 100, "synthesize": dur},
                "funnel": {"considered": 88, "selected": 0, "generated": 0, "approved": 0, "created": 0},
            }
            for i, dur in enumerate([400, 800, 1600])
        ]
        current = {
            "run_id": "current",
            "mode": "dream",
            "status": "completed",
            "signal_row_count": 88,
            "phases": ["orient", "synthesize"],
            "phase_durations": {"orient": 100, "synthesize": 3200},
            "funnel": {"considered": 88, "selected": 0, "generated": 0, "approved": 0, "created": 0},
        }
        scored = score_dream_change_points([*history, current], newest_first=False)
        change_point = scored[-1]["change_point"]
        assert isinstance(change_point, dict)
        self.assertNotEqual(change_point["kind"], "duration_anomaly")

    def test_duration_anomaly_scoring_uses_cached_phase_baselines(self) -> None:
        cycles = [
            {
                "run_id": f"cycle-{i:04d}",
                "mode": "dream",
                "status": "completed",
                "signal_row_count": 88,
                "phases": ["orient", "gather_recent_signal", "synthesize", "promote"],
                "phase_durations": {
                    "orient": 100 + (i % 3),
                    "gather_recent_signal": 180 + (i % 4),
                    "synthesize": 420 + (i % 5),
                    "promote": 90 + (i % 2),
                },
                "funnel": {
                    "considered": 88,
                    "selected": 0,
                    "generated": 0,
                    "approved": 0,
                    "created": 0,
                },
            }
            for i in range(1_200)
        ]
        cycles.append(
            {
                **cycles[-1],
                "run_id": "duration-spike",
                "phase_durations": {
                    "orient": 101,
                    "gather_recent_signal": 181,
                    "synthesize": 2_000,
                    "promote": 91,
                },
            }
        )

        started = time.perf_counter()
        scored = score_dream_change_points(cycles, newest_first=False)
        elapsed = time.perf_counter() - started

        change_point = scored[-1]["change_point"]
        assert isinstance(change_point, dict)
        self.assertEqual(change_point["kind"], "duration_anomaly")
        self.assertLess(elapsed, 0.2)
