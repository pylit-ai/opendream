from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from opendream import workspace_catalog
from opendream.storage import MemoryStore
from opendream.webapp import build_server


class StaticHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        workspace = Path(self.temp_dir.name) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(workspace)
        self.store.initialize(store_kind="project")
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

    def _expect_404(self, path: str) -> None:
        try:
            urllib.request.urlopen(f"{self.base_url}{path}")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 404)
            return
        self.fail(f"expected 404 for {path}")

    def test_static_serves_committed_test_fixture(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/static/vendor/_test.js") as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers["Content-Type"], "application/javascript")
            self.assertIn("test fixture", resp.read().decode("utf-8"))

    def test_static_refuses_path_traversal_dotdot(self) -> None:
        self._expect_404("/static/../webapp.py")

    def test_static_refuses_encoded_traversal(self) -> None:
        self._expect_404("/static/%2e%2e/webapp.py")

    def test_static_refuses_unknown_file(self) -> None:
        self._expect_404("/static/vendor/does-not-exist.js")

    def test_static_sets_long_cache_header(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/static/vendor/_test.js") as resp:
            self.assertEqual(resp.headers["Cache-Control"], "public, max-age=86400")

    def test_insights_route_serves_spa_shell(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/insights") as resp:
            html = resp.read().decode("utf-8")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("OpenDream Observe", html)

    def test_showcase_route_remains_compatible(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/showcase") as resp:
            html = resp.read().decode("utf-8")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("OpenDream Observe", html)

    def test_workspaces_payload_includes_instance_summary(self) -> None:
        workspace_catalog.upsert_entry(self.store.workspace, discovered_by="init")
        with urllib.request.urlopen(f"{self.base_url}/api/workspaces?include_tempdir=1") as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(resp.status, 200)
        self.assertIn("instance_summary", payload)
        self.assertIn("current_context", payload)
        self.assertEqual(payload["current_context"]["status"], "workspace")
        self.assertIn("instance", payload["entries"][0])

    def test_workspace_launch_requires_local_action_header(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/workspace-instances/launch",
            data=json.dumps({"workspace": str(self.store.workspace)}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request)
        self.assertEqual(ctx.exception.code, 403)

    def test_initialize_current_requires_local_action_header(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/workspace-instances/initialize-current",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request)
        self.assertEqual(ctx.exception.code, 403)
