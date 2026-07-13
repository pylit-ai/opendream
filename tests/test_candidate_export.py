from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from opendream.candidate_export import build_candidate_export
from opendream.models import (
    ConsolidationOperation,
    MemoryCandidate,
    MemoryEvent,
    ReviewDecision,
)
from opendream.storage import MemoryStore
from opendream.validation import validate_document

REPO_ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-07-12T12:00:00Z"
GENOME_HASH = "a" * 64


class CandidateExportTests(unittest.TestCase):
    def _store(self, workspace: Path) -> MemoryStore:
        store = MemoryStore(workspace)
        store.initialize()
        event = MemoryEvent(
            event_id="event-1",
            session_id="session-1",
            turn_id="turn-1",
            timestamp=NOW,
            scope="project",
            kind="project_decision",
            source={"channel": "cli", "message_ref": "task-1"},
            content="Use a versioned OpenDream export.",
            reporting_agent={
                "agent_id": "codex",
                "agent_label": "Codex",
                "model_id": "gpt-5",
                "model_version": "2026-07",
                "genome_hash": GENOME_HASH,
            },
        )
        store.append_event(event)
        store.append_candidates(
            [
                MemoryCandidate(
                    candidate_id="candidate-1",
                    derived_from_event_ids=["event-1"],
                    type="project_decision",
                    scope="project",
                    title="Version the integration",
                    summary="Use a versioned export contract.",
                    body="Consumers must pin a supported contract range.",
                    confidence=0.9,
                    salience=0.8,
                    status="new",
                    created_at=NOW,
                    origin_mode="scheduled",
                )
            ],
            "extract-1",
        )
        store.mark_candidates_processed(["candidate-1"])
        store.append_review_decision(
            ReviewDecision(
                id="review-1",
                queue_item_type="memory_candidate",
                queue_item_id="candidate-1",
                action="promote",
                rationale="Evidence is attributable.",
                actor="operator",
                created_at=NOW,
            )
        )
        store.write_consolidation_audit(
            "consolidate-1",
            [
                ConsolidationOperation(
                    op_id="op-1",
                    run_id="consolidate-1",
                    op="supersede",
                    target_id="memory-old",
                    reason="Newer evidence",
                    source_event_ids=["event-1"],
                    timestamp=NOW,
                    payload={"superseded_by": "memory-new"},
                )
            ],
            {"status": "completed"},
            store.snapshot_store_text(),
        )
        return store

    def test_export_is_schema_valid_attributable_and_privacy_safe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            payload = build_candidate_export(store, now=NOW)

        validate_document("promotion-candidate-export.schema.json", payload)
        self.assertEqual(payload["candidate_export_version"], "1")
        candidate = payload["candidates"][0]
        self.assertEqual(candidate["processing_state"], "processed")
        self.assertEqual(candidate["review_decisions"][0]["action"], "promote")
        self.assertEqual(candidate["consolidation_operations"][0]["op"], "supersede")
        evidence = candidate["evidence_spans"][0]
        self.assertEqual(evidence["event_id"], "event-1")
        self.assertEqual(evidence["reporting_agent"]["genome_hash"], GENOME_HASH)
        self.assertNotIn("content", evidence)
        self.assertEqual(len(evidence["content_sha256"]), 64)

    def test_cli_export_matches_build_function(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            store = self._store(workspace)
            expected = build_candidate_export(store, now=NOW)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "opendream.cli",
                    "export",
                    "candidates",
                    "--workspace",
                    str(workspace),
                    "--now",
                    NOW,
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
        self.assertEqual(json.loads(completed.stdout), expected)


if __name__ == "__main__":
    unittest.main()
