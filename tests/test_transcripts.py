from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from opendream.storage import MemoryStore
from opendream.transcripts import flatten_codex_row, ingest_codex_sessions


class TranscriptIngestTests(unittest.TestCase):
    def test_flatten_codex_row_supports_common_role_content_shape(self) -> None:
        row = {
            "id": "turn-1",
            "timestamp": "2026-04-29T12:00:00Z",
            "role": "assistant",
            "content": [{"type": "text", "text": "Use the dream dashboard."}],
        }

        flattened = flatten_codex_row(row)

        self.assertIsNotNone(flattened)
        assert flattened is not None
        self.assertEqual(flattened["speaker"], "assistant")
        self.assertEqual(flattened["text"], "Use the dream dashboard.")

    def test_ingest_codex_sessions_walks_well_known_nested_layout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspace"
            source = root / "codex" / "sessions" / "2026" / "04" / "29"
            source.mkdir(parents=True)
            workspace.mkdir()
            store = MemoryStore(workspace)
            store.initialize(store_kind="project")
            session_file = source / "rollout.jsonl"
            session_file.write_text(
                json.dumps(
                    {
                        "id": "turn-1",
                        "timestamp": "2026-04-29T12:00:00Z",
                        "role": "user",
                        "content": "Please verify dreams.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = ingest_codex_sessions(store, root / "codex" / "sessions")

            self.assertEqual(result["files_written"], 1)
            self.assertEqual(result["rows_out"], 1)
            written = list(store.transcripts_dir.glob("*.jsonl"))
            self.assertEqual(len(written), 1)
