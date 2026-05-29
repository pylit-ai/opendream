from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from opendream.integration import archive_stale_learned_context, emit_event, maintain, prepare_context
from opendream.models import ContextAssembly
from opendream.observability import index_observability
from opendream.storage import MemoryStore
from opendream.util import read_json, write_json
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

    def test_dream_run_requires_transcript_import_consent_when_store_is_empty(self) -> None:
        payload = self.post_json("/api/dream/run", {})

        self.assertEqual(payload["status"], "skipped")
        self.assertEqual(payload["reason"], "no-episodes")
        self.assertIsNone(payload["ingest"])
        self.assertFalse(payload["auto_ingested_transcripts"])
        self.assertTrue(payload["auto_ingest_required"])
        self.assertEqual(payload["episode_files_consulted"], 0)

    def test_dream_run_auto_ingests_transcripts_when_consent_payload_is_set(self) -> None:
        source_dir = Path(self.temp_dir.name) / "claude-sessions"
        source_dir.mkdir(parents=True, exist_ok=True)
        (source_dir / "session.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "type": "user",
                            "timestamp": "2026-03-27T12:01:00Z",
                            "message": {
                                "content": "Decision: use uv for OpenDream test execution in this workspace."
                            },
                            "sessionId": "session-auto-ingest",
                            "uuid": "turn-1",
                        }
                    ),
                    json.dumps(
                        {
                            "type": "assistant",
                            "timestamp": "2026-03-27T12:02:00Z",
                            "message": {
                                "content": "Recorded the uv test workflow and linked it to the workspace setup."
                            },
                            "sessionId": "session-auto-ingest",
                            "uuid": "turn-2",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        with mock.patch(
            "opendream.transcripts.auto_detect_claude_project_dir",
            return_value=source_dir,
        ):
            payload = self.post_json("/api/dream/run", {"auto_ingest_transcripts": True})

        self.assertEqual(payload["ingest"]["status"], "ingested")
        self.assertEqual(payload["ingest"]["files_written"], 1)
        self.assertEqual(payload["episode_files_consulted"], 1)
        self.assertTrue(payload["auto_ingested_transcripts"])
        self.assertFalse(payload["auto_ingest_required"])
        self.assertNotEqual(payload.get("reason"), "no-episodes")

    def test_index_contains_core_entity_groups(self) -> None:
        payload = self.get_json("/api/overview")
        self.assertEqual(payload["memory_counts"]["total"], 2)
        self.assertIn("recent_runs", payload)
        self.assertIn("freshness", payload)
        self.assertIn("runtime_management", payload)
        self.assertIn("memory_surface", payload)
        self.assertIn("last_runtime_effects", payload)
        self.assertIn("semantic_runtime", payload["runtime_management"])
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

    def test_status_api_returns_lightweight_workspace_snapshot(self) -> None:
        payload = self.get_json("/api/status")
        self.assertEqual(payload["workspace"], str(self.workspace))
        self.assertTrue(payload["initialized"])
        self.assertIn(payload["state"], {"idle", "pending", "locked"})
        self.assertIn("pending_events", payload)
        self.assertIn("pending_candidates", payload)
        self.assertIn("dream", payload)

    def test_showcase_api_returns_persisted_report(self) -> None:
        report_path = self.store.memory_root / "state" / "showcase_report.json"
        write_json(
            report_path,
            {
                "scenario": "coding-agent-showcase",
                "status": "passed",
                "objective": {
                    "title": "Show that OpenDream turns prior coding-agent history into useful prompt context."
                },
                "evaluation_case": {"user_prompt": "Update Observe UI and recover repo-specific context."},
                "agent_snippet": "OpenDream found prior memory: Use pnpm.",
                "selected_memory_ids": ["mem_showcase"],
                "context": {"links": [{"memory_id": "mem_showcase", "why_included": "lexical match on pnpm"}]},
                "dream_effectiveness": {"effective": {"baseline_to_after": True}},
                "proof": {"source_refs": [{"memory_id": "mem_showcase", "summary": "Use pnpm."}]},
            },
        )
        payload = self.get_json("/api/showcase")
        self.assertEqual(payload["available"], True)
        self.assertEqual(payload["report"]["scenario"], "coding-agent-showcase")
        self.assertIn("useful prompt context", payload["report"]["objective"]["title"])
        self.assertTrue(payload["report"]["dream_effectiveness"]["effective"]["baseline_to_after"])
        self.assertIn("OpenDream found prior memory:", payload["report"]["agent_snippet"])

    def test_overview_uses_latest_context_pruning_evidence(self) -> None:
        payload = self.get_json("/api/overview")
        pruning = payload["context_pruning"]
        self.assertEqual(pruning["status"], "available")
        self.assertEqual(pruning["profile"], self.context["profile"]["name"])
        self.assertEqual(pruning["raw_candidate_count"], self.context["context_pruning"]["candidate_count"])
        self.assertEqual(pruning["injected_count"], self.context["context_pruning"]["injected_count"])
        self.assertEqual(pruning["suppressed_count"], self.context["context_pruning"]["suppressed_count"])
        self.assertEqual(payload["memory_surface"]["durable_active_total"], 2)
        self.assertTrue(payload["memory_surface"]["type_mix"])
        self.assertTrue(payload["memory_surface"]["recent_highlights"])
        self.assertIn(payload["last_runtime_effects"]["run_type"], {"consolidation", "dream", "semantic_dream"})

    def test_prepare_context_persists_structured_learned_context_compare_data(self) -> None:
        self.store.save_learned_context_records(
            [
                {
                    "record_id": "lc-keep-1",
                    "workspace_id": self.store.store_id,
                    "source_event_ids": ["evt-keep-1"],
                    "query_family_tags": ["redis", "workflow"],
                    "summary": "Keep Redis workflow guidance active for task runs.",
                    "details": "This note is strongly relevant and should remain selected.",
                    "assumptions": "Redis-backed tasks are still current.",
                    "provider_id": "openai-main",
                    "model_id": "gpt-5.4",
                    "prompt_version": "2026-04-23",
                    "created_at": "2026-04-23T10:00:00Z",
                    "fresh_until": "2026-04-30T10:00:00Z",
                    "confidence": 0.92,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "harm_signals": [],
                    "promotion_target": "learned_context",
                    "status": "active",
                },
                {
                    "record_id": "lc-suppress-1",
                    "workspace_id": self.store.store_id,
                    "source_event_ids": ["evt-suppress-1"],
                    "query_family_tags": ["redis", "workflow"],
                    "summary": "Second Redis workflow note should be suppressed by the profile budget.",
                    "details": "This remains in the store, but the assembled context should exclude it.",
                    "assumptions": "The lower-ranked variant is still useful later.",
                    "provider_id": "openai-main",
                    "model_id": "gpt-5.4",
                    "prompt_version": "2026-04-23",
                    "created_at": "2026-04-23T09:00:00Z",
                    "fresh_until": "2026-04-30T09:00:00Z",
                    "confidence": 0.61,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "harm_signals": [],
                    "promotion_target": "learned_context",
                    "status": "active",
                },
            ]
        )

        prepare_context(
            self.store,
            query="redis workflow verification",
            now="2026-04-23T12:00:00Z",
            reporting_agent={
                "agent_id": "codex",
                "agent_label": "Codex",
                "runtime": "codex-cli",
                "model_id": "gpt-5.4",
                "model_version": "2026-04-17",
            },
        )

        assemblies = self.store.load_context_assemblies()
        latest = max(assemblies, key=lambda item: str(item.get("created_at") or ""))
        kept = latest.get("selected_learned_context_items")
        suppressed = latest.get("suppressed_learned_context_items")

        self.assertIsInstance(kept, list)
        self.assertIsInstance(suppressed, list)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(suppressed), 1)
        self.assertEqual(kept[0]["record_id"], "lc-keep-1")
        self.assertEqual(kept[0]["change_class"], "kept")
        self.assertEqual(suppressed[0]["record_id"], "lc-suppress-1")
        self.assertEqual(suppressed[0]["change_class"], "suppressed")
        self.assertEqual(suppressed[0]["reason_code"], "profile_budget_exceeded")
        self.assertIn("details_preview", suppressed[0])
        self.assertIn("query_family_tags", suppressed[0])

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
        self.assertEqual(context["latest_memory_use_state"], "not-recorded")
        self.assertEqual(context["context_use_count"], 0)

        contexts = self.get_json("/api/context?limit=1")
        self.assertGreaterEqual(contexts["total"], 1)
        self.assertEqual(len(contexts["items"]), 1)
        self.assertEqual(contexts["items"][0]["context_id"], self.context["context_id"])
        self.assertEqual(contexts["items"][0]["display_name"], "package manager and redis")
        self.assertEqual(contexts["items"][0]["latest_memory_use_state"], "not-recorded")
        self.assertEqual(contexts["items"][0]["context_use_count"], 0)
        self.assertNotIn("assembled_text", contexts["items"][0])

        context_session_id = context["session_id"]
        sessions = self.get_json("/api/sessions")
        context_session = next(
            item
            for item in sessions["items"]
            if item["session_id"] == context_session_id
        )
        self.assertEqual(context_session["display_name"], "package manager and redis")
        timeline = self.get_json(f"/api/sessions/{context_session_id}/timeline")
        self.assertEqual(timeline["display_name"], "package manager and redis")
        context_event = next(
            item
            for item in timeline["timeline"]
            if item.get("kind") == "memory.context.assembled"
        )
        self.assertEqual(context_event["label"], "package manager and redis")
        self.assertEqual(context_event["payload"]["display_name"], "package manager and redis")

    def test_context_use_records_are_indexed(self) -> None:
        payload = {
            "usage_id": "context-use-test",
            "context_id": self.context["context_id"],
            "timestamp": FIXED_NOW,
            "memory_use_state": "used",
            "selected_memory_ids": self.context["selected_memory_ids"],
            "used_memory_ids": self.context["selected_memory_ids"][:1],
            "reporting_agent": {"agent_id": "codex", "agent_label": "Codex"},
        }
        self.store.write_context_use_audit("context-use-test", payload)

        index = index_observability(self.store, now=FIXED_NOW)

        context_use = index["entities"]["context_use"]
        self.assertEqual(len(context_use), 1)
        self.assertEqual(context_use[0]["context_id"], self.context["context_id"])
        self.assertEqual(context_use[0]["memory_use_state"], "used")
        self.assertEqual(context_use[0]["context_query"], "package manager and redis")

        records = self.get_json("/api/context-use?limit=10")
        self.assertEqual(records["total"], 1)
        self.assertEqual(records["items"][0]["usage_id"], "context-use-test")
        self.assertEqual(records["items"][0]["used_memory_ids_count"], 1)

        detail = self.get_json("/api/context-use/context-use-test")
        self.assertEqual(detail["memory_use_state"], "used")
        self.assertEqual(detail["context_display_name"], "package manager and redis")

        context = self.get_json(f"/api/context/{self.context['context_id']}")
        self.assertEqual(context["latest_memory_use_state"], "used")
        self.assertEqual(context["context_use_count"], 1)
        self.assertEqual(context["context_use_records"][0]["usage_id"], "context-use-test")

        contexts = self.get_json("/api/context?limit=1")
        self.assertEqual(contexts["items"][0]["latest_memory_use_state"], "used")
        self.assertEqual(contexts["items"][0]["context_use_count"], 1)

        graph = self.get_json("/api/graph?focus=context-use-test&limit=20&depth=2")
        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(nodes["context-use-test"]["type"], "context_use")
        self.assertEqual(nodes[self.context["context_id"]]["type"], "context")
        edge_types = {(edge["source"], edge["target"], edge["type"]) for edge in graph["edges"]}
        self.assertIn(
            ("context-use-test", self.context["context_id"], "acknowledges_context"),
            edge_types,
        )
        self.assertIn(
            ("context-use-test", self.context["selected_memory_ids"][0], "used_memory"),
            edge_types,
        )

    def test_settings_api_returns_fast_semantic_config_payload(self) -> None:
        payload = self.get_json("/api/settings")
        self.assertIn("semantic_config", payload)
        self.assertIn("retention", payload["semantic_config"])
        self.assertIn("retention_preview", payload)
        self.assertIn("readiness", payload)
        self.assertEqual(
            payload["semantic_config"]["retention"]["learned_context_archive_grace_days"],
            7,
        )
        self.assertIn("selected", payload["retention_preview"])

    def test_semantic_retention_preview_counts_activity_gate(self) -> None:
        self.store.save_learned_context_records(
            [
                {
                    "record_id": "lc-preview-1",
                    "workspace_id": str(self.workspace),
                    "source_event_ids": ["obs-msg-1"],
                    "query_family_tags": ["dependencies"],
                    "summary": "Use pnpm for workspace dependencies.",
                    "details": "Project setup relies on pnpm.",
                    "assumptions": "Workspace keeps the same package manager.",
                    "provider_id": "builtin",
                    "model_id": "heuristic-v1",
                    "prompt_version": "1",
                    "created_at": "2026-03-20T12:00:00Z",
                    "fresh_until": "2026-03-21T12:00:00Z",
                    "confidence": 0.9,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "status": "active",
                }
            ]
        )
        self.store.write_context_assembly(
            ContextAssembly(
                context_id="context-preview-1",
                session_id="session-preview",
                turn_id="turn-preview-1",
                retrieval_run_id="retrieve-preview-1",
                startup_index_snapshot=[],
                selected_memory_ids=[],
                omitted_memory_ids=[],
                omission_reasons=[],
                assembled_text="# OpenDream Memory Context\nQuery: preview",
                character_count=42,
                token_estimate=6,
                created_at="2026-03-22T12:00:00Z",
            )
        )

        archived = self.get_json("/api/semantic-retention-preview?days=1&contexts=1")
        held = self.get_json("/api/semantic-retention-preview?days=1&contexts=99")

        self.assertEqual(archived["selected"]["would_archive_now"], 1)
        self.assertEqual(held["selected"]["would_archive_now"], 0)
        self.assertEqual(held["selected"]["held_by_activity"], 1)

    def test_semantic_retention_preview_explains_archived_recovery(self) -> None:
        self.store.save_learned_context_records(
            [
                {
                    "record_id": "lc-archived-direct",
                    "summary": "Recently archived context.",
                    "details": "Still inside restore window.",
                    "fresh_until": "2026-03-01T12:00:00Z",
                    "status": "archived",
                    "restorable_until": "2100-01-01T00:00:00Z",
                },
                {
                    "record_id": "lc-archived-old",
                    "summary": "Older archived context.",
                    "details": "No restore window was recorded.",
                    "fresh_until": "2026-03-01T12:00:00Z",
                    "status": "archived",
                },
            ]
        )

        payload = self.get_json("/api/semantic-retention-preview?days=30&contexts=4")

        selected = payload["selected"]
        self.assertEqual(selected["active_total"], 0)
        self.assertEqual(selected["archived_total"], 2)
        self.assertEqual(selected["directly_restorable_total"], 1)
        self.assertEqual(selected["reopenable_archived_total"], 1)
        self.assertTrue(selected["future_only"])
        self.assertEqual(selected["immediate_effect"], "future_only")

    def test_reopen_archived_learned_context_marks_review_required(self) -> None:
        self.store.save_learned_context_records(
            [
                {
                    "record_id": "lc-archived-reopen",
                    "summary": "Archived context to inspect.",
                    "details": "Needs review before trust.",
                    "fresh_until": "2026-03-01T12:00:00Z",
                    "status": "archived",
                    "verifier_status": "approved",
                    "archived_at": "2026-03-20T12:00:00Z",
                    "archive_reason": "stale_after_grace",
                }
            ]
        )

        payload = self.post_json("/api/learned-context/reopen", {"limit": 25, "now": FIXED_NOW})

        self.assertEqual(payload["result"]["reopened"], 1)
        [record] = self.store.load_learned_context_records()
        self.assertEqual(record["status"], "active")
        self.assertEqual(record["verifier_status"], "review_required")
        self.assertEqual(record["restored_from_status"], "archived")
        self.assertNotIn("archived_at", record)

    def test_retention_archive_sets_restore_window_for_future_recovery(self) -> None:
        self.store.save_learned_context_records(
            [
                {
                    "record_id": "lc-active-expired",
                    "summary": "Expired context.",
                    "details": "Should archive with a recovery window.",
                    "fresh_until": "2026-03-01T12:00:00Z",
                    "status": "active",
                    "verifier_status": "approved",
                }
            ]
        )

        result = archive_stale_learned_context(self.store, now=FIXED_NOW, grace_days=1)

        self.assertEqual(result["archived"], 1)
        [record] = self.store.load_learned_context_records()
        self.assertEqual(record["status"], "archived")
        self.assertEqual(record["restorable_until"], "2026-03-28T12:00:00Z")

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

    def test_dream_visualization_api_endpoints(self) -> None:
        summary_path = self.store.audit_semantic_dream_dir / "semantic-dream-viz-summary.json"
        write_json(
            summary_path,
            {
                "action": "semantic_dream",
                "run_id": "semantic-dream-viz",
                "workspace": str(self.workspace),
                "memory_root": str(self.store.memory_root),
                "target_paths": [],
                "summary": {
                    "run_id": "semantic-dream-viz",
                    "mode": "hybrid",
                    "status": "completed",
                    "started_at": FIXED_NOW,
                    "ended_at": FIXED_NOW,
                    "phases": ["orient", "gather_recent_signal", "synthesize", "promote"],
                    "duration_ms": 40,
                    "query_families_considered": 5,
                    "query_families_selected": 3,
                    "proposals_generated": 2,
                    "proposals_approved": 1,
                    "proposals_rejected": 1,
                    "learned_context_created": 1,
                    "signal_row_count": 8,
                    "latest_signal_source": "explicit_events",
                    "latest_signal_timestamp": FIXED_NOW,
                    "semantic_trace": {
                        "signal": {
                            "source": "explicit_events",
                            "latest_timestamp": FIXED_NOW,
                            "rows_scanned": 8,
                            "rows_gathered": 8,
                        },
                        "planner": {
                            "families_considered": 5,
                            "families_selected": 3,
                            "selected_family_ids": ["what-failed", "command-sequences"],
                        },
                        "synthesis": {
                            "proposal_count": 2,
                            "proposal_ids": ["proposal-1", "proposal-2"],
                            "drop_reasons": ["no-row-family-token-overlap"],
                            "fallback_reason": "",
                        },
                        "verification": {
                            "verdict_counts": {"approve": 1, "reject": 1},
                            "results": [],
                        },
                        "materialization": {
                            "created_count": 1,
                            "promoted_record_ids": ["lc-viz"],
                            "retention_status": "active",
                            "no_materialization_reason": "",
                        },
                    },
                    "narrative": (
                        "Hybrid dream reviewed 2 proposal(s), approved 1, "
                        "created 1 learned-context record(s), and rejected 1."
                    ),
                },
            },
        )
        index_observability(self.store, now=FIXED_NOW)

        cycles = self.get_json("/api/dream/cycles?limit=50")
        self.assertGreaterEqual(cycles["total"], 1)
        row = next(item for item in cycles["items"] if item["run_id"] == "semantic-dream-viz")
        self.assertEqual(row["funnel"]["generated"], 2)
        self.assertEqual(row["signal_source"], "explicit_events")
        self.assertEqual(row["latest_signal_timestamp"], FIXED_NOW)
        self.assertIn("narrative", row)
        self.assertEqual(row["trace_summary"]["rows_scanned"], 8)
        self.assertEqual(row["trace_summary"]["families_selected"], 3)
        self.assertEqual(row["trace_summary"]["verifier_verdicts"]["approve"], 1)
        self.assertEqual(row["trace_summary"]["learned_context_created"], 1)
        self.assertNotIn("semantic_trace", row)
        self.assertEqual(row["change_point"]["kind"], "material")
        self.assertGreaterEqual(row["change_point"]["score"], 80)
        self.assertNotIn("diff_text", row)

        detail = self.get_json("/api/dream/cycles/semantic-dream-viz")
        self.assertEqual(detail["phase_durations"]["orient"], 10)
        self.assertEqual(detail["change_point"], row["change_point"])
        self.assertIn("summary", detail)
        self.assertIn("semantic_trace", detail["summary"])

        funnel = self.get_json("/api/dream/funnel?window=9999d")
        self.assertGreaterEqual(funnel["funnel"]["created"], 1)

        coverage = self.get_json("/api/dream/coverage?window=9999d")
        self.assertTrue(coverage["items"])
        self.assertIn("explicit_events", coverage["items"][0])

        payload = read_json(summary_path, {})
        self.assertEqual(payload["summary"]["narrative"], row["narrative"])

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
            "/semantic-changes",
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
            self.assertIn("OpenDream Observe", html)

    def test_graph_js_includes_a11y_banner(self) -> None:
        graph_js = Path(__file__).resolve().parents[1] / "opendream" / "static" / "graph.js"
        text = graph_js.read_text(encoding="utf-8")
        self.assertIn("od-graph-a11y-banner", text)
        self.assertIn("od-graph-open-data", text)


if __name__ == "__main__":
    unittest.main()
