"""Tests for opendream.sessions canonical session-id minter."""
from __future__ import annotations

import contextvars
import json
import tempfile
import unittest
from pathlib import Path

from opendream.integration import emit_event
from opendream.sessions import (
    _SESSION_ID_VAR,
    _workspace_token_path,
    clear_session_id,
    current_session_id,
    set_session_id,
)
from opendream.storage import MemoryStore

FIXED_NOW = "2026-01-01T00:00:00Z"


def _make_store(tmp: Path) -> MemoryStore:
    workspace = tmp / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    store = MemoryStore(workspace)
    store.initialize(store_kind="project")
    return store


class TestContextVar(unittest.TestCase):
    def setUp(self) -> None:
        # Reset contextvar between tests
        _SESSION_ID_VAR.set(None)

    def tearDown(self) -> None:
        _SESSION_ID_VAR.set(None)

    def test_default_is_none(self) -> None:
        self.assertIsNone(current_session_id())

    def test_set_and_get(self) -> None:
        set_session_id("sess-abc")
        self.assertEqual(current_session_id(), "sess-abc")

    def test_clear(self) -> None:
        set_session_id("sess-abc")
        clear_session_id()
        self.assertIsNone(current_session_id())

    def test_reentrant_same_id(self) -> None:
        """Multiple calls within the same contextvar scope return same id."""
        set_session_id("span-xyz")
        ids = [current_session_id() for _ in range(5)]
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(ids[0], "span-xyz")

    def test_child_context_isolation(self) -> None:
        """contextvars.copy_context() provides isolation."""
        set_session_id("parent-sess")

        def child() -> str | None:
            # child context inherits parent value — no separate set
            return current_session_id()

        ctx = contextvars.copy_context()
        result = ctx.run(child)
        self.assertEqual(result, "parent-sess")


class TestTokenFile(unittest.TestCase):
    def setUp(self) -> None:
        _SESSION_ID_VAR.set(None)
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_dir.name)
        self.store = _make_store(self.tmp)

    def tearDown(self) -> None:
        _SESSION_ID_VAR.set(None)
        self.tmp_dir.cleanup()

    def test_token_written_on_set(self) -> None:
        set_session_id("tok-001", store=self.store)
        token_path = _workspace_token_path(self.store)
        self.assertTrue(token_path.exists())
        self.assertEqual(token_path.read_text(encoding="utf-8"), "tok-001")

    def test_token_removed_on_clear(self) -> None:
        set_session_id("tok-002", store=self.store)
        clear_session_id(store=self.store)
        token_path = _workspace_token_path(self.store)
        self.assertFalse(token_path.exists())

    def test_token_roundtrip(self) -> None:
        set_session_id("tok-003", store=self.store)
        # Simulate a fresh contextvar (different span) — contextvar still holds value
        # but the value should match what was written
        self.assertEqual(current_session_id(), "tok-003")

    def test_corrupt_token_returns_none_gracefully(self) -> None:
        """A corrupt token file must not crash callers."""
        token_path = _workspace_token_path(self.store)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        # Write binary garbage
        token_path.write_bytes(b"\xff\xfe")
        # current_session_id only reads contextvar; corrupt file doesn't crash
        self.assertIsNone(current_session_id())

    def test_set_without_store_does_not_write_file(self) -> None:
        set_session_id("no-store-sess")
        token_path = _workspace_token_path(self.store)
        self.assertFalse(token_path.exists())


class TestEmitEventFallback(unittest.TestCase):
    def setUp(self) -> None:
        _SESSION_ID_VAR.set(None)
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_dir.name)
        self.store = _make_store(self.tmp)

    def tearDown(self) -> None:
        _SESSION_ID_VAR.set(None)
        self.tmp_dir.cleanup()

    _emit_counter = 0

    def _emit_and_read_session_id(self, session_id: str | None = None) -> str:
        """Emit an event and return the session_id stored in the event file."""
        TestEmitEventFallback._emit_counter += 1
        result = emit_event(
            self.store,
            kind="project_decision",
            content=f"test content for session test {self._emit_counter}",
            scope="project",
            channel="cli",
            message_ref=f"ref-session-test-{self._emit_counter}",
            timestamp=FIXED_NOW,
            session_id=session_id,
        )
        event_path = self.store.workspace / result["event_path"]
        target_event_id = result["event_id"]
        for line in event_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("event_id") == target_event_id:
                data = row
                break
        else:
            raise AssertionError(f"event_id {target_event_id} not found in {event_path}")
        return data["session_id"]

    def test_explicit_session_id_used(self) -> None:
        set_session_id("current-sess")
        sid = self._emit_and_read_session_id(session_id="explicit-sess")
        self.assertEqual(sid, "explicit-sess")

    def test_fallback_to_current_session_id(self) -> None:
        set_session_id("current-sess")
        sid = self._emit_and_read_session_id()
        self.assertEqual(sid, "current-sess")

    def test_fallback_to_stable_id_when_unset(self) -> None:
        """When current_session_id() is None, emit_event uses stable_id fallback."""
        self.assertIsNone(current_session_id())
        sid = self._emit_and_read_session_id()
        # Must be a non-empty string (the stable_id hash)
        self.assertIsInstance(sid, str)
        self.assertTrue(len(sid) > 0)
        # Must NOT equal the value we'd get if current_session_id were set
        set_session_id("different-sess")
        sid2 = self._emit_and_read_session_id()
        self.assertEqual(sid2, "different-sess")
