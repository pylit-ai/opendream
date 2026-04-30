"""Tests for session diagnostics (Phase 3/4 of spec 447)."""
from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from opendream.integration import emit_event, maintain
from opendream.observability import _session_diagnostics, index_observability
from opendream.sessions import cleanup_orphans
from opendream.storage import MemoryStore
from opendream.webapp import build_server

FIXED_NOW = "2026-04-29T10:00:00Z"


def _make_store(tmp: Path) -> MemoryStore:
    workspace = tmp / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    store = MemoryStore(workspace)
    store.initialize(store_kind="project")
    return store


def _emit(store: MemoryStore, *, kind: str = "project_decision", session_id: str | None = None) -> dict:
    return emit_event(
        store,
        kind=kind,
        content="test content",
        scope="project",
        channel="cli",
        message_ref="test-ref",
        session_id=session_id,
        timestamp=FIXED_NOW,
        reporting_agent={"agent_id": "test", "agent_label": "Test"},
    )


class TestSessionDiagnosticsOrphanEvents(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store = _make_store(Path(self.tmp_dir.name))

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_no_orphans_when_sessions_match(self) -> None:
        _emit(self.store, session_id="sess-a")
        maintain(self.store, now=FIXED_NOW)
        index_observability(self.store, now=FIXED_NOW)
        result = _session_diagnostics(self.store)
        # sess-a should be known; no orphans
        self.assertEqual(result["orphan_events_total"], 0)
        self.assertEqual(len(result["orphan_events"]), 0)

    def test_orphan_event_detected(self) -> None:
        # Build an index from a known session first so we have an authoritative source.
        _emit(self.store, session_id="sess-known")
        maintain(self.store, now=FIXED_NOW)
        index_observability(self.store, now=FIXED_NOW)
        # Inject an event directly with a session_id that has no entity record
        events_dir = self.store.events_dir
        events_dir.mkdir(parents=True, exist_ok=True)
        orphan_event = {
            "event_id": "evt-orphan-1",
            "session_id": "sess-ghost",
            "kind": "project_decision",
            "content": "orphan",
            "scope": "project",
            "channel": "cli",
            "timestamp": FIXED_NOW,
            "source": {"message_ref": "ref"},
            "tags": [],
        }
        path = events_dir / "orphan.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(orphan_event) + "\n")
        result = _session_diagnostics(self.store)
        self.assertGreater(result["orphan_events_total"], 0)
        sids = {item["session_id"] for item in result["orphan_events"]}
        self.assertIn("sess-ghost", sids)

    def test_orphan_events_capped_at_25_samples(self) -> None:
        # Build an index so we have an authoritative source.
        _emit(self.store, session_id="sess-anchor")
        maintain(self.store, now=FIXED_NOW)
        index_observability(self.store, now=FIXED_NOW)
        events_dir = self.store.events_dir
        events_dir.mkdir(parents=True, exist_ok=True)
        path = events_dir / "many_orphans.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for i in range(30):
                ev = {
                    "event_id": f"evt-orphan-{i}",
                    "session_id": f"sess-ghost-{i}",
                    "kind": "project_decision",
                    "content": "orphan",
                    "scope": "project",
                    "channel": "cli",
                    "timestamp": FIXED_NOW,
                    "source": {"message_ref": "ref"},
                    "tags": [],
                }
                fh.write(json.dumps(ev) + "\n")
        result = _session_diagnostics(self.store)
        self.assertEqual(result["orphan_events_total"], 30)
        self.assertLessEqual(len(result["orphan_events"]), 25)


class TestSessionDiagnosticsZeroEvents(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store = _make_store(Path(self.tmp_dir.name))

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_normal_session_not_in_zero_list(self) -> None:
        _emit(self.store, session_id="sess-with-events")
        maintain(self.store, now=FIXED_NOW)
        index_observability(self.store, now=FIXED_NOW)
        result = _session_diagnostics(self.store)
        self.assertNotIn("sess-with-events", result["zero_event_sessions"])

    def test_total_events_count(self) -> None:
        _emit(self.store, session_id="sess-x")
        _emit(self.store, session_id="sess-x")
        result = _session_diagnostics(self.store)
        self.assertGreaterEqual(result["total_events"], 2)


class TestSessionDiagnosticsStructure(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store = _make_store(Path(self.tmp_dir.name))

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_result_has_required_keys(self) -> None:
        result = _session_diagnostics(self.store)
        for key in [
            "orphan_events",
            "orphan_events_total",
            "mismatch_records",
            "mismatch_records_total",
            "zero_event_sessions",
            "zero_event_sessions_total",
            "total_sessions",
            "total_events",
        ]:
            self.assertIn(key, result)

    def test_readonly_does_not_mutate(self) -> None:
        _emit(self.store, session_id="sess-readonly")
        before = list(self.store.load_events())
        _session_diagnostics(self.store)
        after = list(self.store.load_events())
        self.assertEqual(len(before), len(after))


class TestCleanupOrphans(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store = _make_store(Path(self.tmp_dir.name))

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _inject_orphan(self, event_id: str, session_id: str) -> None:
        events_dir = self.store.events_dir
        events_dir.mkdir(parents=True, exist_ok=True)
        path = events_dir / f"{event_id}.jsonl"
        ev = {
            "event_id": event_id,
            "session_id": session_id,
            "kind": "project_decision",
            "content": "orphan",
            "scope": "project",
            "channel": "cli",
            "timestamp": FIXED_NOW,
            "source": {"message_ref": "ref"},
            "tags": [],
        }
        with path.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(ev) + "\n")

    def test_dry_run_does_not_remove(self) -> None:
        # Emit a real event and index so we have an authoritative source.
        _emit(self.store, session_id="sess-real-dry")
        maintain(self.store, now=FIXED_NOW)
        index_observability(self.store, now=FIXED_NOW)
        # Inject an orphan after indexing.
        self._inject_orphan("evt-dry", "sess-ghost-dry")
        result = cleanup_orphans(self.store, orphans=True, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertGreater(result["removed_event_count"], 0)
        # Event file should still contain the orphan
        diag = _session_diagnostics(self.store)
        self.assertGreater(diag["orphan_events_total"], 0)

    def test_cleanup_removes_orphan_events(self) -> None:
        # Emit a real event and index so we have an authoritative source.
        _emit(self.store, session_id="sess-real-del")
        maintain(self.store, now=FIXED_NOW)
        index_observability(self.store, now=FIXED_NOW)
        self._inject_orphan("evt-del", "sess-ghost-del")
        # Verify orphan detected before cleanup
        diag_before = _session_diagnostics(self.store)
        self.assertGreater(diag_before["orphan_events_total"], 0)
        result = cleanup_orphans(self.store, orphans=True, dry_run=False)
        self.assertFalse(result["dry_run"])
        self.assertGreater(result["removed_event_count"], 0)
        # After cleanup orphan should be gone
        diag_after = _session_diagnostics(self.store)
        self.assertEqual(diag_after["orphan_events_total"], 0)

    def test_cleanup_preserves_valid_events(self) -> None:
        _emit(self.store, session_id="sess-keep")
        maintain(self.store, now=FIXED_NOW)
        index_observability(self.store, now=FIXED_NOW)
        self._inject_orphan("evt-bad", "sess-nonexistent")
        before_count = len(
            [e for e in self.store.load_events() if e.get("session_id") == "sess-keep"]
        )
        cleanup_orphans(self.store, orphans=True, dry_run=False)
        after_count = len(
            [e for e in self.store.load_events() if e.get("session_id") == "sess-keep"]
        )
        self.assertEqual(before_count, after_count)


class TestSessionDiagnosticsWebapp(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store = _make_store(Path(self.tmp_dir.name))
        _emit(self.store, session_id="sess-webapp-test")
        maintain(self.store, now=FIXED_NOW)
        index_observability(self.store, now=FIXED_NOW)
        self.server = build_server(self.store, host="127.0.0.1", port=0)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)
        self.tmp_dir.cleanup()

    def test_diagnostics_endpoint_returns_200(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/api/sessions/diagnostics") as resp:
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read().decode())
        self.assertIn("orphan_events", body)
        self.assertIn("total_sessions", body)
        self.assertIn("total_events", body)

    def test_diagnostics_endpoint_read_only(self) -> None:
        before = len(self.store.load_events())
        with urllib.request.urlopen(f"{self.base_url}/api/sessions/diagnostics"):
            pass
        after = len(self.store.load_events())
        self.assertEqual(before, after)


class TestSessionsCliArgparse(unittest.TestCase):
    """Smoke-test CLI subcommand registration via build_parser()."""

    def test_sessions_diagnose_registered(self) -> None:
        from opendream.cli import build_parser
        parser = build_parser()
        # Should parse without error
        args = parser.parse_args(["sessions", "diagnose", "--workspace", "/tmp/fake"])
        self.assertEqual(args.sessions_command, "diagnose")
        from opendream.cli import command_sessions_diagnose
        self.assertIs(args.func, command_sessions_diagnose)

    def test_sessions_cleanup_registered(self) -> None:
        from opendream.cli import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "sessions", "cleanup", "--workspace", "/tmp/fake",
            "--orphans", "--dry-run",
        ])
        self.assertEqual(args.sessions_command, "cleanup")
        self.assertTrue(args.orphans)
        self.assertTrue(args.dry_run)

    def test_sessions_cleanup_requires_flag(self) -> None:
        from types import SimpleNamespace

        from opendream.cli import command_sessions_cleanup
        args = SimpleNamespace(
            workspace="/tmp/fake",
            orphans=False,
            zero_events=False,
            dry_run=True,
            yes=False,
            memory_dir=None,
        )
        with self.assertRaises(ValueError):
            command_sessions_cleanup(args)


if __name__ == "__main__":
    unittest.main()
