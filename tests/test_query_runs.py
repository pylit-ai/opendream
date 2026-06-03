"""Unit tests for ``query_runs`` list filtering and pagination."""

from __future__ import annotations

import unittest

from opendream.observability import query_runs


def _index_with_runs(runs: list[dict]) -> dict:
    return {"entities": {"runs": runs}}


class QueryRunsTests(unittest.TestCase):
    def test_search_matches_run_id_type_status(self) -> None:
        idx = _index_with_runs(
            [
                {
                    "run_id": "run-alpha",
                    "type": "consolidation",
                    "status": "ok",
                    "started_at": "2026-01-01T10:00:00Z",
                    "ended_at": "2026-01-01T11:00:00Z",
                    "source_reporting_agents": [
                        {"agent_id": "codex", "agent_label": "Codex", "model_id": "gpt-5.4"}
                    ],
                },
                {
                    "run_id": "run-beta",
                    "type": "dream",
                    "status": "failed",
                    "started_at": "2026-02-01T10:00:00Z",
                    "ended_at": "",
                    "source_reporting_agents": [
                        {"agent_id": "claude-code", "agent_label": "Claude Code"}
                    ],
                },
            ]
        )
        r = query_runs(idx, search="Claude Code")
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["items"][0]["run_id"], "run-beta")

    def test_time_bounds_use_effective_ended_then_started(self) -> None:
        idx = _index_with_runs(
            [
                {
                    "run_id": "a",
                    "type": "x",
                    "status": "ok",
                    "started_at": "2026-03-15T12:00:00Z",
                    "ended_at": "2026-03-20T12:00:00Z",
                },
                {
                    "run_id": "b",
                    "type": "x",
                    "status": "ok",
                    "started_at": "2026-03-10T12:00:00Z",
                    "ended_at": "",
                },
            ]
        )
        r = query_runs(
            idx,
            ended_after="2026-03-16T00:00:00Z",
            ended_before="2026-03-25T00:00:00Z",
        )
        ids = {row["run_id"] for row in r["items"]}
        self.assertEqual(ids, {"a"})

        # Run ``b`` has no ``ended_at``; effective time is ``started_at`` (2026-03-10 noon).
        r2 = query_runs(
            idx,
            ended_after="2026-03-10T11:00:00Z",
            ended_before="2026-03-10T13:00:00Z",
        )
        self.assertEqual({row["run_id"] for row in r2["items"]}, {"b"})

    def test_pagination_returns_total_and_slice(self) -> None:
        runs = [
            {
                "run_id": f"r{i:03d}",
                "type": "consolidation",
                "status": "ok",
                "started_at": f"2026-01-{i + 1:02d}T10:00:00Z",
                "ended_at": f"2026-01-{i + 1:02d}T11:00:00Z",
            }
            for i in range(5)
        ]
        idx = _index_with_runs(runs)
        out = query_runs(idx, sort="run_id", sort_dir="asc", offset=1, limit=2)
        self.assertEqual(out["total"], 5)
        self.assertEqual(len(out["items"]), 2)
        self.assertEqual(out["items"][0]["run_id"], "r001")
        self.assertEqual(out["items"][1]["run_id"], "r002")


if __name__ == "__main__":
    unittest.main()
