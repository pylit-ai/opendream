from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from opendream.episodes import row_to_event
from opendream.storage import MemoryStore
from opendream.transcripts import (
    flatten_claude_row,
    flatten_codex_row,
    ingest_codex_sessions,
)


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
        self.assertEqual(flattened["reporting_agent"]["agent_id"], "codex")
        self.assertEqual(flattened["reporting_agent"]["agent_label"], "Codex")

    def test_flatten_codex_row_supports_response_item_payload_shape(self) -> None:
        row = {
            "timestamp": "2026-05-23T04:00:00Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Rerun the dream worker."}],
            },
        }

        flattened = flatten_codex_row(row)

        self.assertIsNotNone(flattened)
        assert flattened is not None
        self.assertEqual(flattened["timestamp"], "2026-05-23T04:00:00Z")
        self.assertEqual(flattened["speaker"], "user")
        self.assertEqual(flattened["text"], "Rerun the dream worker.")
        self.assertEqual(flattened["reporting_agent"]["agent_id"], "codex")

    def test_flatten_claude_row_preserves_agent_identity_in_memory_event(self) -> None:
        flattened = flatten_claude_row(
            {
                "type": "assistant",
                "timestamp": "2026-05-23T04:00:00Z",
                "message": {"content": "Use pnpm for the frontend workflow."},
                "sessionId": "claude-session",
                "uuid": "claude-turn",
            }
        )

        self.assertIsNotNone(flattened)
        assert flattened is not None
        self.assertEqual(flattened["reporting_agent"]["agent_id"], "claude-code")
        self.assertEqual(flattened["reporting_agent"]["agent_label"], "Claude Code")

        event = row_to_event(flattened)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.reporting_agent["agent_id"], "claude-code")
        self.assertEqual(event.reporting_agent["agent_label"], "Claude Code")

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

    def test_ingest_codex_sessions_can_filter_by_workspace_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspace"
            other_workspace = root / "other"
            source = root / "codex" / "sessions" / "2026" / "05" / "23"
            source.mkdir(parents=True)
            workspace.mkdir()
            other_workspace.mkdir()
            store = MemoryStore(workspace)
            store.initialize(store_kind="project")

            def write_session(path: Path, cwd: Path, content: str) -> None:
                path.write_text(
                    json.dumps(
                        {
                            "timestamp": "2026-05-23T04:00:00Z",
                            "type": "turn_context",
                            "payload": {"cwd": str(cwd)},
                        }
                    )
                    + "\n"
                    + json.dumps(
                        {
                            "timestamp": "2026-05-23T04:01:00Z",
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": content}],
                            },
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

            write_session(source / "matching.jsonl", workspace, "MRH-local note.")
            write_session(source / "other.jsonl", other_workspace, "Other workspace note.")

            result = ingest_codex_sessions(
                store,
                root / "codex" / "sessions",
                workspace_filter=workspace,
            )

            self.assertEqual(result["files_written"], 1)
            self.assertEqual(result["files_filtered"], 1)
            self.assertEqual(result["rows_out"], 1)
            written = list(store.transcripts_dir.glob("*.jsonl"))
            self.assertEqual(len(written), 1)
            self.assertIn("MRH-local note.", written[0].read_text(encoding="utf-8"))
