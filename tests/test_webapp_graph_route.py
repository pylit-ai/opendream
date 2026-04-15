from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from opendream.integration import emit_event, maintain
from opendream.observability import index_observability
from opendream.storage import MemoryStore
from opendream.webapp import INDEX_HTML, build_server

_OBSERVE_UI_JS = (
    Path(__file__).resolve().parent.parent / "opendream" / "static" / "observe-ui.js"
).read_text(encoding="utf-8")

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

    def post_json(self, path: str, body: dict[str, object]) -> tuple[int, dict[str, object]]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return int(resp.status), json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                raw = exc.read().decode("utf-8")
            finally:
                exc.close()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"error": raw}
            return int(exc.code), payload

    def test_api_ui_context_matches_store_workspace(self) -> None:
        payload = self.get_json("/api/ui-context")
        self.assertEqual(payload.get("kind"), "observe_serve")
        self.assertEqual(
            payload.get("workspace_path"),
            str(self.store.workspace.resolve()),
        )
        self.assertIn("workspace_path", payload)
        self.assertIn("semantic_state_summary", payload)
        self.assertIsNone(payload.get("semantic_state_summary"))
        self.assertEqual(payload.get("workspace_probe_status"), "ok")
        self.assertEqual(payload.get("dream_mode"), "deterministic")
        sh = payload.get("scope_health")
        self.assertIsInstance(sh, dict)
        self.assertIn("kind", sh)
        self.assertIn("level", sh)
        self.assertIn("label", sh)
        self.assertIn("memory_total", sh)
        self.assertIn("link", sh)
        self.assertIsInstance(sh.get("link"), str)
        self.assertTrue(str(sh.get("link", "")).startswith("/"))

    def test_api_ui_context_semantic_summary_from_disk_config(self) -> None:
        cfg = self.store.memory_root / "state" / "semantic_config.json"
        cfg.write_text(json.dumps({"mode": "hybrid"}), encoding="utf-8")
        payload = self.get_json("/api/ui-context")
        self.assertEqual(payload.get("semantic_state_summary"), "semantic:hybrid")
        self.assertEqual(payload.get("workspace_probe_status"), "ok")
        self.assertEqual(payload.get("dream_mode"), "hybrid")

    def test_post_semantic_dream_mode_persists(self) -> None:
        status, out = self.post_json("/api/semantic-dream-mode", {"mode": "hybrid"})
        self.assertEqual(status, 200)
        self.assertEqual(out.get("status"), "ok")
        self.assertEqual(out.get("dream_mode"), "hybrid")
        cfg = self.store.load_semantic_config()
        self.assertEqual(cfg.get("mode"), "hybrid")
        get_ctx = self.get_json("/api/ui-context")
        self.assertEqual(get_ctx.get("dream_mode"), "hybrid")

    def test_post_semantic_dream_mode_invalid_mode(self) -> None:
        status, out = self.post_json("/api/semantic-dream-mode", {"mode": "nope"})
        self.assertEqual(status, 400)
        self.assertIn("error", out)

    def test_api_ui_meta_exposes_cli_json_version(self) -> None:
        payload = self.get_json("/api/ui-meta")
        self.assertIn("cli_json_version", payload)
        self.assertIsInstance(payload.get("cli_json_version"), int)

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

    def test_graph_html_links_static_assets(self) -> None:
        # Sanity check: the SPA HTML loads observe-ui.js; graph scripts are
        # requested from that bundle when visiting /graph.
        self.assertIn("/static/observe-ui.js", INDEX_HTML)
        for path in [
            '/static/graph.js',
            '/static/vendor/sigma.min.js',
            '/static/vendor/graphology.umd.min.js',
        ]:
            self.assertIn(path, _OBSERVE_UI_JS)

    def test_observe_shell_nav_async_and_presets(self) -> None:
        bundle = INDEX_HTML + _OBSERVE_UI_JS
        for needle in (
            'href="/sessions"',
            'href="/context"',
            "pathMatchesNav",
            "runRender",
            "applyMemoryTimePreset",
            "applyRetrievalTimePreset",
            'aria-live="polite"',
            "Could not load",
            "Store metadata (read-only)",
            "od-data-freshness",
            "Data loaded at",
            "odCopyApiUrl",
            "od-copy-err-btn",
            "err.status",
            "sidebar-sec-catalog",
            "sidebar-sec-this-ws",
            "od-scope-bar",
            "od-scope-add-bookmark",
            "od-scope-bookmark-list",
            "opendream-dashboard-bookmarks",
            "od-empty-nextsteps",
            "od-overview-strip",
            "odCopyCurrentViewUrl",
            "About this dashboard",
            "od-dream-mode-select",
            "semantic-dream-mode",
            "sidebar-mobile-open",
            "data-mobile-nav",
        ):
            self.assertIn(needle, bundle)

    def test_graph_static_accessibility_needles(self) -> None:
        graph_js = (
            Path(__file__).resolve().parent.parent / "opendream" / "static" / "graph.js"
        ).read_text(encoding="utf-8")
        for needle in (
            "Graph data",
            "graph-data-panel",
            "graph-shortcuts-help",
            "data-view-mode",
            "applyViewModeVisibility",
            "graph-data-table",
        ):
            self.assertIn(needle, graph_js)
