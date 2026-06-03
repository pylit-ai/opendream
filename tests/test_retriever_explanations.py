from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from opendream.retriever import retrieve, retrieve_with_fusion
from opendream.storage import MemoryStore
from opendream.util import write_json

NOW = "2026-04-19T12:00:00Z"


def durable_record(
    memory_id: str,
    *,
    title: str,
    body: str,
    status: str = "active",
    memory_type: str = "project_decision",
    updated_at: str = "2026-04-18T12:00:00Z",
    conflicts_with: list[str] | None = None,
) -> dict[str, object]:
    return {
        "memory_id": memory_id,
        "type": memory_type,
        "scope": "project",
        "title": title,
        "summary": body,
        "body": body,
        "status": status,
        "confidence": 0.8,
        "salience": 0.7,
        "source_event_ids": [f"event-{memory_id}"],
        "supersedes": [],
        "conflicts_with": conflicts_with or [],
        "valid_from": "2026-01-01T00:00:00Z",
        "valid_to": None,
        "access_count": 0,
        "last_accessed_at": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": updated_at,
    }


class RetrieverExplanationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="retriever-explanations-")
        self.workspace = Path(self.tmp.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(self.workspace)
        self.store.initialize(store_kind="project")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_explains_exclusions_reranking_freshness_conflicts_and_score_components(self) -> None:
        write_json(
            self.store.durable_records_path,
            [
                durable_record(
                    "mem-active",
                    title="Use uv for package installs",
                    body="Install project dependencies with uv and keep lockfiles current.",
                    memory_type="workflow",
                    updated_at="2026-01-01T00:00:00Z",
                    conflicts_with=["mem-contested"],
                ),
                durable_record(
                    "mem-contested",
                    title="Use pip for package installs",
                    body="Install project dependencies with pip.",
                    status="contested",
                    conflicts_with=["mem-active"],
                ),
                durable_record(
                    "mem-retired",
                    title="Retired package guidance",
                    body="Old dependency setup guidance.",
                    status="retired",
                ),
                durable_record(
                    "mem-unmatched",
                    title="Editor preference",
                    body="Use compact editor tabs.",
                ),
            ],
        )
        write_json(
            self.store.relation_edges_path,
            [
                {
                    "edge_id": "edge-conflict",
                    "from_id": "mem-active",
                    "to_id": "mem-contested",
                    "kind": "conflicts_with",
                    "reason": "fixture conflict",
                    "created_at": NOW,
                    "source_event_ids": ["event-edge"],
                }
            ],
        )

        result = retrieve(
            self.store,
            query="how install project dependencies with uv",
            limit=1,
            now=NOW,
            embedding_enabled=False,
        )

        self.assertEqual(result["selected_memory_ids"], ["mem-active"])
        self.assertFalse(result["reranked"])
        self.assertEqual(result["rerank"]["reason"], "single prefilter candidate; rerank skipped")

        explanation = result["explanations"][0]
        self.assertEqual(explanation["freshness"]["state"], "stale")
        self.assertGreater(explanation["freshness"]["days_since_update"], 30)
        self.assertEqual(explanation["conflict"]["state"], "conflicting")
        self.assertEqual(explanation["conflict"]["conflicts_with"], ["mem-contested"])
        self.assertEqual(explanation["score_contributions"]["procedural_query_boost"], 1.5)
        component_names = {component["name"] for component in explanation["score_components"]}
        self.assertIn("recency_prior", component_names)
        self.assertIn("relation_adjustment", component_names)

        exclusions = {item["memory_id"]: item for item in result["excluded"]}
        self.assertEqual(exclusions["mem-contested"]["reason_code"], "contested_default_exclusion")
        self.assertEqual(exclusions["mem-contested"]["conflict"]["state"], "contested")
        self.assertEqual(exclusions["mem-retired"]["reason_code"], "status_not_retrievable")
        self.assertEqual(exclusions["mem-unmatched"]["reason_code"], "no_match")
        self.assertEqual(exclusions["mem-unmatched"]["matched_evidence"]["lexical_terms"], [])

    def test_fusion_explains_learned_context_freshness_conflicts_and_score_components(self) -> None:
        write_json(self.store.durable_records_path, [])
        write_json(
            self.store.learned_context_path,
            [
                {
                    "record_id": "lc-stale-conflict",
                    "status": "active",
                    "verifier_status": "review_required",
                    "summary": "Dependency installs use uv",
                    "details": "Use uv sync for dependency setup.",
                    "confidence": 0.9,
                    "fresh_until": "2026-03-01T00:00:00Z",
                    "conflict_state": "detected",
                    "query_family_tags": ["dependency", "install"],
                }
            ],
        )

        result = retrieve_with_fusion(
            self.store,
            query="install dependency setup with uv",
            limit=3,
            now=NOW,
            include_automation=False,
        )

        self.assertEqual(result["selected_learned_context_ids"], ["lc-stale-conflict"])
        explanation = result["learned_context_explanations"][0]
        self.assertEqual(explanation["freshness"]["state"], "expired")
        self.assertEqual(explanation["freshness"]["score_effect"], -0.3)
        self.assertEqual(explanation["conflict"]["state"], "detected")
        self.assertEqual(explanation["conflict"]["score_effect"], -0.5)
        self.assertEqual(explanation["score_contributions"]["freshness_penalty"], -0.3)
        self.assertEqual(explanation["score_contributions"]["conflict_penalty"], -0.5)
        self.assertIn("stale_learned_context:lc-stale-conflict", result["memory_hurt"]["learned_context_harm"])
        self.assertIn("conflicted_learned_context:lc-stale-conflict", result["memory_hurt"]["learned_context_harm"])


if __name__ == "__main__":
    unittest.main()
