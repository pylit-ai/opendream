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
from opendream.webapp import INDEX_HTML, build_server

_OBSERVE_UI_JS = (
    Path(__file__).resolve().parents[1] / "opendream" / "static" / "observe-ui.js"
).read_text(encoding="utf-8")

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
            reporting_agent={
                "agent_id": "codex",
                "agent_label": "Codex",
                "runtime": "codex-cli",
                "model_id": "gpt-5.4",
                "model_version": "2026-04-17",
            },
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
            reporting_agent={"agent_id": "claude-code", "agent_label": "Claude Code"},
        )
        maintain(self.store, now=FIXED_NOW)
        self.context = prepare_context(
            self.store,
            query="package manager and redis",
            now=FIXED_NOW,
            reporting_agent={
                "agent_id": "codex",
                "agent_label": "Codex",
                "runtime": "codex-cli",
                "model_id": "gpt-5.4",
                "model_version": "2026-04-17",
            },
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
        self.assertIn("freshness", payload)
        self.assertEqual(payload["freshness"]["last_event_at"], FIXED_NOW)
        self.assertEqual(payload["freshness"]["last_session_activity_at"], FIXED_NOW)
        self.assertEqual(payload["freshness"]["last_retrieval_at"], FIXED_NOW)
        self.assertEqual(payload["freshness"]["last_run_at"], FIXED_NOW)

        memories = self.get_json("/api/memories")
        self.assertGreaterEqual(memories["total"], 2)
        self.assertEqual(len(memories["items"]), 2)

    def test_health_api_reports_evidence(self) -> None:
        payload = self.get_json("/api/health")
        self.assertEqual(payload["startup"]["status"], "ok")
        self.assertEqual(payload["readiness"]["status"], "ready")
        self.assertIn(payload["liveness"]["status"], {"live", "idle"})
        self.assertEqual(payload["evidence"]["last_event_at"], FIXED_NOW)
        self.assertEqual(payload["evidence"]["last_run_at"], FIXED_NOW)
        self.assertEqual(payload["evidence"]["pending_events"], 0)
        self.assertEqual(payload["evidence"]["pending_candidates"], 0)
        self.assertTrue(payload["live_check"]["supported"])
        self.assertIsNone(payload["live_check"]["last_probe_at"])

    def test_memories_api_pagination_limit_cap_and_range_query(self) -> None:
        page0 = self.get_json("/api/memories?limit=1&offset=0&sort=memory_id&sort_dir=asc")
        self.assertGreaterEqual(page0["total"], 2)
        self.assertEqual(len(page0["items"]), 1)
        page1 = self.get_json("/api/memories?limit=1&offset=1&sort=memory_id&sort_dir=asc")
        self.assertEqual(len(page1["items"]), 1)
        self.assertNotEqual(page0["items"][0]["memory_id"], page1["items"][0]["memory_id"])

        capped = self.get_json("/api/memories?limit=9999&offset=0")
        self.assertLessEqual(len(capped["items"]), 500)

        ranged = self.get_json("/api/memories?salience_min=0&salience_max=1&limit=50")
        self.assertIn("total", ranged)
        self.assertIn("items", ranged)
        self.assertLessEqual(len(ranged["items"]), 50)

    def test_memories_api_search_filter_and_sort_by_reporting_agent(self) -> None:
        codex = self.get_json("/api/memories?agent_id=codex&limit=50")
        self.assertGreaterEqual(codex["total"], 1)
        self.assertTrue(
            all(item["reporting_agents"][0]["agent_id"] == "codex" for item in codex["items"])
        )

        searched = self.get_json("/api/memories?search=Claude%20Code&limit=50")
        self.assertGreaterEqual(searched["total"], 1)
        self.assertTrue(
            any(
                agent["agent_label"] == "Claude Code"
                for item in searched["items"]
                for agent in item["reporting_agents"]
            )
        )

        sorted_rows = self.get_json("/api/memories?sort=reporting_agent&sort_dir=asc&limit=50")
        labels = [item["reporting_agent_label"] for item in sorted_rows["items"]]
        self.assertEqual(labels, sorted(labels))

    def test_retrievals_and_runs_expose_agent_provenance(self) -> None:
        retrievals = self.get_json("/api/retrievals?search=gpt-5.4&sort=reporting_agent&limit=50")
        self.assertGreaterEqual(retrievals["total"], 1)
        retrieval = retrievals["items"][0]
        self.assertEqual(retrieval["reporting_agent"]["agent_id"], "codex")
        self.assertEqual(retrieval["reporting_agent"]["model_id"], "gpt-5.4")
        self.assertTrue(retrieval["source_reporting_agents"])

        runs = self.get_json("/api/runs?search=gpt-5.4&limit=50")
        self.assertGreaterEqual(runs["total"], 1)
        self.assertTrue(
            any(
                agent.get("model_id") == "gpt-5.4"
                for run in runs["items"]
                for agent in run.get("source_reporting_agents", [])
            )
        )

    def test_legacy_codex_events_are_inferred_and_unknown_model_is_explicit(self) -> None:
        emit_event(
            self.store,
            kind="task_outcome",
            content="Legacy Codex completion.",
            scope="project",
            channel="cli",
            message_ref="codex-post-task",
            timestamp="2026-03-27T12:05:00Z",
        )
        maintain(self.store, now="2026-03-27T12:05:00Z")
        index_observability(self.store, now=FIXED_NOW)

        sessions = self.get_json("/api/sessions")
        session_id = next(
            item["session_id"]
            for item in sessions["items"]
            if any(
                agent["agent_id"] == "codex" and agent.get("model_id") == "unknown"
                for agent in item.get("reporting_agents", [])
            )
        )
        timeline = self.get_json(f"/api/sessions/{session_id}/timeline")
        row = next(
            item
            for item in timeline["timeline"]
            if "Legacy Codex completion." in str((item.get("payload") or {}).get("content", ""))
        )
        self.assertTrue(
            row["reporting_agent"]["agent_id"] == "codex"
        )
        self.assertEqual(row["reporting_agent"]["model_id"], "unknown")

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

    def test_retrievals_api_pagination_and_total(self) -> None:
        r0 = self.get_json("/api/retrievals?limit=1&offset=0&sort=id&sort_dir=asc")
        self.assertIn("total", r0)
        self.assertGreaterEqual(r0["total"], 1)
        self.assertEqual(len(r0["items"]), 1)
        capped = self.get_json("/api/retrievals?limit=9999&offset=0")
        self.assertLessEqual(len(capped["items"]), 500)

    def test_runs_sessions_and_graph_endpoints(self) -> None:
        runs = self.get_json("/api/runs")
        self.assertIn("total", runs)
        self.assertGreaterEqual(runs["total"], 1)
        self.assertGreaterEqual(len(runs["items"]), 1)
        run_id = runs["items"][0]["run_id"]
        run = self.get_json(f"/api/runs/{run_id}")
        self.assertIn("phase_traces", run)
        self.assertIn("diff_text", run)
        self.assertEqual(run["started_at"], FIXED_NOW)
        self.assertEqual(run["ended_at"], FIXED_NOW)

        sessions = self.get_json("/api/sessions")
        self.assertGreaterEqual(len(sessions["items"]), 1)
        session_id = sessions["items"][0]["session_id"]
        self.assertEqual(sessions["items"][0]["started_at"], FIXED_NOW)
        self.assertEqual(sessions["items"][0]["ended_at"], FIXED_NOW)
        self.assertEqual(sessions["items"][0]["last_activity_at"], FIXED_NOW)
        timeline = self.get_json(f"/api/sessions/{session_id}/timeline")
        self.assertIn("timeline", timeline)

        graph = self.get_json("/api/graph")
        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)

    def test_server_refreshes_index_when_new_capture_arrives(self) -> None:
        later = "2026-03-27T12:10:00Z"
        emit_event(
            self.store,
            kind="task_outcome",
            content="A fresh live capture arrived after observe serve started.",
            scope="project",
            channel="cli",
            message_ref="obs-msg-live",
            session_id="session-live",
            timestamp=later,
            reporting_agent={
                "agent_id": "claude-code",
                "agent_label": "Claude Code",
                "model_id": "claude-opus-4.1",
                "model_version": "2026-04-17",
            },
        )
        maintain(self.store, now=later)

        sessions = self.get_json("/api/sessions")
        self.assertEqual(sessions["items"][0]["session_id"], "session-live")
        self.assertEqual(sessions["items"][0]["last_activity_at"], later)

        overview = self.get_json("/api/overview")
        self.assertEqual(overview["freshness"]["last_event_at"], later)
        self.assertEqual(overview["freshness"]["last_run_at"], later)

    def test_runs_api_pagination_and_limit_cap(self) -> None:
        page0 = self.get_json("/api/runs?limit=1&offset=0&sort=run_id&sort_dir=asc")
        self.assertIn("total", page0)
        self.assertGreaterEqual(page0["total"], 1)
        self.assertEqual(len(page0["items"]), 1)
        capped = self.get_json("/api/runs?limit=9999&offset=0")
        self.assertLessEqual(len(capped["items"]), 500)

    def test_live_check_appends_probe_without_creating_memory(self) -> None:
        payload = self.post_json("/api/health/live-check", {})
        probe = payload["probe"]
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(probe["observed_in_index"])
        self.assertEqual(payload["evidence"]["last_event_at"], probe["timestamp"])
        self.assertEqual(payload["evidence"]["pending_events"], 0)

        memories = self.get_json("/api/memories")
        self.assertEqual(memories["total"], 2)

        health = self.get_json("/api/health")
        self.assertEqual(health["live_check"]["last_probe_at"], probe["timestamp"])
        self.assertEqual(health["live_check"]["last_probe_event_id"], probe["event_id"])

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

    def test_index_html_includes_ux_ax_markers(self) -> None:
        bundle = INDEX_HTML + _OBSERVE_UI_JS
        for needle in (
            "od-skip-link",
            "od-dream-mode-select",
            "syncDreamModeUi",
            "/api/semantic-dream-mode",
            "od-route-announce",
            "od-command-palette",
            "od-skeleton-wrap",
            "odCopyApiCurl",
            "odCopyApiFetch",
            "odCopyCurrentViewUrl",
            "od-overview-strip",
            "About this dashboard",
            "od-first-steps",
            "odDismissFirstSteps",
            "opendream-first-steps-dismissed",
            "focus_search=1",
            "odCommandPalette",
            "routeToPageId",
            "handlePaletteAction",
            "Agent",
            "agent_id",
            "reporting_agent",
            "model_id",
            "agent-pill",
            "agentPillsHtml",
        ):
            self.assertIn(needle, bundle)

    def test_graph_js_includes_a11y_banner(self) -> None:
        graph_js = Path(__file__).resolve().parents[1] / "opendream" / "static" / "graph.js"
        text = graph_js.read_text(encoding="utf-8")
        self.assertIn("od-graph-a11y-banner", text)
        self.assertIn("od-graph-open-data", text)


if __name__ == "__main__":
    unittest.main()
