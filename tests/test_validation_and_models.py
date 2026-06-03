from __future__ import annotations

import json
import random
import unittest
from pathlib import Path

from opendream.extractor import extract_candidates
from opendream.validation import SchemaValidationError, validate_document

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = "2026-03-26T12:00:00Z"


class ValidationAndModelTests(unittest.TestCase):
    def test_golden_fixture_events_match_schema(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
        for line in fixture.read_text(encoding="utf-8").splitlines():
            validate_document("memory-event.schema.json", json.loads(line))

    def test_extracted_candidates_match_schema(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
        events = [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines() if line.strip()]
        candidates = extract_candidates(events, origin_mode="scheduled", now=FIXED_NOW)
        self.assertGreater(len(candidates), 0)
        for candidate in candidates:
            validate_document("memory-candidate.schema.json", candidate.to_dict())

    def test_property_style_memory_topics_remain_schema_valid(self) -> None:
        rng = random.Random(7)
        statuses = ["active", "contested", "superseded", "quarantined"]
        for index in range(20):
            payload = {
                "memory_id": f"mem_{index}",
                "type": "semantic_fact",
                "scope": "project",
                "title": f"Fact: generated-{index}",
                "summary": f"summary-{index}",
                "body": f"body-{index}",
                "status": rng.choice(statuses),
                "confidence": round(rng.random(), 2),
                "salience": round(rng.random(), 2),
                "source_event_ids": [f"event_{index}"],
                "supersedes": [],
                "conflicts_with": [],
                "valid_from": FIXED_NOW,
                "valid_to": None,
                "access_count": index,
                "last_accessed_at": None,
                "created_at": FIXED_NOW,
                "updated_at": FIXED_NOW,
            }
            with self.subTest(index=index):
                validate_document("memory-topic.schema.json", payload)

    def test_invalid_memory_topic_status_is_rejected(self) -> None:
        payload = {
            "memory_id": "mem_invalid",
            "type": "semantic_fact",
            "scope": "project",
            "title": "Fact: invalid",
            "summary": "invalid",
            "body": "invalid",
            "status": "deprecated",
            "confidence": 0.5,
            "salience": 0.5,
            "source_event_ids": ["event_invalid"],
            "supersedes": [],
            "conflicts_with": [],
            "valid_from": FIXED_NOW,
            "valid_to": None,
            "access_count": 0,
            "last_accessed_at": None,
            "created_at": FIXED_NOW,
            "updated_at": FIXED_NOW,
        }
        with self.assertRaises(SchemaValidationError):
            validate_document("memory-topic.schema.json", payload)


if __name__ == "__main__":
    unittest.main()
