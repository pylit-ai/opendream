from __future__ import annotations

import json
import unittest
from pathlib import Path

from opendream_memory.extractor import extract_candidates
from opendream_memory.validation import validate_document


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


if __name__ == "__main__":
    unittest.main()
