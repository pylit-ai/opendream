"""Unit tests for ``query_memories`` (list filtering, ranges, time bounds, sort, pagination)."""

from __future__ import annotations

import unittest

from opendream.observability import query_memories


def _idx(rows: list[dict]) -> dict:
    return {"entities": {"memories": rows}}


class QueryMemoriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            {
                "memory_id": "m1",
                "title": "Alpha",
                "summary": "one",
                "body": "",
                "type": "semantic_fact",
                "scope": "project",
                "status": "active",
                "salience": 0.2,
                "confidence": 0.9,
                "retrieval_frequency": 3,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            },
            {
                "memory_id": "m2",
                "title": "Beta",
                "summary": "two",
                "body": "",
                "type": "semantic_fact",
                "scope": "project",
                "status": "contested",
                "salience": 0.8,
                "confidence": 0.5,
                "retrieval_frequency": 0,
                "created_at": "2026-01-03T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "memory_id": "m3",
                "title": "Gamma",
                "summary": "three",
                "body": "",
                "type": "user_preference",
                "scope": "user",
                "status": "active",
                "retrieval_frequency": 1,
                "created_at": "2026-01-02T00:00:00Z",
                "updated_at": "2026-01-03T00:00:00Z",
            },
        ]

    def test_search_matches_title_and_id(self) -> None:
        r = query_memories(_idx(self.rows), search="beta")
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["items"][0]["memory_id"], "m2")

    def test_filters_type_scope_status(self) -> None:
        r = query_memories(
            _idx(self.rows),
            filters={"type": "semantic_fact", "scope": "project", "status": "active"},
        )
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["items"][0]["memory_id"], "m1")

    def test_salience_range_excludes_missing_salience(self) -> None:
        r = query_memories(_idx(self.rows), salience_min=0.3, salience_max=1.0)
        ids = {row["memory_id"] for row in r["items"]}
        self.assertEqual(ids, {"m2"})

    def test_confidence_range(self) -> None:
        r = query_memories(_idx(self.rows), confidence_max=0.6)
        ids = {row["memory_id"] for row in r["items"]}
        self.assertEqual(ids, {"m2"})

    def test_updated_time_window(self) -> None:
        r = query_memories(
            _idx(self.rows),
            updated_after="2026-01-02T00:00:00Z",
            updated_before="2026-01-03T00:00:00Z",
        )
        ids = {row["memory_id"] for row in r["items"]}
        self.assertEqual(ids, {"m1", "m3"})

    def test_created_time_window(self) -> None:
        r = query_memories(_idx(self.rows), created_after="2026-01-02T00:00:00Z")
        ids = {row["memory_id"] for row in r["items"]}
        self.assertEqual(ids, {"m2", "m3"})

    def test_sort_salience_desc(self) -> None:
        r = query_memories(_idx(self.rows), sort="salience", sort_dir="desc", limit=10)
        self.assertEqual([row["memory_id"] for row in r["items"]], ["m2", "m1", "m3"])

    def test_sort_title_asc_tiebreak_memory_id(self) -> None:
        base = {
            "title": "Same",
            "summary": "",
            "body": "",
            "type": "semantic_fact",
            "scope": "project",
            "status": "active",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        rows = [
            {**base, "memory_id": "b"},
            {**base, "memory_id": "a"},
        ]
        r = query_memories(_idx(rows), sort="title", sort_dir="asc", limit=10)
        self.assertEqual([row["memory_id"] for row in r["items"]], ["a", "b"])

    def test_pagination(self) -> None:
        r0 = query_memories(_idx(self.rows), sort="memory_id", sort_dir="asc", offset=0, limit=2)
        r1 = query_memories(_idx(self.rows), sort="memory_id", sort_dir="asc", offset=2, limit=2)
        self.assertEqual(len(r0["items"]), 2)
        self.assertEqual(len(r1["items"]), 1)
        self.assertEqual(r0["items"][0]["memory_id"], "m1")
        self.assertEqual(r1["items"][0]["memory_id"], "m3")

    def test_invalid_sort_field_falls_back(self) -> None:
        r = query_memories(_idx(self.rows), sort="not_a_column", sort_dir="desc", limit=10)
        self.assertEqual(r["total"], 3)

    def test_legacy_sort_dir_default_desc_for_updated_at(self) -> None:
        r = query_memories(_idx(self.rows), sort="updated_at", limit=10)
        ids = [row["memory_id"] for row in r["items"]]
        self.assertEqual(ids, ["m3", "m1", "m2"])


if __name__ == "__main__":
    unittest.main()
