"""Unit tests for ``query_retrievals`` (search, time bounds, selected count, sort, pagination)."""

from __future__ import annotations

import unittest

from opendream.observability import query_retrievals


def _idx(rows: list[dict]) -> dict:
    return {"entities": {"retrievals": rows}}


class QueryRetrievalsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            {
                "id": "r1",
                "run_id": "r1",
                "timestamp": "2026-01-01T10:00:00Z",
                "query": "alpha query",
                "summary": "s1",
                "selected_memory_ids": ["a", "b"],
                "reporting_agent": {"agent_id": "codex", "agent_label": "Codex"},
                "source_reporting_agents": [{"agent_id": "claude-code", "agent_label": "Claude Code"}],
            },
            {
                "id": "r2",
                "run_id": "r2",
                "timestamp": "2026-01-03T10:00:00Z",
                "query": "beta",
                "summary": "s2",
                "selected_memory_ids": [],
                "reporting_agent": {"agent_id": "unknown", "agent_label": "Unknown"},
            },
            {
                "id": "r3",
                "run_id": "r3",
                "timestamp": "2026-01-02T10:00:00Z",
                "query": "gamma beta",
                "summary": "s3",
                "selected_memory_ids": ["x"],
                "reporting_agent": {"agent_id": "cursor", "agent_label": "Cursor"},
            },
        ]

    def test_search_matches_query_and_id(self) -> None:
        r = query_retrievals(_idx(self.rows), search="beta")
        ids = {row["id"] for row in r["items"]}
        self.assertEqual(ids, {"r2", "r3"})

    def test_search_filter_and_sort_by_agent(self) -> None:
        searched = query_retrievals(_idx(self.rows), search="Claude Code")
        self.assertEqual([row["id"] for row in searched["items"]], ["r1"])

        filtered = query_retrievals(_idx(self.rows), filters={"agent_id": "codex"})
        self.assertEqual([row["id"] for row in filtered["items"]], ["r1"])

        sorted_rows = query_retrievals(
            _idx(self.rows),
            sort="reporting_agent",
            sort_dir="asc",
            limit=10,
        )
        self.assertEqual([row["id"] for row in sorted_rows["items"]], ["r1", "r3", "r2"])

    def test_timestamp_window(self) -> None:
        r = query_retrievals(
            _idx(self.rows),
            timestamp_after="2026-01-02T00:00:00Z",
            timestamp_before="2026-01-03T00:00:00Z",
        )
        ids = {row["id"] for row in r["items"]}
        self.assertEqual(ids, {"r3"})

    def test_min_max_selected(self) -> None:
        r = query_retrievals(_idx(self.rows), min_selected=1, max_selected=2)
        ids = {row["id"] for row in r["items"]}
        self.assertEqual(ids, {"r1", "r3"})

    def test_sort_timestamp_desc_default(self) -> None:
        r = query_retrievals(_idx(self.rows), sort="timestamp", limit=10)
        self.assertEqual([row["id"] for row in r["items"]], ["r2", "r3", "r1"])

    def test_sort_selected_count_asc(self) -> None:
        r = query_retrievals(_idx(self.rows), sort="selected_count", sort_dir="asc", limit=10)
        self.assertEqual([row["id"] for row in r["items"]], ["r2", "r3", "r1"])

    def test_pagination(self) -> None:
        r0 = query_retrievals(_idx(self.rows), sort="id", sort_dir="asc", offset=0, limit=2)
        r1 = query_retrievals(_idx(self.rows), sort="id", sort_dir="asc", offset=2, limit=2)
        self.assertEqual(len(r0["items"]), 2)
        self.assertEqual(len(r1["items"]), 1)
        self.assertEqual(r0["total"], 3)


if __name__ == "__main__":
    unittest.main()
