from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from opendream.integration import emit_event, maintain
from opendream.observability import index_observability
from opendream.storage import MemoryStore
from opendream.webapp import INDEX_HTML, build_server

FIXED_NOW = "2026-04-10T12:00:00Z"


class GraphRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        workspace = Path(self.temp_dir.name) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(workspace)
        self.store.initialize(store_kind="project")
        emit_event(
            self.store,
            kind="project_decision",
            content="seed memory for graph test",
            scope="project",
            channel="cli",
            message_ref="g-1",
            timestamp=FIXED_NOW,
        )
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
        self.temp_dir.cleanup()

    def get_json(self, path: str) -> dict[str, object]:
        with urllib.request.urlopen(f"{self.base_url}{path}") as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_default_layout_includes_positions(self) -> None:
        payload = self.get_json("/api/graph")
        self.assertEqual(payload["layout"], "hierarchical")
        if payload["nodes"]:
            self.assertIn("x", payload["nodes"][0])
            self.assertIn("y", payload["nodes"][0])

    def test_force_layout_omits_positions(self) -> None:
        payload = self.get_json("/api/graph?layout=forceatlas2")
        self.assertEqual(payload["layout"], "forceatlas2")
        for node in payload["nodes"]:
            self.assertNotIn("x", node)

    def test_depth_query_param_accepted(self) -> None:
        payload = self.get_json("/api/graph?depth=3")
        self.assertEqual(payload["depth"], 3)
