from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from opendream.integration import emit_event, maintain, prepare_context
from opendream.observability import index_observability
from opendream.storage import MemoryStore
from opendream.webapp import build_server

FIXED_NOW = "2026-04-10T12:00:00Z"


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


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
        self.assertEqual(payload.get("product_posture"), "deterministic-by-choice")
        self.assertEqual(payload.get("semantic_capability_state"), "disabled_by_choice")
        self.assertIn("memory_quality", payload)
        self.assertIn("context_pruning", payload)
        self.assertIn("last_semantic_run", payload)
        self.assertIn("service_management", payload)

    def test_concurrent_ui_context_requests_rebuild_index_without_racing(self) -> None:
        self.store.observability_index_path.unlink(missing_ok=True)
        payloads: list[dict[str, object]] = []
        failures: list[BaseException] = []
        lock = threading.Lock()

        def worker() -> None:
            try:
                payload = self.get_json("/api/ui-context")
            except BaseException as exc:  # pragma: no cover - captured for assertion
                with lock:
                    failures.append(exc)
                return
            with lock:
                payloads.append(payload)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)

        self.assertFalse(failures, failures)
        self.assertEqual(len(payloads), 4)
        self.assertTrue(self.store.observability_index_path.exists())

    def test_api_service_control_enable_and_disable(self) -> None:
        try:
            status, out = self.post_json("/api/service/control", {"action": "enable"})
            self.assertEqual(status, 200)
            self.assertEqual(out.get("status"), "ok")
            self.assertEqual(out["service"]["policy"]["management_mode"], "managed")
            self.assertTrue(out["service"]["running"])

            status, out = self.post_json("/api/service/control", {"action": "disable"})
            self.assertEqual(status, 200)
            self.assertEqual(out.get("status"), "ok")
            self.assertEqual(out["service"]["policy"]["management_mode"], "disabled")
            self.assertFalse(out["service"]["running"])
        finally:
            self.post_json("/api/service/control", {"action": "disable"})

    def test_head_and_favicon_requests_do_not_error(self) -> None:
        head_req = urllib.request.Request(f"{self.base_url}/overview", method="HEAD")
        with urllib.request.urlopen(head_req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers.get("Content-Type", ""))

        favicon_req = urllib.request.Request(f"{self.base_url}/favicon.ico", method="GET")
        with urllib.request.urlopen(favicon_req) as resp:
            self.assertEqual(resp.status, 204)
            self.assertEqual(resp.read(), b"")

    def test_api_service_control_poll_runs_semantic_cycle(self) -> None:
        self.store.save_semantic_config(
            {
                **self.store.load_semantic_config(),
                "mode": "semantic",
                "execution_strategy": "direct-provider",
                "candidate_strategies": ["direct-provider", "deterministic"],
                "preferred_auth_mode": "direct-provider",
            }
        )
        self.store.save_provider_registry(
            [
                {
                    "provider_id": "openai-main",
                    "transport": "openai",
                    "model_id": "gpt-5.4",
                    "roles": ["synthesis", "verification"],
                    "health_status": "healthy",
                }
            ]
        )
        emit_event(
            self.store,
            kind="task_outcome",
            content=(
                "Workflow to reproduce the failure: run pytest tests/test_worker.py "
                "because Redis is required locally."
            ),
            scope="project",
            channel="cli",
            message_ref="semantic-poll-1",
            timestamp="2026-04-10T12:01:00Z",
        )
        emit_event(
            self.store,
            kind="task_outcome",
            content=(
                "The tests failed because the local Redis service was missing; "
                "the working command sequence is docker compose up redis then pytest."
            ),
            scope="project",
            channel="cli",
            message_ref="semantic-poll-2",
            timestamp="2026-04-10T12:02:00Z",
        )

        status, out = self.post_json("/api/service/control", {"action": "poll", "now": FIXED_NOW})

        self.assertEqual(status, 200)
        self.assertEqual(out.get("status"), "ok")
        self.assertEqual(out.get("action"), "poll")
        self.assertTrue(out["result"]["backlog_results"])
        self.assertEqual(out["result"]["backlog_results"][0]["status"], "completed")
        self.assertEqual(out["overview"]["runtime_management"]["semantic_runtime"]["state"], "materialized")

    def test_api_ui_context_semantic_summary_from_disk_config(self) -> None:
        cfg = self.store.memory_root / "state" / "semantic_config.json"
        cfg.write_text(json.dumps({"mode": "hybrid"}), encoding="utf-8")
        payload = self.get_json("/api/ui-context")
        self.assertEqual(payload.get("semantic_state_summary"), "semantic:hybrid")
        self.assertEqual(payload.get("workspace_probe_status"), "ok")
        self.assertEqual(payload.get("dream_mode"), "hybrid")

    def test_api_ui_context_marks_semantic_setup_required_truthfully(self) -> None:
        self.store.save_semantic_config(
            {
                **self.store.load_semantic_config(),
                "mode": "semantic",
                "execution_strategy": "deterministic",
                "candidate_strategies": ["codex-account", "deterministic"],
            }
        )
        payload = self.get_json("/api/ui-context")
        self.assertEqual(payload.get("product_posture"), "semantic-first")
        self.assertEqual(payload.get("semantic_capability_state"), "setup_required")
        self.assertIsInstance(payload.get("semantic_unavailability_reason"), str)
        self.assertEqual(payload["scope_health"]["label"], "Semantic setup required")
        self.assertEqual(payload["scope_health"]["link"], "/settings")

    def test_api_ui_context_marks_semantic_ready(self) -> None:
        self.store.save_semantic_config(
            {
                **self.store.load_semantic_config(),
                "mode": "semantic",
                "execution_strategy": "direct-provider",
                "candidate_strategies": ["direct-provider", "deterministic"],
                "preferred_auth_mode": "direct-provider",
            }
        )
        self.store.save_provider_registry(
            [
                {
                    "provider_id": "openai-main",
                    "transport": "openai",
                    "model_id": "gpt-5.4",
                    "roles": ["synthesis", "verification"],
                    "health_status": "healthy",
                }
            ]
        )
        self.store.save_learned_context_records(
            [
                {
                    "record_id": "lc-1",
                    "workspace_id": self.store.store_id,
                    "source_event_ids": ["evt-1"],
                    "query_family_tags": ["python", "verification"],
                    "summary": "The workspace repeatedly needs Python verification guidance.",
                    "details": "Recent tasks often ask for verification and local Python tooling.",
                    "assumptions": "Python workflow remains stable.",
                    "provider_id": "openai-main",
                    "model_id": "gpt-5.4",
                    "prompt_version": "2026-04-19",
                    "created_at": "2026-04-19T10:00:00Z",
                    "fresh_until": "2026-04-26T10:00:00Z",
                    "confidence": 0.87,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "harm_signals": [],
                    "promotion_target": "learned_context",
                    "status": "active",
                }
            ]
        )
        payload = self.get_json("/api/ui-context")
        self.assertEqual(payload.get("product_posture"), "semantic-first")
        self.assertEqual(payload.get("semantic_capability_state"), "ready")
        self.assertEqual(payload["scope_health"]["label"], "Semantic ready")
        self.assertEqual(payload["scope_health"]["link"], "/overview")

    def test_api_ui_context_marks_applied_but_unevidenced_semantic_as_degraded(self) -> None:
        self.store.save_semantic_config(
            {
                **self.store.load_semantic_config(),
                "mode": "semantic",
                "execution_strategy": "direct-provider",
                "candidate_strategies": ["direct-provider", "deterministic"],
                "preferred_auth_mode": "direct-provider",
            }
        )
        self.store.save_provider_registry(
            [
                {
                    "provider_id": "openai-main",
                    "transport": "openai",
                    "model_id": "gpt-5.4",
                    "roles": ["synthesis", "verification"],
                    "health_status": "healthy",
                }
            ]
        )
        payload = self.get_json("/api/ui-context")
        self.assertEqual(payload.get("product_posture"), "semantic-first")
        self.assertEqual(payload.get("semantic_capability_state"), "degraded")
        self.assertEqual(payload["scope_health"]["label"], "Semantic degraded")
        self.assertEqual(payload["scope_health"]["link"], "/settings")

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

    def test_api_overview_includes_semantic_change_summary(self) -> None:
        self.store.save_learned_context_records(
            [
                {
                    "record_id": "lc-active-1",
                    "workspace_id": self.store.store_id,
                    "source_event_ids": ["evt-1"],
                    "query_family_tags": ["redis", "workflow"],
                    "summary": "Keep the active semantic workflow note available.",
                    "details": "This remains active and should appear as kept in the compare view.",
                    "assumptions": "Workflow is current.",
                    "provider_id": "openai-main",
                    "model_id": "gpt-5.4",
                    "prompt_version": "2026-04-19",
                    "created_at": "2026-04-19T09:00:00Z",
                    "fresh_until": "2026-04-26T09:00:00Z",
                    "confidence": 0.88,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "harm_signals": [],
                    "promotion_target": "learned_context",
                    "status": "active",
                },
                {
                    "record_id": "lc-active-2",
                    "workspace_id": self.store.store_id,
                    "source_event_ids": ["evt-3"],
                    "query_family_tags": ["redis", "workflow"],
                    "summary": "Second active semantic workflow note should be suppressed by the profile budget.",
                    "details": "This stays active in the store but should not fit into the assembled context.",
                    "assumptions": "Profile budgets remain bounded.",
                    "provider_id": "openai-main",
                    "model_id": "gpt-5.4",
                    "prompt_version": "2026-04-19",
                    "created_at": "2026-04-19T08:30:00Z",
                    "fresh_until": "2026-04-26T08:30:00Z",
                    "confidence": 0.58,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "harm_signals": [],
                    "promotion_target": "learned_context",
                    "status": "active",
                },
                {
                    "record_id": "lc-pruned-1",
                    "workspace_id": self.store.store_id,
                    "source_event_ids": ["evt-2"],
                    "query_family_tags": ["redis", "jobs"],
                    "summary": "Redis troubleshooting note was recently superseded.",
                    "details": "A newer semantic note replaced this one.",
                    "assumptions": "Redis workflow moved forward.",
                    "provider_id": "openai-main",
                    "model_id": "gpt-5.4",
                    "prompt_version": "2026-04-19",
                    "created_at": "2026-04-19T08:00:00Z",
                    "fresh_until": "2026-04-26T08:00:00Z",
                    "confidence": 0.64,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "harm_signals": [],
                    "promotion_target": "learned_context",
                    "status": "superseded",
                    "superseded_by": "lc-active-1",
                    "status_changed_at": "2026-04-10T11:30:00Z",
                    "restorable_until": "2026-04-11T11:30:00Z",
                },
            ]
        )
        context = prepare_context(
            self.store,
            query="redis workflow verification",
            now=FIXED_NOW,
        )
        index_observability(self.store, now=FIXED_NOW)

        payload = self.get_json("/api/overview")
        summary = payload.get("semantic_change_summary")
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary["latest_context_id"], context["context_id"])
        self.assertEqual(summary["kept_count"], 1)
        self.assertEqual(summary["suppressed_count"], 1)
        self.assertEqual(summary["deactivated_count"], 1)
        self.assertEqual(summary["restorable_count"], 1)

    def test_semantic_changes_api_returns_compare_payload_and_supports_context_lookup(self) -> None:
        self.store.save_learned_context_records(
            [
                {
                    "record_id": "lc-keep-1",
                    "workspace_id": self.store.store_id,
                    "source_event_ids": ["evt-1"],
                    "query_family_tags": ["workflow", "redis"],
                    "summary": "Keep this learned-context item in the assembled context.",
                    "details": "It should show up as kept.",
                    "assumptions": "Still relevant.",
                    "provider_id": "openai-main",
                    "model_id": "gpt-5.4",
                    "prompt_version": "2026-04-23",
                    "created_at": "2026-04-23T09:00:00Z",
                    "fresh_until": "2026-04-30T09:00:00Z",
                    "confidence": 0.93,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "harm_signals": [],
                    "promotion_target": "learned_context",
                    "status": "active",
                },
                {
                    "record_id": "lc-suppress-1",
                    "workspace_id": self.store.store_id,
                    "source_event_ids": ["evt-2"],
                    "query_family_tags": ["workflow", "redis"],
                    "summary": "Suppress this active learned-context item from the assembled context.",
                    "details": "It should be grouped under suppressed in this context.",
                    "assumptions": "Useful later.",
                    "provider_id": "openai-main",
                    "model_id": "gpt-5.4",
                    "prompt_version": "2026-04-23",
                    "created_at": "2026-04-23T08:00:00Z",
                    "fresh_until": "2026-04-30T08:00:00Z",
                    "confidence": 0.57,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "harm_signals": [],
                    "promotion_target": "learned_context",
                    "status": "active",
                },
                {
                    "record_id": "lc-deactivated-1",
                    "workspace_id": self.store.store_id,
                    "source_event_ids": ["evt-3"],
                    "query_family_tags": ["jobs"],
                    "summary": "This learned-context item was removed from active learned context.",
                    "details": "It should be restorable.",
                    "assumptions": "Recent semantic churn.",
                    "provider_id": "openai-main",
                    "model_id": "gpt-5.4",
                    "prompt_version": "2026-04-23",
                    "created_at": "2026-04-23T07:00:00Z",
                    "fresh_until": "2026-04-30T07:00:00Z",
                    "confidence": 0.68,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "harm_signals": [],
                    "promotion_target": "learned_context",
                    "status": "superseded",
                    "superseded_by": "lc-keep-1",
                    "status_changed_at": "2026-04-10T11:45:00Z",
                    "restorable_until": "2026-04-11T11:45:00Z",
                },
            ]
        )
        context = prepare_context(
            self.store,
            query="redis workflow verification",
            now=FIXED_NOW,
        )
        index_observability(self.store, now=FIXED_NOW)

        latest = self.get_json("/api/semantic-changes/latest")
        self.assertEqual(latest["source_kind"], "context_assembly")
        self.assertEqual(latest["source_id"], context["context_id"])
        self.assertEqual(latest["summary_counts"]["kept_count"], 1)
        self.assertEqual(latest["summary_counts"]["suppressed_count"], 1)
        self.assertEqual(latest["summary_counts"]["deactivated_count"], 1)
        self.assertEqual(latest["summary_counts"]["restorable_count"], 1)
        self.assertEqual(latest["view_hints"]["default_view_mode"], "summary")
        self.assertIn("side_by_side", latest["view_hints"]["available_compare_modes"])
        self.assertIn("overlay", latest["view_hints"]["available_compare_modes"])
        change_classes = {item["change_class"] for item in latest["items"]}
        self.assertIn("kept", change_classes)
        self.assertIn("suppressed", change_classes)
        self.assertIn("deactivated", change_classes)
        suppressed_item = next(item for item in latest["items"] if item["change_class"] == "suppressed")
        self.assertEqual(suppressed_item["retention_effect"], "still_active_not_purged")
        self.assertIn("Not purged", suppressed_item["operator_summary"])
        self.assertIn("usually no action", " ".join(suppressed_item["operator_next_actions"]).lower())
        self.assertEqual(
            suppressed_item["memory_detail_href"],
            f"/memories/changes/{context['context_id']}?item=lc-suppress-1",
        )

        by_context = self.get_json(f"/api/semantic-changes/{context['context_id']}")
        self.assertEqual(by_context["change_review_id"], latest["change_review_id"])

    def test_semantic_changes_latest_returns_unavailable_payload_without_learned_context(self) -> None:
        latest = self.get_json("/api/semantic-changes/latest")

        self.assertEqual(latest["status"], "not_available")
        self.assertEqual(latest["reason_code"], "no_learned_context")
        self.assertIn("durable memory exists", latest["details"])
        self.assertEqual(latest["learned_context_total"], 0)
        self.assertEqual(latest["comparable_context_total"], 0)
        self.assertIn("next_actions", latest)

    def test_semantic_changes_latest_explains_contexts_without_comparable_items(self) -> None:
        prepare_context(self.store, query="redis workflow verification", now=FIXED_NOW)
        self.store.save_learned_context_records(
            [
                {
                    "record_id": "lc-unmatched-1",
                    "workspace_id": self.store.store_id,
                    "source_event_ids": ["evt-unmatched"],
                    "query_family_tags": ["billing"],
                    "summary": "Billing setup note that should not match this context.",
                    "details": (
                        "This note exists, but the prepared context has no kept or suppressed "
                        "learned-context compare items."
                    ),
                    "assumptions": "Billing work is unrelated to the query.",
                    "provider_id": "openai-main",
                    "model_id": "gpt-5.4",
                    "prompt_version": "2026-04-23",
                    "created_at": "2026-04-23T09:00:00Z",
                    "fresh_until": "2026-04-30T09:00:00Z",
                    "confidence": 0.12,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "harm_signals": [],
                    "promotion_target": "learned_context",
                    "status": "active",
                }
            ]
        )
        index_observability(self.store, now=FIXED_NOW)

        latest = self.get_json("/api/semantic-changes/latest")

        self.assertEqual(latest["status"], "not_available")
        self.assertEqual(latest["reason_code"], "no_comparable_context")
        self.assertGreaterEqual(latest["learned_context_total"], 1)
        self.assertGreaterEqual(latest["context_assembly_total"], 1)
        self.assertEqual(latest["comparable_context_total"], 0)
        self.assertIn("without learned-context kept or suppressed items", latest["details"])

    def test_semantic_changes_api_returns_404_for_unknown_context(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{self.base_url}/api/semantic-changes/not-found")
        try:
            self.assertEqual(ctx.exception.code, 404)
        finally:
            ctx.exception.close()

    def test_post_learned_context_restore_reactivates_recent_record(self) -> None:
        self.store.save_learned_context_records(
            [
                {
                    "record_id": "lc-restore-1",
                    "workspace_id": self.store.store_id,
                    "source_event_ids": ["evt-restore"],
                    "query_family_tags": ["verification"],
                    "summary": "Recently pruned verification note.",
                    "details": "This note should be recoverable for a short window.",
                    "assumptions": "The note is still useful.",
                    "provider_id": "openai-main",
                    "model_id": "gpt-5.4",
                    "prompt_version": "2026-04-19",
                    "created_at": "2026-04-19T08:00:00Z",
                    "fresh_until": "2026-04-26T08:00:00Z",
                    "confidence": 0.72,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "harm_signals": [],
                    "promotion_target": "learned_context",
                    "status": "superseded",
                    "superseded_by": "lc-newer-1",
                    "status_changed_at": "2026-04-10T11:45:00Z",
                    "restorable_until": "2026-04-11T11:45:00Z",
                }
            ]
        )
        index_observability(self.store, now=FIXED_NOW)

        status, out = self.post_json(
            "/api/learned-context/restore",
            {"record_id": "lc-restore-1", "now": FIXED_NOW},
        )

        self.assertEqual(status, 200)
        self.assertEqual(out.get("status"), "ok")
        self.assertEqual(out["result"]["status"], "restored")
        records = self.store.load_learned_context_records()
        restored = next(record for record in records if record["record_id"] == "lc-restore-1")
        self.assertEqual(restored["status"], "active")
        self.assertEqual(restored["restored_from_status"], "superseded")
        self.assertEqual(restored["restored_at"], FIXED_NOW)
        self.assertNotIn("superseded_by", restored)

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

    def test_api_graph_defaults_to_latest_memory_focus_and_depth_two(self) -> None:
        latest_memory = self.get_json("/api/memories")["items"][0]["memory_id"]
        payload = self.get_json("/api/graph")
        self.assertEqual(payload["focus"], latest_memory)
        self.assertEqual(payload["depth"], 2)

    def test_graph_route_redirects_to_default_focus_query(self) -> None:
        latest_memory = self.get_json("/api/memories")["items"][0]["memory_id"]
        opener = urllib.request.build_opener(_NoRedirectHandler())
        req = urllib.request.Request(f"{self.base_url}/graph", method="GET")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(req)
        try:
            self.assertEqual(ctx.exception.code, 302)
            location = ctx.exception.headers["Location"]
            self.assertIsNotNone(location)
            parsed = urlparse(location)
            self.assertEqual(parsed.path, "/graph")
            params = parse_qs(parsed.query)
            self.assertEqual(params.get("focus"), [latest_memory])
            self.assertEqual(params.get("depth"), ["2"])
        finally:
            ctx.exception.close()

    def test_force_layout_omits_positions(self) -> None:
        payload = self.get_json("/api/graph?layout=forceatlas2")
        self.assertEqual(payload["layout"], "forceatlas2")
        for node in payload["nodes"]:
            self.assertNotIn("x", node)

    def test_depth_query_param_accepted(self) -> None:
        payload = self.get_json("/api/graph?depth=3")
        self.assertEqual(payload["depth"], 3)

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
