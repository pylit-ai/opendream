from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from opendream.integration import emit_event, maintain, prepare_context
from opendream.observability import index_observability
from opendream.storage import MemoryStore
from opendream.webapp import build_server

FIXED_NOW = "2026-03-27T12:00:00Z"


class ObservabilityIntegrationTests(unittest.TestCase):
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
            message_ref="obs-msg-1",
            timestamp=FIXED_NOW,
            tags=["key:package-manager"],
        )
        emit_event(
            self.store,
            kind="environment_requirement",
            content="Redis is required for background jobs.",
            scope="project",
            channel="cli",
            message_ref="obs-msg-2",
            timestamp=FIXED_NOW,
            tags=["key:redis"],
        )
        maintain(self.store, now=FIXED_NOW)
        self.context = prepare_context(self.store, query="package manager and redis", now=FIXED_NOW)
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

    def get_json(self, path: str) -> dict[str, object]:
        with urllib.request.urlopen(f"{self.base_url}{path}") as response:
            return json.loads(response.read().decode("utf-8"))

    def post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_index_contains_core_entity_groups(self) -> None:
        payload = self.get_json("/api/overview")
        self.assertEqual(payload["memory_counts"]["total"], 2)
        self.assertIn("recent_runs", payload)

        memories = self.get_json("/api/memories")
        self.assertGreaterEqual(memories["total"], 2)
        self.assertEqual(len(memories["items"]), 2)

    def test_context_and_retrieval_surfaces_are_available(self) -> None:
        retrievals = self.get_json("/api/retrievals")
        self.assertGreaterEqual(len(retrievals["items"]), 1)
        retrieval_id = retrievals["items"][0]["id"]
        retrieval = self.get_json(f"/api/retrievals/{retrieval_id}")
        self.assertIn("explanations", retrieval)
        self.assertIn("final_context_assembly_order", retrieval)

        context = self.get_json(f"/api/context/{self.context['context_id']}")
        self.assertEqual(context["context_id"], self.context["context_id"])
        self.assertTrue(context["assembled_text"].startswith("# OpenDream Memory Context"))

    def test_runs_sessions_and_graph_endpoints(self) -> None:
        runs = self.get_json("/api/runs")
        self.assertGreaterEqual(len(runs["items"]), 1)
        run_id = runs["items"][0]["run_id"]
        run = self.get_json(f"/api/runs/{run_id}")
        self.assertIn("phase_traces", run)
        self.assertIn("diff_text", run)

        sessions = self.get_json("/api/sessions")
        self.assertGreaterEqual(len(sessions["items"]), 1)
        session_id = sessions["items"][0]["session_id"]
        timeline = self.get_json(f"/api/sessions/{session_id}/timeline")
        self.assertIn("timeline", timeline)

        graph = self.get_json("/api/graph")
        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)

    def test_review_annotation_export_and_sse_work(self) -> None:
        reviews = self.get_json("/api/reviews")
        self.assertGreaterEqual(len(reviews["items"]), 1)
        queue_item = reviews["items"][0]

        annotation = self.post_json(
            "/api/annotations",
            {
                "object_type": "memory",
                "object_id": queue_item["queue_item_id"],
                "actor": "tester",
                "label": "note",
                "note": "looks reasonable",
                "score": 0.8,
            },
        )
        self.assertEqual(annotation["actor"], "tester")

        decision = self.post_json(
            f"/api/reviews/{queue_item['queue_item_id']}/approve",
            {
                "queue_item_type": queue_item["queue_item_type"],
                "actor": "tester",
                "rationale": "approved during test",
            },
        )
        self.assertEqual(decision["action"], "approve")

        export_record = self.post_json(
            "/api/exports",
            {
                "export_type": "run_bundle",
                "actor": "tester",
                "include": ["runs", "memories", "contexts"],
            },
        )
        self.assertEqual(export_record["actor"], "tester")

        with urllib.request.urlopen(f"{self.base_url}/api/stream/status") as response:
            body = response.read().decode("utf-8")
        self.assertIn("event: status", body)
        self.assertIn("event: overview", body)

    def test_static_routes_render_html(self) -> None:
        paths = [
            "/overview",
            "/memories",
            "/runs",
            "/retrievals",
            "/reviews",
            "/graph",
            "/evals",
            "/exports",
            "/settings",
        ]
        for path in paths:
            with urllib.request.urlopen(f"{self.base_url}{path}") as response:
                html = response.read().decode("utf-8")
            self.assertIn("OpenDream Observability", html)


if __name__ == "__main__":
    unittest.main()
