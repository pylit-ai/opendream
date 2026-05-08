from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from opendream.integration import emit_event, maintain, prepare_context
from opendream.observability import index_observability
from opendream.storage import MemoryStore
from opendream.webapp import build_server

FIXED_NOW = "2026-03-27T12:00:00Z"


class PerfEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(self.workspace)
        self.store.initialize(store_kind="project")
        emit_event(
            self.store,
            kind="project_decision",
            content="Use pnpm for workspace dependencies.",
            scope="project",
            channel="cli",
            message_ref="perf-msg-1",
            timestamp=FIXED_NOW,
            tags=["key:package-manager"],
            reporting_agent={"agent_id": "codex", "agent_label": "Codex"},
        )
        emit_event(
            self.store,
            kind="environment_requirement",
            content="Redis is required.",
            scope="project",
            channel="cli",
            message_ref="perf-msg-2",
            timestamp=FIXED_NOW,
            tags=["key:redis"],
            reporting_agent={"agent_id": "claude-code", "agent_label": "Claude Code"},
        )
        maintain(self.store, now=FIXED_NOW)
        prepare_context(
            self.store,
            query="package manager",
            now=FIXED_NOW,
            reporting_agent={"agent_id": "codex", "agent_label": "Codex"},
        )
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
        self.temp_dir.cleanup()

    def get_json(self, path: str) -> dict:
        with urllib.request.urlopen(f"{self.base_url}{path}") as resp:
            return json.loads(resp.read().decode("utf-8"))

    # --- /api/overview/lite ---

    def test_overview_lite_shape(self) -> None:
        payload = self.get_json("/api/overview/lite")
        self.assertIn("generated_at", payload)
        self.assertIn("store_health", payload)
        self.assertIn("memory_counts", payload)
        self.assertIn("recent_runs", payload)
        self.assertIn("recent_sessions", payload)
        sh = payload["store_health"]
        self.assertIn("state", sh)
        self.assertIn("memory_root", sh)
        self.assertIn("pending_events", sh)
        mc = payload["memory_counts"]
        self.assertIn("total", mc)
        self.assertIn("by_status", mc)

    def test_overview_lite_smaller_than_full(self) -> None:
        lite = self.get_json("/api/overview/lite")
        full = self.get_json("/api/overview")
        lite_bytes = len(json.dumps(lite))
        full_bytes = len(json.dumps(full))
        self.assertLess(lite_bytes, full_bytes)

    def test_overview_lite_recent_runs_max_5(self) -> None:
        payload = self.get_json("/api/overview/lite")
        self.assertLessEqual(len(payload["recent_runs"]), 5)

    def test_overview_lite_recent_sessions_max_5(self) -> None:
        payload = self.get_json("/api/overview/lite")
        self.assertLessEqual(len(payload["recent_sessions"]), 5)

    def test_overview_lite_session_fields(self) -> None:
        payload = self.get_json("/api/overview/lite")
        for s in payload["recent_sessions"]:
            self.assertIn("session_id", s)
            self.assertIn("event_count", s)
            self.assertIn("started_at", s)

    # --- /api/runs?limit ---

    def test_runs_limit_param(self) -> None:
        payload = self.get_json("/api/runs?limit=1")
        self.assertLessEqual(len(payload["items"]), 1)

    def test_runs_since_future_returns_empty(self) -> None:
        payload = self.get_json("/api/runs?since=2099-01-01T00:00:00Z")
        self.assertEqual(payload["items"], [])

    def test_runs_list_no_heavy_fields(self) -> None:
        payload = self.get_json("/api/runs")
        for row in payload["items"]:
            self.assertNotIn("phase_traces", row)
            self.assertNotIn("operations", row)

    def test_runs_limit_cap(self) -> None:
        # Requesting over the cap should not error; should return <= cap
        payload = self.get_json("/api/runs?limit=9999")
        self.assertLessEqual(len(payload["items"]), 500)

    # --- /api/retrievals?limit/since ---

    def test_retrievals_limit_param(self) -> None:
        payload = self.get_json("/api/retrievals?limit=1")
        self.assertLessEqual(len(payload["items"]), 1)

    def test_retrievals_since_future_returns_empty(self) -> None:
        payload = self.get_json("/api/retrievals?since=2099-01-01T00:00:00Z")
        self.assertEqual(payload["items"], [])

    def test_retrievals_list_no_heavy_fields(self) -> None:
        payload = self.get_json("/api/retrievals")
        for row in payload["items"]:
            self.assertNotIn("candidates", row)
            self.assertNotIn("explanations", row)

    def test_list_endpoints_do_not_load_full_observability_index(self) -> None:
        list_paths = [
            "/api/overview",
            "/api/dream/cycles?limit=50",
            "/api/sessions",
            "/api/runs",
            "/api/retrievals",
        ]
        with patch(
            "opendream.webapp.load_or_build_index",
            side_effect=AssertionError("full index loaded for list endpoint"),
        ):
            for path in list_paths:
                with self.subTest(path=path):
                    payload = self.get_json(path)
                    if path == "/api/overview":
                        self.assertIn("memory_counts", payload)
                    else:
                        self.assertIn("items", payload)
                    for row in payload.get("items", []):
                        self.assertNotIn("graph", row)
                        self.assertNotIn("operations", row)
                        self.assertNotIn("candidates", row)
                        self.assertNotIn("explanations", row)
                        self.assertNotIn("timeline", row)

    def test_compact_index_excludes_graph_and_detail_payloads(self) -> None:
        compact = self.store.load_observability_compact_index()
        entities = compact["entities"]
        self.assertNotIn("graph", entities)
        for row in entities["runs"]:
            self.assertNotIn("phase_traces", row)
            self.assertNotIn("operations", row)
            self.assertNotIn("diff_text", row)
        for row in entities["retrievals"]:
            self.assertNotIn("candidates", row)
            self.assertNotIn("explanations", row)
            self.assertNotIn("selected_memory_ids", row)
            self.assertIn("selected_memory_ids_count", row)
        for row in entities["sessions"]:
            self.assertNotIn("timeline", row)

    # --- /api/sessions?limit/since ---

    def test_sessions_limit_param(self) -> None:
        payload = self.get_json("/api/sessions?limit=1")
        self.assertLessEqual(len(payload["items"]), 1)

    def test_sessions_since_future_returns_empty(self) -> None:
        payload = self.get_json("/api/sessions?since=2099-01-01T00:00:00Z")
        self.assertEqual(payload["items"], [])

    # --- /api/_perf ---

    def test_perf_endpoint_returns_timings(self) -> None:
        # Make a few requests so timings are populated
        self.get_json("/api/overview/lite")
        self.get_json("/api/runs")
        self.get_json("/api/retrievals")
        payload = self.get_json("/api/_perf")
        self.assertIn("timings", payload)
        self.assertIsInstance(payload["timings"], list)
        # At least the 3 requests above should be recorded
        self.assertGreaterEqual(len(payload["timings"]), 3)

    def test_perf_entries_have_expected_keys(self) -> None:
        self.get_json("/api/overview")
        payload = self.get_json("/api/_perf")
        timings = payload["timings"]
        self.assertTrue(len(timings) > 0)
        entry = timings[-1]
        self.assertIn("path", entry)
        self.assertIn("query_keys", entry)
        self.assertIn("ms", entry)
        self.assertIn("status", entry)

    def test_perf_endpoint_not_self_recorded(self) -> None:
        # /api/_perf calls should not appear in the buffer
        self.get_json("/api/_perf")
        self.get_json("/api/_perf")
        payload = self.get_json("/api/_perf")
        for entry in payload["timings"]:
            self.assertNotEqual(entry["path"], "/api/_perf")
