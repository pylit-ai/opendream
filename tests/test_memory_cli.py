from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from opendream import cli
from opendream.consolidator import consolidate
from opendream.models import ContextAssembly, MemoryRecord
from opendream.storage import DEFAULT_MEMORY_DIR, LEGACY_MEMORY_DIR, MemoryStore
from opendream.validation import validate_document

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = "2026-03-26T12:00:00Z"


def run_cli_raw(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "opendream.cli", *args],
        cwd=cwd or REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def run_cli(*args: str, cwd: Path | None = None) -> dict[str, object]:
    completed = run_cli_raw(*args, cwd=cwd, check=True)
    return json.loads(completed.stdout)


class MemoryCliIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.global_workspace = Path(self.temp_dir.name) / "global-store"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_manifest(self, *stores: tuple[Path, str]) -> Path:
        manifest_path = Path(self.temp_dir.name) / "stores.json"
        payload = {
            "stores": [
                {"workspace": str(workspace), "store_kind": store_kind}
                for workspace, store_kind in stores
            ]
        }
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        return manifest_path

    def write_opendream_shim(self) -> Path:
        bin_dir = Path(self.temp_dir.name) / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        shim_path = bin_dir / "opendream"
        shim_path.write_text(
            "\n".join(
                [
                    "#!/bin/sh",
                    f'exec "{sys.executable}" -m opendream.cli "$@"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        shim_path.chmod(0o755)
        return shim_path

    def write_automation_spec(self, payload: dict[str, object], name: str = "automation.json") -> Path:
        path = Path(self.temp_dir.name) / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def emit_runtime_event(
        self,
        workspace: Path,
        *,
        kind: str,
        content: str,
        message_ref: str,
        scope: str = "project",
        tag: str | None = None,
        route: str | None = None,
        global_workspace: Path | None = None,
        sensitivity: str | None = None,
    ) -> dict[str, object]:
        args = [
            "emit-event",
            "--workspace",
            str(workspace),
            "--kind",
            kind,
            "--content",
            content,
            "--message-ref",
            message_ref,
            "--scope",
            scope,
            "--timestamp",
            FIXED_NOW,
        ]
        if tag:
            args.extend(["--tag", tag])
        if route:
            args.extend(["--route", route])
        if global_workspace:
            args.extend(["--global-workspace", str(global_workspace)])
        if sensitivity:
            args.extend(["--sensitivity", sensitivity])
        return run_cli(*args)

    def write_learned_context_records(self, workspace: Path, *records: dict[str, object]) -> None:
        store = MemoryStore(workspace)
        existing = store.load_learned_context_records()
        store.save_learned_context_records([*existing, *records])

    def learned_context_record(
        self,
        record_id: str,
        *,
        summary: str = "Use the ledger-backed resolver for ticket verification.",
        details: str = "Ticket files and verification surface should be inspected together.",
        fresh_until: str = "2999-01-01T00:00:00Z",
        status: str = "active",
        verifier_status: str = "approved",
        conflict_state: str = "none",
    ) -> dict[str, object]:
        return {
            "record_id": record_id,
            "workspace_id": "workspace",
            "source_event_ids": [f"event-{record_id}"],
            "query_family_tags": ["ticket-verification"],
            "summary": summary,
            "details": details,
            "assumptions": "Applies to local repository verification only.",
            "provider_id": "heuristic",
            "model_id": "deterministic",
            "prompt_version": "v1",
            "created_at": FIXED_NOW,
            "fresh_until": fresh_until,
            "confidence": 0.8,
            "verifier_status": verifier_status,
            "conflict_state": conflict_state,
            "promotion_target": "learned_context",
            "status": status,
        }

    def test_demo_creates_reproducible_artifacts(self) -> None:
        result = run_cli("demo", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        memory_root = self.workspace / DEFAULT_MEMORY_DIR
        self.assertTrue((memory_root / "MEMORY.md").exists())
        self.assertTrue((memory_root / "state" / "durable_records.json").exists())
        self.assertTrue(any((memory_root / "topics").glob("*.md")))
        self.assertTrue(any((memory_root / "audit" / "consolidation").glob("*.diff")))
        self.assertGreater(result["extract"]["created_candidates"], 0)
        self.assertGreater(len(result["retrieve"]["selected_memory_ids"]), 0)

    def test_showcase_fixture_validates_coding_agent_story(self) -> None:
        fixture = REPO_ROOT / "opendream" / "fixtures" / "showcase_coding_agent_memory.jsonl"
        events = [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines() if line]
        self.assertGreaterEqual(len(events), 8)
        for event in events:
            validate_document("memory-event.schema.json", event)
        contents = "\n".join(event["content"] for event in events)
        self.assertIn("pnpm", contents)
        self.assertIn("Redis", contents)
        self.assertIn("anti-pattern", contents)
        self.assertIn("correction", contents.lower())
        self.assertIn("GraphQL", contents)

    def test_showcase_demo_creates_before_after_proof_report(self) -> None:
        result = run_cli(
            "demo",
            "--scenario",
            "coding-agent-showcase",
            "--workspace",
            str(self.workspace),
            "--now",
            FIXED_NOW,
        )
        self.assertEqual(result["scenario"], "coding-agent-showcase")
        self.assertIn("useful prompt context", result["objective"]["title"])
        self.assertIn("OpenDream Memory Context", result["context"]["prompt_context"] or "")
        self.assertIn("OpenDream Observe UI", result["evaluation_case"]["user_prompt"])
        self.assertEqual(result["before"]["selected_memory_ids"], [])
        self.assertTrue(result["after"]["selected_memory_ids"])
        self.assertIn("OpenDream found prior memory:", result["agent_snippet"])
        self.assertEqual(result["selected_memory_ids"], result["after"]["selected_memory_ids"])
        self.assertEqual(len(result["context"]["links"]), len(result["selected_memory_ids"]))
        agent_answers = result["agent_answers"]
        stateless = agent_answers["stateless"]
        memory_assisted = agent_answers["memory_assisted"]
        self.assertEqual(stateless["selected_memory_ids"], [])
        self.assertEqual(memory_assisted["selected_memory_ids"], result["selected_memory_ids"])
        self.assertFalse(stateless["measurement"]["passed"])
        self.assertTrue(memory_assisted["measurement"]["passed"])
        self.assertGreater(
            memory_assisted["measurement"]["score"],
            stateless["measurement"]["score"],
        )
        self.assertTrue(agent_answers["comparison"]["passed"])
        self.assertIn("pnpm", memory_assisted["answer"])
        self.assertIn("Redis", memory_assisted["answer"])
        self.assertIn("opendream/static/dist", memory_assisted["answer"])
        self.assertIn("memory-showcase", memory_assisted["answer"])
        self.assertTrue(result["retrieval_rationale"])
        prompt_context = result["context"]["prompt_context"]
        self.assertNotIn("GraphQL billing API", prompt_context)
        visibility = result["context"]["visibility"]
        self.assertEqual(
            set(visibility),
            {"selected", "excluded", "diagnostic-only", "startup-index-only"},
        )
        self.assertGreaterEqual(visibility["excluded"]["count"], 1)
        self.assertTrue(result["dream_effectiveness"]["effective"]["baseline_to_after"])
        self.assertTrue(result["dream_effectiveness"]["effective"]["stale_guidance_contested"])
        self.assertTrue(result["dream_effectiveness"]["effective"]["decoy_excluded"])
        self.assertTrue(result["dream_effectiveness"]["effective"]["negative_controls_passed"])
        self.assertTrue(result["dream_effectiveness"]["effective"]["abstention_cases_passed"])
        self.assertTrue(result["dream_effectiveness"]["effective"]["memory_hurt_case_passed"])
        self.assertTrue(result["dream_effectiveness"]["effective"]["curated_actionable_prompt_context_built"])
        self.assertTrue(result["dream_effectiveness"]["effective"]["memory_assisted_answer_improved"])
        self.assertGreater(result["dream_effectiveness"]["metrics"]["answer_score_delta"], 0)
        self.assertNotIn("compact_context_built", result["dream_effectiveness"]["effective"])
        self.assertTrue(result["checks"]["answer_improvement"]["passed"])
        self.assertTrue(result["checks"]["negative_controls"]["passed"])
        self.assertTrue(result["checks"]["abstention"]["passed"])
        self.assertTrue(result["checks"]["memory_hurt"]["passed"])
        self.assertGreaterEqual(len(result["negative_controls"]), 3)
        self.assertTrue(all(case["passed"] for case in result["negative_controls"]))
        self.assertEqual(len(result["abstention_cases"]), 2)
        self.assertTrue(all(case["abstained"] for case in result["abstention_cases"]))
        self.assertTrue(any(case["gated"] for case in result["abstention_cases"]))
        self.assertEqual(len(result["memory_hurt_cases"]), 1)
        self.assertTrue(result["memory_hurt_cases"][0]["harm_prevented_by_default"])
        self.assertTrue(result["memory_hurt_cases"][0]["forced_memory_hurt"]["contradicted_recalled"])
        self.assertTrue(result["proof"]["source_refs"])
        summaries = "\n".join(ref["summary"] for ref in result["proof"]["source_refs"])
        self.assertIn("pnpm", summaries)
        self.assertNotIn("GraphQL billing API", summaries)
        self.assertIn(
            "excluded from selected durable memory",
            "\n".join(result["dream_effectiveness"]["why_it_matters"]),
        )
        report_path = Path(result["report_path"])
        self.assertTrue(report_path.exists())
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["agent_snippet"], result["agent_snippet"])
        self.assertEqual(report["agent_answers"], result["agent_answers"])

    def test_no_subcommand_error_includes_next_step_hint(self) -> None:
        completed = run_cli_raw(check=False)
        self.assertEqual(completed.returncode, 2)
        self.assertIn('opendream init --workspace "$PWD" --activate-configured', completed.stderr)
        self.assertIn('opendream status --workspace "$PWD"', completed.stderr)

    def test_bootstrap_index_stages_without_topic_writes(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "bootstrap_events.jsonl"
        result = run_cli(
            "bootstrap-index",
            "--workspace",
            str(self.workspace),
            "--events",
            str(fixture),
            "--now",
            FIXED_NOW,
        )
        self.assertGreaterEqual(result["categories"], 4)
        self.assertEqual(len(list((self.workspace / DEFAULT_MEMORY_DIR / "topics").glob("*.md"))), 0)
        reports = list((self.workspace / DEFAULT_MEMORY_DIR / "audit" / "bootstrap").glob("*.json"))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(report["raw_only_ids"]), 1)
        self.assertGreaterEqual(len(report["quarantine_ids"]), 1)

    def test_init_persists_store_kind_metadata(self) -> None:
        project_result = run_cli("init", "--workspace", str(self.workspace))
        global_result = run_cli("init", "--workspace", str(self.global_workspace), "--store-kind", "global")

        project_store = json.loads(
            (self.workspace / DEFAULT_MEMORY_DIR / "state" / "store.json").read_text(encoding="utf-8")
        )
        global_store = json.loads(
            (self.global_workspace / DEFAULT_MEMORY_DIR / "state" / "store.json").read_text(encoding="utf-8")
        )

        self.assertEqual(project_result["store_kind"], "project")
        self.assertEqual(global_result["store_kind"], "global")
        self.assertEqual(project_store["store_kind"], "project")
        self.assertEqual(global_store["store_kind"], "global")

    def test_command_observe_serve_handles_keyboard_interrupt_cleanly(self) -> None:
        args = argparse.Namespace(
            workspace=str(self.workspace),
            memory_dir=None,
            compat_mode=False,
            now=None,
            host="127.0.0.1",
            port=0,
        )

        class _InterruptingServer:
            server_address = ("127.0.0.1", 8771)

            def serve_forever(self) -> None:
                raise KeyboardInterrupt

            def server_close(self) -> None:
                self.closed = True

        server = _InterruptingServer()
        with (
            patch("opendream.cli.build_server", return_value=server),
            patch("opendream.cli.index_observability"),
            patch("builtins.print"),
        ):
            result = cli.command_observe_serve(args)

        self.assertEqual(result, {"status": "stopped", "host": "127.0.0.1", "port": 8771})
        self.assertTrue(getattr(server, "closed", False))

    def test_emit_event_records_reporting_agent_with_unknown_default(self) -> None:
        run_cli(
            "emit-event",
            "--workspace",
            str(self.workspace),
            "--kind",
            "project_decision",
            "--content",
            "Agent metadata should be explicit.",
            "--message-ref",
            "agent-msg-1",
            "--timestamp",
            FIXED_NOW,
        )

        event_path = next((self.workspace / DEFAULT_MEMORY_DIR / "state" / "events").glob("*.jsonl"))
        event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(event["reporting_agent"]["agent_id"], "unknown")
        self.assertEqual(event["reporting_agent"]["agent_label"], "Unknown")
        validate_document("memory-event.schema.json", event)

    def test_emit_event_records_explicit_reporting_agent(self) -> None:
        run_cli(
            "emit-event",
            "--workspace",
            str(self.workspace),
            "--kind",
            "project_decision",
            "--content",
            "Codex reported this decision.",
            "--message-ref",
            "agent-msg-2",
            "--timestamp",
            FIXED_NOW,
            "--agent-id",
            "codex",
            "--agent-label",
            "Codex",
            "--agent-runtime",
            "codex-cli",
            "--agent-adapter-id",
            "codex-account",
            "--agent-model-id",
            "gpt-5.4",
            "--agent-model-version",
            "2026-04-17",
        )

        event_path = next((self.workspace / DEFAULT_MEMORY_DIR / "state" / "events").glob("*.jsonl"))
        event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(
            event["reporting_agent"],
            {
                "agent_id": "codex",
                "agent_label": "Codex",
                "runtime": "codex-cli",
                "adapter_id": "codex-account",
                "model_id": "gpt-5.4",
                "model_version": "2026-04-17",
            },
        )
        validate_document("memory-event.schema.json", event)

    def test_deterministic_consolidation_and_schema_validation(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
        run_cli("append-event", "--workspace", str(self.workspace), "--events", str(fixture))
        run_cli("extract", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        first = run_cli("consolidate", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        durable_before = (
            self.workspace / DEFAULT_MEMORY_DIR / "state" / "durable_records.json"
        ).read_text(encoding="utf-8")
        index_before = (self.workspace / DEFAULT_MEMORY_DIR / "MEMORY.md").read_text(encoding="utf-8")
        second = run_cli("consolidate", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        durable_after = (
            self.workspace / DEFAULT_MEMORY_DIR / "state" / "durable_records.json"
        ).read_text(encoding="utf-8")
        index_after = (self.workspace / DEFAULT_MEMORY_DIR / "MEMORY.md").read_text(encoding="utf-8")

        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["created"], 0)
        self.assertEqual(durable_before, durable_after)
        self.assertEqual(index_before, index_after)

        records = json.loads(durable_after)
        for record in records:
            validate_document("memory-topic.schema.json", record)
        workflow = next(record for record in records if record["title"] == "Workflow: schema-migration")
        self.assertEqual(workflow["type"], "workflow")
        self.assertEqual(workflow["lifecycle"]["state"], "active")
        self.assertEqual(workflow["lifecycle"]["source_event_count"], 4)
        self.assertEqual(workflow["lifecycle"]["promotion_run_id"], first["run_id"])
        index = json.loads((self.workspace / DEFAULT_MEMORY_DIR / "state" / "index.json").read_text(encoding="utf-8"))
        validate_document("memory-index.schema.json", index)
        audit_file = next((self.workspace / DEFAULT_MEMORY_DIR / "audit" / "consolidation").glob("*.jsonl"))
        for line in audit_file.read_text(encoding="utf-8").splitlines():
            validate_document("consolidation-op.schema.json", json.loads(line))

    def test_retrieve_returns_relevant_memory(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
        run_cli("append-event", "--workspace", str(self.workspace), "--events", str(fixture))
        run_cli("extract", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        run_cli("consolidate", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        retrieval = run_cli(
            "retrieve",
            "--workspace",
            str(self.workspace),
            "--query",
            "Which package manager, Redis setup, and schema migration workflow should I use?",
            "--now",
            FIXED_NOW,
        )
        records = {
            record["memory_id"]: record
            for record in json.loads(
                (self.workspace / DEFAULT_MEMORY_DIR / "state" / "durable_records.json").read_text(encoding="utf-8")
            )
        }
        selected_titles = {records[memory_id]["title"] for memory_id in retrieval["selected_memory_ids"]}
        self.assertIn("Preference: package-manager", selected_titles)
        self.assertIn("Environment: redis", selected_titles)
        self.assertIn("Workflow: schema-migration", selected_titles)
        self.assertTrue(any((self.workspace / DEFAULT_MEMORY_DIR / "audit" / "retrieval").glob("*.json")))

    def test_single_writer_lock_exits_cleanly(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
        run_cli("append-event", "--workspace", str(self.workspace), "--events", str(fixture))
        run_cli("extract", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        store = MemoryStore(self.workspace)
        results: list[dict[str, object]] = []

        def worker(delay: float) -> None:
            results.append(consolidate(store, now=FIXED_NOW, sleep_before_write=delay))

        thread_one = threading.Thread(target=worker, args=(0.2,))
        thread_two = threading.Thread(target=worker, args=(0.0,))
        thread_one.start()
        thread_two.start()
        thread_one.join()
        thread_two.join()

        skipped = [result for result in results if result["status"] == "skipped"]
        completed = [result for result in results if result["status"] == "completed"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(len(completed), 1)
        self.assertFalse((self.workspace / DEFAULT_MEMORY_DIR / "locks" / "consolidator.lock").exists())

    def test_memory_commands_write_only_inside_memory_store(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
        run_cli("append-event", "--workspace", str(self.workspace), "--events", str(fixture))
        run_cli("extract", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        run_cli("consolidate", "--workspace", str(self.workspace), "--now", FIXED_NOW)

        mem_root = (self.workspace / DEFAULT_MEMORY_DIR).resolve()
        non_memory_files: list[Path] = []
        for path in self.workspace.rglob("*"):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved == mem_root or mem_root in resolved.parents:
                continue
            non_memory_files.append(path)
        self.assertEqual(non_memory_files, [])

    def test_emit_event_appends_schema_valid_event(self) -> None:
        result = run_cli(
            "emit-event",
            "--workspace",
            str(self.workspace),
            "--kind",
            "project_decision",
            "--content",
            "Use the local-first memory runtime.",
            "--message-ref",
            "runtime-msg-1",
            "--tag",
            "key:runtime",
            "--confidence-hint",
            "0.9",
            "--timestamp",
            FIXED_NOW,
        )
        self.assertEqual(result["status"], "appended")
        event_files = list((self.workspace / DEFAULT_MEMORY_DIR / "state" / "events").glob("*.jsonl"))
        self.assertEqual(len(event_files), 1)
        event = json.loads(event_files[0].read_text(encoding="utf-8").splitlines()[0])
        validate_document("memory-event.schema.json", event)
        self.assertEqual(event["kind"], "project_decision")
        summary_path = self.workspace / result["audit"]["summary_path"]
        diff_path = self.workspace / result["audit"]["diff_path"]
        self.assertTrue(summary_path.exists())
        self.assertTrue(diff_path.exists())

    def test_custom_memory_dir_is_honored_for_direct_writes(self) -> None:
        result = run_cli(
            "emit-event",
            "--workspace",
            str(self.workspace),
            "--memory-dir",
            ".dream-memory",
            "--kind",
            "project_decision",
            "--content",
            "Use the dedicated custom memory directory.",
            "--message-ref",
            "runtime-msg-custom-dir",
            "--timestamp",
            FIXED_NOW,
        )
        self.assertEqual(result["status"], "appended")
        self.assertTrue((self.workspace / ".dream-memory" / "state" / "events").exists())
        self.assertFalse((self.workspace / DEFAULT_MEMORY_DIR).exists())
        self.assertFalse((self.workspace / LEGACY_MEMORY_DIR).exists())

    def test_emit_event_can_route_to_global_store(self) -> None:
        run_cli("init", "--workspace", str(self.global_workspace), "--store-kind", "global")
        result = self.emit_runtime_event(
            self.workspace,
            kind="preference_signal",
            content="Prefer concise commit messages across repos.",
            message_ref="global-msg-1",
            scope="global",
            tag="key:commit-style",
            route="global",
            global_workspace=self.global_workspace,
        )
        self.assertEqual(result["store_kind"], "global")
        self.assertFalse((self.workspace / DEFAULT_MEMORY_DIR / "state" / "events").exists())
        event_files = list((self.global_workspace / DEFAULT_MEMORY_DIR / "state" / "events").glob("*.jsonl"))
        self.assertEqual(len(event_files), 1)

    def test_emit_event_rejects_sensitive_global_routing(self) -> None:
        run_cli("init", "--workspace", str(self.global_workspace), "--store-kind", "global")
        with self.assertRaises(subprocess.CalledProcessError):
            run_cli_raw(
                "emit-event",
                "--workspace",
                str(self.workspace),
                "--global-workspace",
                str(self.global_workspace),
                "--route",
                "global",
                "--scope",
                "global",
                "--kind",
                "preference_signal",
                "--content",
                "Store my secret API key.",
                "--message-ref",
                "global-msg-2",
                "--sensitivity",
                "sensitive",
                "--timestamp",
                FIXED_NOW,
                check=True,
            )

    def test_maintain_runs_then_skips_on_min_interval(self) -> None:
        self.emit_runtime_event(
            self.workspace,
            kind="project_decision",
            content="Use the local-first memory runtime.",
            message_ref="runtime-msg-2",
            tag="key:runtime",
        )
        first = run_cli(
            "maintain",
            "--workspace",
            str(self.workspace),
            "--now",
            FIXED_NOW,
            "--min-interval-seconds",
            "60",
        )
        second = run_cli(
            "maintain",
            "--workspace",
            str(self.workspace),
            "--now",
            "2026-03-26T12:00:10Z",
            "--min-interval-seconds",
            "60",
        )
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["extract"]["processed_events"], 1)
        self.assertEqual(second["status"], "skipped")
        self.assertEqual(second["reason"], "min-interval")

    def test_maintain_archives_stale_learned_context_after_grace(self) -> None:
        self.write_learned_context_records(
            self.workspace,
            self.learned_context_record("lc-fresh", fresh_until="2999-01-01T00:00:00Z"),
            self.learned_context_record(
                "lc-stale-within-grace",
                fresh_until="2026-03-24T12:00:00Z",
            ),
            self.learned_context_record(
                "lc-stale-after-grace",
                fresh_until="2026-03-01T12:00:00Z",
            ),
        )

        result = run_cli("maintain", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        records = {
            record["record_id"]: record
            for record in MemoryStore(self.workspace).load_learned_context_records()
        }

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["learned_context_lifecycle"]["archived"], 1)
        self.assertEqual(records["lc-fresh"]["status"], "active")
        self.assertEqual(records["lc-stale-within-grace"]["status"], "active")
        self.assertEqual(records["lc-stale-after-grace"]["status"], "archived")
        self.assertEqual(records["lc-stale-after-grace"]["archive_reason"], "stale_after_grace")
        self.assertEqual(records["lc-stale-after-grace"]["archived_at"], FIXED_NOW)

    def test_maintain_uses_semantic_config_for_learned_context_archive_grace(self) -> None:
        store = MemoryStore(self.workspace)
        store.save_semantic_config(
            {
                **store.load_semantic_config(),
                "retention": {"learned_context_archive_grace_days": 1},
            }
        )
        self.write_learned_context_records(
            self.workspace,
            self.learned_context_record(
                "lc-stale-after-one-day",
                fresh_until="2026-03-24T12:00:00Z",
            ),
        )

        result = run_cli("maintain", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        records = {
            record["record_id"]: record
            for record in MemoryStore(self.workspace).load_learned_context_records()
        }

        self.assertEqual(result["learned_context_lifecycle"]["grace_days"], 1)
        self.assertEqual(result["learned_context_lifecycle"]["archived"], 1)
        self.assertEqual(records["lc-stale-after-one-day"]["status"], "archived")

    def test_maintain_can_gate_learned_context_archive_on_context_activity(self) -> None:
        store = MemoryStore(self.workspace)
        store.save_semantic_config(
            {
                **store.load_semantic_config(),
                "retention": {
                    "learned_context_archive_grace_days": 1,
                    "learned_context_archive_grace_contexts": 2,
                },
            }
        )
        self.write_learned_context_records(
            self.workspace,
            self.learned_context_record(
                "lc-activity-gated",
                fresh_until="2026-03-24T12:00:00Z",
            ),
        )

        first = run_cli("maintain", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        records = {
            record["record_id"]: record
            for record in MemoryStore(self.workspace).load_learned_context_records()
        }
        self.assertEqual(first["learned_context_lifecycle"]["archived"], 0)
        self.assertEqual(records["lc-activity-gated"]["status"], "active")

        for idx, created_at in enumerate(["2026-03-25T12:00:01Z", "2026-03-25T12:00:02Z"]):
            store.write_context_assembly(
                ContextAssembly(
                    context_id=f"context-activity-{idx}",
                    session_id="session-activity",
                    turn_id=f"turn-activity-{idx}",
                    retrieval_run_id=f"retrieve-activity-{idx}",
                    startup_index_snapshot=[],
                    selected_memory_ids=[],
                    omitted_memory_ids=[],
                    omission_reasons=[],
                    assembled_text="# OpenDream Memory Context\nQuery: activity gate",
                    character_count=43,
                    token_estimate=6,
                    created_at=created_at,
                )
            )

        second = run_cli("maintain", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        records = {
            record["record_id"]: record
            for record in MemoryStore(self.workspace).load_learned_context_records()
        }
        self.assertEqual(second["learned_context_lifecycle"]["grace_contexts"], 2)
        self.assertEqual(second["learned_context_lifecycle"]["archived"], 1)
        self.assertEqual(records["lc-activity-gated"]["status"], "archived")

    def test_semantic_status_reports_prompt_eligible_stale_active_and_archived_counts(self) -> None:
        self.write_learned_context_records(
            self.workspace,
            self.learned_context_record("lc-prompt-eligible", fresh_until="2999-01-01T00:00:00Z"),
            self.learned_context_record("lc-stale-active", fresh_until="2000-01-01T00:00:00Z"),
            self.learned_context_record(
                "lc-archived",
                fresh_until="2000-01-01T00:00:00Z",
                status="archived",
            ),
            self.learned_context_record(
                "lc-verifier-pending",
                fresh_until="2999-01-01T00:00:00Z",
                verifier_status="pending",
            ),
        )

        status = run_cli("semantic", "status", "--workspace", str(self.workspace))
        learned = status["learned_context"]

        self.assertEqual(learned["active"], 3)
        self.assertEqual(learned["prompt_eligible"], 1)
        self.assertEqual(learned["stale_active"], 1)
        self.assertEqual(learned["archived"], 1)

    def test_prepare_context_returns_prompt_ready_memory(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
        run_cli("append-event", "--workspace", str(self.workspace), "--events", str(fixture))
        run_cli("maintain", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        context = run_cli(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "package manager and workflow",
            "--now",
            FIXED_NOW,
        )
        self.assertIn("OpenDream Memory Context", context["prompt_context"])
        self.assertIn("## Startup Index", context["prompt_context"])
        self.assertIn("Selected Durable Memory", context["prompt_context"])
        self.assertTrue(context["selected_memory_ids"])
        visibility = context["prompt_context_visibility"]
        self.assertEqual(
            set(visibility),
            {"selected", "excluded", "diagnostic-only", "startup-index-only"},
        )
        self.assertEqual(visibility["selected"]["count"], len(context["selected_memory_ids"]))
        self.assertIsNone(context.get("empty_reason"))
        self.assertEqual(context.get("hints"), [])

    def test_prepare_context_output_modes_preserve_full_audit_and_compact_prompt(self) -> None:
        self.write_learned_context_records(
            self.workspace,
            self.learned_context_record("lc-output-mode"),
            self.learned_context_record(
                "lc-output-budget",
                summary="Budget-only record",
                details="Another matching ticket verification record.",
            ),
        )

        full = run_cli(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "ticket verification resolver",
            "--now",
            FIXED_NOW,
            "--output",
            "full-json",
        )
        compact = run_cli(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "ticket verification resolver",
            "--now",
            FIXED_NOW,
            "--output",
            "compact-json",
        )
        prompt = run_cli_raw(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "ticket verification resolver",
            "--now",
            FIXED_NOW,
            "--output",
            "prompt",
        )

        self.assertIn("suppressed", full)
        self.assertIn("selected_learned_context_records", full)
        self.assertIn("prompt_context", compact)
        self.assertIn("context_pruning", compact)
        self.assertIn("prompt_context_visibility", compact)
        self.assertIn("audit", compact)
        self.assertNotIn("suppressed", compact)
        self.assertNotIn("omitted", compact)
        self.assertNotIn("selected_memories", compact)
        self.assertNotIn("selected_learned_context_records", compact)
        self.assertIn("OpenDream Memory Context", prompt.stdout)
        self.assertNotIn('"prompt_context"', prompt.stdout)

    def test_prepare_context_compact_output_stays_bounded_with_many_suppressed_records(self) -> None:
        self.write_learned_context_records(
            self.workspace,
            *[
                self.learned_context_record(
                    f"lc-suppressed-{idx:03d}",
                    summary=f"Stale ticket verification record {idx}",
                    details="Ticket verification stale record " * 8,
                    fresh_until="2000-01-01T00:00:00Z",
                )
                for idx in range(400)
            ],
        )

        full = run_cli_raw(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "ticket verification resolver",
            "--now",
            FIXED_NOW,
            "--output",
            "full-json",
        )
        compact = run_cli_raw(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "ticket verification resolver",
            "--now",
            FIXED_NOW,
            "--output",
            "compact-json",
        )
        compact_payload = json.loads(compact.stdout)

        self.assertGreater(len(full.stdout), 32768)
        self.assertLess(len(compact.stdout.encode("utf-8")), 32768)
        self.assertEqual(compact_payload["context_pruning"]["suppressed_count"], 400)
        self.assertEqual(compact_payload["suppression_summary"]["stale_learned_context"], 400)
        self.assertNotIn("suppressed", compact_payload)

    def test_prepare_context_compact_output_warns_when_prompt_exceeds_hook_budget(self) -> None:
        self.write_learned_context_records(
            self.workspace,
            self.learned_context_record(
                "lc-large-selected",
                summary="Ticket verification resolver budget warning",
                details="ticket verification resolver " * 2500,
            ),
        )

        compact = run_cli(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "ticket verification resolver",
            "--now",
            FIXED_NOW,
            "--output",
            "compact-json",
        )

        self.assertGreater(len(json.dumps(compact).encode("utf-8")), 32768)
        self.assertEqual(compact["warnings"][0]["code"], "compact_context_budget_exceeded")

    def test_prepare_context_records_reporting_agent_and_model(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
        run_cli("append-event", "--workspace", str(self.workspace), "--events", str(fixture))
        run_cli("maintain", "--workspace", str(self.workspace), "--now", FIXED_NOW)

        context = run_cli(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "package manager and workflow",
            "--now",
            FIXED_NOW,
            "--agent-id",
            "codex",
            "--agent-label",
            "Codex",
            "--agent-runtime",
            "codex-cli",
            "--agent-model-id",
            "gpt-5.4",
            "--agent-model-version",
            "2026-04-17",
        )

        self.assertTrue(context["context_id"])
        assembly_path = (
            self.workspace
            / DEFAULT_MEMORY_DIR
            / "audit"
            / "context"
            / f"{context['context_id']}.json"
        )
        assembly = json.loads(assembly_path.read_text(encoding="utf-8"))
        retrieval_run_id = str(assembly["retrieval_run_id"]).split(",")[0]
        retrieval_path = self.workspace / DEFAULT_MEMORY_DIR / "audit" / "retrieval" / f"{retrieval_run_id}.json"
        retrieval = json.loads(retrieval_path.read_text(encoding="utf-8"))
        self.assertEqual(retrieval["reporting_agent"]["agent_id"], "codex")
        self.assertEqual(retrieval["reporting_agent"]["agent_label"], "Codex")
        self.assertEqual(retrieval["reporting_agent"]["model_id"], "gpt-5.4")
        self.assertEqual(retrieval["reporting_agent"]["model_version"], "2026-04-17")

    def test_prepare_context_reports_empty_reason_when_no_durable_memories(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        context = run_cli(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "anything",
            "--now",
            FIXED_NOW,
        )
        self.assertEqual(context.get("empty_reason"), "no_durable_memories")
        self.assertIsInstance(context.get("hints"), list)
        self.assertTrue(any("maintain" in hint for hint in context["hints"]))

    def test_status_includes_memory_layout(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        payload = run_cli("status", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        self.assertIn("memory_layout", payload)
        self.assertEqual(payload["memory_layout"]["active_memory_root"], DEFAULT_MEMORY_DIR)
        self.assertEqual(payload["memory_layout"]["memory_dir_name"], DEFAULT_MEMORY_DIR)

    def test_default_memory_dir_without_existing_store(self) -> None:
        store = MemoryStore(self.workspace)
        self.assertEqual(store.memory_dir_name, DEFAULT_MEMORY_DIR)

    def test_legacy_memory_dir_when_only_root_store_json_exists(self) -> None:
        legacy = self.workspace / LEGACY_MEMORY_DIR
        (legacy / "state").mkdir(parents=True)
        (legacy / "state" / "store.json").write_text(
            json.dumps({"layout": {"memory_dir": LEGACY_MEMORY_DIR, "compat_mode": "canonical"}}),
            encoding="utf-8",
        )
        store = MemoryStore(self.workspace)
        self.assertEqual(store.memory_dir_name, LEGACY_MEMORY_DIR)

    def test_doctor_memory_surface_reports_layout(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        out = run_cli("doctor", "--workspace", str(self.workspace), "--surface", "memory")
        self.assertEqual(out["surface"], "memory")
        self.assertEqual(out["status"], "healthy")
        self.assertIn("cli_output_version", out)
        self.assertIn("memory_layout", out)
        self.assertIn("durable_record_count", out)

    def test_dream_worker_includes_agent_summary_when_no_episodes(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        out = run_cli("dream", "worker", "--workspace", str(self.workspace), "--once", "--now", FIXED_NOW)
        self.assertIn("agent_summary", out)
        self.assertIn("cli_output_version", out)
        self.assertIn("transcript", out["agent_summary"].lower())

    def test_dream_worker_auto_mode_materializes_semantic_learning_from_events(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        store = MemoryStore(self.workspace)
        store.save_semantic_config(
            {
                **store.load_semantic_config(),
                "mode": "semantic",
                "execution_strategy": "direct-provider",
                "preferred_auth_mode": "direct-provider",
                "candidate_strategies": ["direct-provider", "deterministic"],
            }
        )
        store.save_provider_registry(
            [
                {
                    "provider_id": "openai-primary",
                    "transport": "openai",
                    "model_id": "gpt-5.4",
                    "roles": ["synthesis", "verification"],
                    "health_status": "healthy",
                }
            ]
        )
        self.emit_runtime_event(
            self.workspace,
            kind="task_outcome",
            content=(
                "Workflow to reproduce the failure: run pytest tests/test_worker.py "
                "because Redis is required locally."
            ),
            message_ref="semantic-worker-1",
        )
        self.emit_runtime_event(
            self.workspace,
            kind="task_outcome",
            content=(
                "The tests failed because the local Redis service was missing; "
                "the working command sequence is docker compose up redis then pytest."
            ),
            message_ref="semantic-worker-2",
        )

        out = run_cli(
            "dream",
            "worker",
            "--workspace",
            str(self.workspace),
            "--once",
            "--mode",
            "auto",
            "--now",
            FIXED_NOW,
        )

        self.assertEqual(out["status"], "completed")
        self.assertTrue(out["backlog_results"])
        backlog = out["backlog_results"][0]
        self.assertEqual(backlog["status"], "completed")
        self.assertEqual(backlog["mode"], "semantic")

        semantic_status = run_cli("semantic", "status", "--workspace", str(self.workspace))
        self.assertEqual(semantic_status["semantic_capability_state"], "ready")
        self.assertGreaterEqual(semantic_status["learned_context"]["active"], 1)
        self.assertEqual(semantic_status["last_semantic_run"], "semantic")

    def test_dream_worker_looping_mode_recovers_after_transient_lock_contention(self) -> None:
        from opendream.dream import dream_worker

        run_cli("init", "--workspace", str(self.workspace))
        store = MemoryStore(self.workspace)
        result_holder: dict[str, object] = {}

        def _run_worker() -> None:
            result_holder["result"] = dream_worker(
                store,
                now=FIXED_NOW,
                interval_seconds=0.05,
                max_polls=2,
                idle_exit=False,
                mode="auto",
            )

        with store.dream_worker_lock():
            thread = threading.Thread(target=_run_worker)
            thread.start()
            time.sleep(0.02)

        thread.join(timeout=2)
        self.assertIn("result", result_holder)
        result = result_holder["result"]
        self.assertEqual(result["status"], "completed")
        self.assertGreaterEqual(result["lock_failures"], 1)
        self.assertEqual(store.load_dream_worker_state()["last_result"], "skipped")
        self.assertIn(
            "worker-lock-held",
            [item["reason"] for item in store.load_worker_health().get("recent_failures", [])],
        )

    def test_service_status_hides_stale_lock_contention_after_later_success(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        store = MemoryStore(self.workspace)
        store.save_worker_health(
            {
                "pid": 1234,
                "started_at": "2026-04-20T10:00:00Z",
                "last_loop_at": "2026-04-20T10:10:00Z",
                "last_success_at": "2026-04-20T12:00:00Z",
                "queue_backlog": 0,
                "active_job_id": None,
                "active_phase": None,
                "restart_count": 0,
                "recent_failures": [
                    {"at": "2026-04-20T10:05:00Z", "reason": "worker-lock-held"},
                    {"at": "2026-04-20T11:50:00Z", "reason": "provider-timeout"},
                ],
                "state": "idle",
                "service_name": None,
                "supervisor_kind": None,
            }
        )

        status = run_cli("service", "status", "--workspace", str(self.workspace))

        self.assertEqual(
            [item["reason"] for item in status["recent_failures"]],
            ["provider-timeout"],
        )
        self.assertEqual(
            [item["reason"] for item in status["worker_health"]["recent_failures"]],
            ["provider-timeout"],
        )

    def test_service_status_hides_lock_contention_immediately_after_later_success(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        store = MemoryStore(self.workspace)
        store.save_worker_health(
            {
                "pid": 1234,
                "started_at": "2026-04-20T10:00:00Z",
                "last_loop_at": "2026-04-20T10:10:00Z",
                "last_success_at": "2026-04-20T10:06:00Z",
                "queue_backlog": 0,
                "active_job_id": None,
                "active_phase": None,
                "restart_count": 0,
                "recent_failures": [
                    {"at": "2026-04-20T10:05:00Z", "reason": "worker-lock-held"},
                    {"at": "2026-04-20T10:05:30Z", "reason": "provider-timeout"},
                ],
                "state": "idle",
                "service_name": None,
                "supervisor_kind": None,
            }
        )

        status = run_cli("service", "status", "--workspace", str(self.workspace))

        self.assertEqual(
            [item["reason"] for item in status["recent_failures"]],
            ["provider-timeout"],
        )

    def test_status_hides_stale_lock_contention_after_later_success(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        store = MemoryStore(self.workspace)
        store.save_worker_health(
            {
                "pid": 1234,
                "started_at": "2026-04-20T10:00:00Z",
                "last_loop_at": "2026-04-20T10:10:00Z",
                "last_success_at": "2026-04-20T12:00:00Z",
                "queue_backlog": 0,
                "active_job_id": None,
                "active_phase": None,
                "restart_count": 0,
                "recent_failures": [
                    {"at": "2026-04-20T10:05:00Z", "reason": "worker-lock-held"},
                    {"at": "2026-04-20T11:50:00Z", "reason": "provider-timeout"},
                ],
                "state": "idle",
                "service_name": None,
                "supervisor_kind": None,
            }
        )

        status = run_cli("status", "--workspace", str(self.workspace))

        self.assertEqual(
            [item["reason"] for item in status["dream"]["worker_health"]["recent_failures"]],
            ["provider-timeout"],
        )

    def test_consolidate_retypes_generic_semantic_fact_when_source_events_are_specific(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        store = MemoryStore(self.workspace)
        self.emit_runtime_event(
            self.workspace,
            kind="task_outcome",
            content="Redis must be running locally before the integration tests will pass.",
            message_ref="retype-1",
        )
        event = store.load_events()[-1]
        store.save_durable_records(
            [
                MemoryRecord(
                    memory_id="mem_semantic_fact_1",
                    type="semantic_fact",
                    scope="project",
                    title="Fact: redis-local-tests",
                    summary="Redis must be running locally before the integration tests will pass.",
                    body="Redis must be running locally before the integration tests will pass.",
                    status="active",
                    confidence=0.6,
                    salience=0.6,
                    source_event_ids=[event["event_id"]],
                    supersedes=[],
                    conflicts_with=[],
                    valid_from=FIXED_NOW,
                    valid_to=None,
                    access_count=0,
                    last_accessed_at=None,
                    created_at=FIXED_NOW,
                    updated_at=FIXED_NOW,
                    provenance_tier="inferred",
                    claim_class="externally_checkable",
                )
            ]
        )

        result = consolidate(store, now="2026-04-20T12:10:00Z")
        records = store.load_durable_records()

        self.assertEqual(result["updated"], 1)
        self.assertEqual(records[0]["type"], "environment_requirement")
        self.assertTrue(records[0]["title"].startswith("Environment:"))

    def test_service_status_reports_semantic_runtime_diagnosis(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        store = MemoryStore(self.workspace)
        store.save_semantic_config(
            {
                **store.load_semantic_config(),
                "mode": "semantic",
                "execution_strategy": "direct-provider",
                "preferred_auth_mode": "direct-provider",
                "candidate_strategies": ["direct-provider", "deterministic"],
            }
        )
        store.save_provider_registry(
            [
                {
                    "provider_id": "openai-primary",
                    "transport": "openai",
                    "model_id": "gpt-5.4",
                    "roles": ["synthesis", "verification"],
                    "health_status": "healthy",
                }
            ]
        )
        self.emit_runtime_event(
            self.workspace,
            kind="task_outcome",
            content="The semantic worker should synthesize learned context from explicit event backlog.",
            message_ref="semantic-status-1",
        )

        status = run_cli("service", "status", "--workspace", str(self.workspace))

        self.assertIn("semantic_runtime", status)
        semantic_runtime = status["semantic_runtime"]
        self.assertEqual(semantic_runtime["state"], "awaiting_materialization")
        self.assertEqual(semantic_runtime["work_mode"], "semantic")
        self.assertTrue(semantic_runtime["has_pending_signal"])
        self.assertEqual(semantic_runtime["latest_signal_source"], "explicit_events")

    def test_semantic_setup_apply_runs_initial_cycle_when_signal_is_available(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        store = MemoryStore(self.workspace)
        store.save_provider_registry(
            [
                {
                    "provider_id": "openai-primary",
                    "transport": "openai",
                    "model_id": "gpt-5.4",
                    "roles": ["synthesis", "verification"],
                    "health_status": "healthy",
                }
            ]
        )
        self.emit_runtime_event(
            self.workspace,
            kind="task_outcome",
            content=(
                "Workflow to reproduce the failure: run pytest tests/test_worker.py "
                "because Redis is required locally."
            ),
            message_ref="semantic-setup-1",
        )
        self.emit_runtime_event(
            self.workspace,
            kind="task_outcome",
            content=(
                "The tests failed because the local Redis service was missing; "
                "the working command sequence is docker compose up redis then pytest."
            ),
            message_ref="semantic-setup-2",
        )

        try:
            out = run_cli(
                "semantic",
                "setup",
                "--workspace",
                str(self.workspace),
                "--prefer",
                "direct-provider",
                "--apply",
                "--now",
                FIXED_NOW,
            )

            self.assertEqual(out["status"], "applied")
            self.assertIn("initial_cycle", out)
            self.assertTrue(out["initial_cycle"]["backlog_results"])
            self.assertEqual(out["initial_cycle"]["backlog_results"][0]["status"], "completed")
            self.assertEqual(out["readiness"]["semantic_capability_state"], "ready")
        finally:
            run_cli_raw("service", "disable", "--workspace", str(self.workspace), check=False)

    def test_workspace_upgrade_refreshes_managed_service_manifest(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        try:
            run_cli("service", "enable", "--workspace", str(self.workspace))
            store = MemoryStore(self.workspace)
            manifest = store.load_service_manifest()
            manifest["command"] = [part for part in manifest["command"] if part not in {"--mode", "auto"}]
            store.save_service_manifest(manifest)

            out = run_cli("workspace", "upgrade", "--workspace", str(self.workspace))

            workspaces = out["workspaces"]
            self.assertEqual(len(workspaces), 1)
            self.assertIn("updated", workspaces[0]["runtime_management"]["steps"])
            refreshed = store.load_service_manifest()
            self.assertIn("--mode", refreshed["command"])
            self.assertIn("auto", refreshed["command"])
        finally:
            run_cli("service", "disable", "--workspace", str(self.workspace))

    def test_prepare_context_merges_project_and_global_with_precedence(self) -> None:
        run_cli("init", "--workspace", str(self.global_workspace), "--store-kind", "global")
        self.emit_runtime_event(
            self.global_workspace,
            kind="preference_signal",
            content="Use uv across repos.",
            message_ref="global-pref-1",
            scope="global",
            tag="key:package-manager",
        )
        self.emit_runtime_event(
            self.global_workspace,
            kind="preference_signal",
            content="Prefer bat for paging output.",
            message_ref="global-pref-2",
            scope="global",
            tag="key:pager",
        )
        run_cli("maintain", "--workspace", str(self.global_workspace), "--now", FIXED_NOW)

        self.emit_runtime_event(
            self.workspace,
            kind="project_decision",
            content="Use pnpm in this repo.",
            message_ref="project-decision-1",
            tag="key:package-manager",
        )
        run_cli("maintain", "--workspace", str(self.workspace), "--now", FIXED_NOW)

        context = run_cli(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "package manager and pager preferences",
            "--now",
            FIXED_NOW,
            "--include-global",
            "--global-workspace",
            str(self.global_workspace),
        )
        self.assertIn("Use pnpm in this repo.", context["prompt_context"])
        self.assertNotIn("Use uv across repos.", context["prompt_context"])
        self.assertIn("Prefer bat for paging output.", context["prompt_context"])
        self.assertTrue(any(item["store_kind"] == "global" for item in context["selected_memories"]))
        self.assertTrue(any(item["store_kind"] == "project" for item in context["selected_memories"]))

    def test_prepare_context_startup_profile_stays_pointer_like(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        self.emit_runtime_event(
            self.workspace,
            kind="project_decision",
            content="Use pnpm for workspace dependencies and keep install scripts deterministic.",
            message_ref="startup-project-1",
            tag="key:package-manager",
        )
        self.emit_runtime_event(
            self.workspace,
            kind="environment_requirement",
            content="Redis is required for background jobs and local smoke runs.",
            message_ref="startup-env-1",
            tag="key:redis",
        )
        run_cli("maintain", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        self.write_learned_context_records(
            self.workspace,
            {
                "record_id": "learned-startup-1",
                "workspace_id": str(self.workspace),
                "source_event_ids": ["startup-project-1"],
                "query_family_tags": ["startup", "overview", "setup"],
                "summary": "Startup tasks usually need package manager and service pointers only.",
                "details": "Expand learned context only after a concrete task asks for operational detail.",
                "assumptions": "Startup context should stay compact.",
                "provider_id": "codex-local",
                "model_id": "gpt-5.4",
                "prompt_version": "v1",
                "created_at": FIXED_NOW,
                "fresh_until": "2026-04-26T12:00:00Z",
                "confidence": 0.87,
                "verifier_status": "approved",
                "conflict_state": "none",
                "promotion_target": "learned_context",
                "status": "active",
            },
        )

        context = run_cli(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "startup overview",
            "--now",
            FIXED_NOW,
        )

        self.assertEqual(context["profile"]["name"], "startup")
        self.assertEqual(context["selected_learned_context_records"], [])
        self.assertEqual(context["selection"]["learned_context"]["selected"], 0)
        self.assertGreaterEqual(context["selection"]["startup_index"]["selected"], 1)
        self.assertGreater(context["context_pruning"]["candidate_count"], context["context_pruning"]["injected_count"])
        self.assertNotIn("####", context["prompt_context"])
        self.assertNotIn(
            "Expand learned context only after a concrete task asks for operational detail.",
            context["prompt_context"],
        )
        self.assertTrue(
            any(
                item["reason"] == "startup_profile_keeps_learned_context_pointer_only"
                for item in context["suppressed"]
            )
        )

    def test_prepare_context_semantic_task_profile_bounds_learned_context(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        self.emit_runtime_event(
            self.workspace,
            kind="project_decision",
            content="Use pnpm for workspace dependencies and workspace scripts.",
            message_ref="task-project-1",
            tag="key:package-manager",
        )
        self.emit_runtime_event(
            self.workspace,
            kind="environment_requirement",
            content="Redis is required for background jobs and semantic workers.",
            message_ref="task-env-1",
            tag="key:redis",
        )
        run_cli("maintain", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        self.write_learned_context_records(
            self.workspace,
            {
                "record_id": "learned-task-1",
                "workspace_id": str(self.workspace),
                "source_event_ids": ["task-project-1"],
                "query_family_tags": ["workflow", "dependencies", "setup"],
                "summary": "When updating dependencies, check pnpm workspace constraints first.",
                "details": "Run pnpm install, then verify Redis-backed jobs against the same lockfile.",
                "assumptions": "Dependencies and runtime services stay coupled in this repo.",
                "provider_id": "codex-local",
                "model_id": "gpt-5.4",
                "prompt_version": "v1",
                "created_at": FIXED_NOW,
                "fresh_until": "2026-04-26T12:00:00Z",
                "confidence": 0.91,
                "verifier_status": "approved",
                "conflict_state": "none",
                "promotion_target": "learned_context",
                "status": "active",
            },
            {
                "record_id": "learned-task-2",
                "workspace_id": str(self.workspace),
                "source_event_ids": ["task-env-1"],
                "query_family_tags": ["workflow", "jobs", "redis"],
                "summary": "Redis checks matter after dependency changes.",
                "details": "Confirm the worker boots cleanly before treating the dependency task as complete.",
                "assumptions": "The job runner remains local-first.",
                "provider_id": "codex-local",
                "model_id": "gpt-5.4",
                "prompt_version": "v1",
                "created_at": FIXED_NOW,
                "fresh_until": "2026-04-26T12:00:00Z",
                "confidence": 0.78,
                "verifier_status": "approved",
                "conflict_state": "none",
                "promotion_target": "learned_context",
                "status": "active",
            },
        )

        context = run_cli(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "how should I update the package manager workflow for redis jobs",
            "--now",
            FIXED_NOW,
        )

        self.assertEqual(context["profile"]["name"], "semantic_task")
        self.assertEqual(len(context["selected_learned_context_records"]), 1)
        self.assertEqual(context["selection"]["learned_context"]["selected"], 1)
        self.assertEqual(context["profile"]["learned_context_budget"], 1)
        self.assertIn("## Learned Context", context["prompt_context"])
        self.assertIn(
            "Run pnpm install, then verify Redis-backed jobs against the same lockfile.",
            context["prompt_context"],
        )
        self.assertTrue(any(item["reason"] == "profile_budget_exceeded" for item in context["suppressed"]))

    def test_prepare_context_deep_task_profile_expands_learned_context_budget(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        self.emit_runtime_event(
            self.workspace,
            kind="project_decision",
            content="Use pnpm for workspace dependencies and workspace scripts.",
            message_ref="deep-project-1",
            tag="key:package-manager",
        )
        self.emit_runtime_event(
            self.workspace,
            kind="environment_requirement",
            content="Redis is required for background jobs and semantic workers.",
            message_ref="deep-env-1",
            tag="key:redis",
        )
        run_cli("maintain", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        self.write_learned_context_records(
            self.workspace,
            {
                "record_id": "learned-deep-1",
                "workspace_id": str(self.workspace),
                "source_event_ids": ["deep-project-1"],
                "query_family_tags": ["workflow", "dependencies", "setup"],
                "summary": "Dependency changes should preserve pnpm workspace invariants.",
                "details": "Check workspace filters, lockfile drift, and install hooks before merging.",
                "assumptions": "The repo keeps one package-manager policy.",
                "provider_id": "codex-local",
                "model_id": "gpt-5.4",
                "prompt_version": "v1",
                "created_at": FIXED_NOW,
                "fresh_until": "2026-04-26T12:00:00Z",
                "confidence": 0.93,
                "verifier_status": "approved",
                "conflict_state": "none",
                "promotion_target": "learned_context",
                "status": "active",
            },
            {
                "record_id": "learned-deep-2",
                "workspace_id": str(self.workspace),
                "source_event_ids": ["deep-env-1"],
                "query_family_tags": ["workflow", "redis", "jobs"],
                "summary": "Redis-backed jobs need an explicit smoke pass after dependency work.",
                "details": "Validate worker boot, queue reachability, and at least one end-to-end job.",
                "assumptions": "The operator wants deeper task context, not startup pointers.",
                "provider_id": "codex-local",
                "model_id": "gpt-5.4",
                "prompt_version": "v1",
                "created_at": FIXED_NOW,
                "fresh_until": "2026-04-26T12:00:00Z",
                "confidence": 0.86,
                "verifier_status": "approved",
                "conflict_state": "none",
                "promotion_target": "learned_context",
                "status": "active",
            },
            {
                "record_id": "learned-deep-3",
                "workspace_id": str(self.workspace),
                "source_event_ids": ["deep-env-1"],
                "query_family_tags": ["workflow", "redis", "analysis"],
                "summary": "Deep investigations should keep one additional Redis troubleshooting note.",
                "details": "Capture queue inspection commands and worker diagnostics only in the deep profile.",
                "assumptions": "This note is useful only when the operator explicitly asks for deeper context.",
                "provider_id": "codex-local",
                "model_id": "gpt-5.4",
                "prompt_version": "v1",
                "created_at": FIXED_NOW,
                "fresh_until": "2026-04-26T12:00:00Z",
                "confidence": 0.71,
                "verifier_status": "approved",
                "conflict_state": "none",
                "promotion_target": "learned_context",
                "status": "active",
            },
        )

        context = run_cli(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "deep analysis for updating the package manager workflow and redis background jobs",
            "--limit",
            "8",
            "--now",
            FIXED_NOW,
        )

        self.assertEqual(context["profile"]["name"], "deep_task")
        self.assertEqual(context["profile"]["learned_context_budget"], 2)
        self.assertEqual(len(context["selected_learned_context_records"]), 2)
        self.assertEqual(context["selection"]["learned_context"]["selected"], 2)
        self.assertIn(
            "Check workspace filters, lockfile drift, and install hooks before merging.",
            context["prompt_context"],
        )
        self.assertIn(
            "Validate worker boot, queue reachability, and at least one end-to-end job.",
            context["prompt_context"],
        )
        self.assertGreaterEqual(context["context_pruning"]["saved_characters"], 1)

    def test_maintain_supports_store_manifests(self) -> None:
        run_cli("init", "--workspace", str(self.global_workspace), "--store-kind", "global")
        self.emit_runtime_event(
            self.workspace,
            kind="project_decision",
            content="Use pnpm in this repo.",
            message_ref="manifest-project-1",
            tag="key:package-manager",
        )
        self.emit_runtime_event(
            self.global_workspace,
            kind="preference_signal",
            content="Prefer concise summaries across repos.",
            message_ref="manifest-global-1",
            scope="global",
            tag="key:summary-style",
        )
        manifest = self.write_manifest((self.workspace, "project"), (self.global_workspace, "global"))
        result = run_cli(
            "maintain",
            "--workspace",
            str(self.workspace),
            "--stores-manifest",
            str(manifest),
            "--now",
            FIXED_NOW,
        )
        self.assertEqual(result["store_count"], 2)
        self.assertEqual([item["store_kind"] for item in result["stores"]], ["project", "global"])
        self.assertTrue(all(item["status"] == "completed" for item in result["stores"]))

    def test_status_reports_uninitialized_and_stale_lock(self) -> None:
        uninitialized = run_cli("status", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        self.assertFalse(uninitialized["initialized"])
        self.assertEqual(uninitialized["state"], "uninitialized")
        self.assertEqual(uninitialized["overall_state"], "inactive")
        self.assertEqual(uninitialized["dream"]["state"], "never_ran")

        run_cli("init", "--workspace", str(self.workspace))
        lock_path = self.workspace / DEFAULT_MEMORY_DIR / "locks" / "consolidator.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps({"pid": 1234, "acquired_at": FIXED_NOW}), encoding="utf-8")
        stale = time.time() - 4000
        os.utime(lock_path, (stale, stale))

        snapshot = run_cli("status", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        self.assertTrue(snapshot["initialized"])
        self.assertTrue(snapshot["lock"]["present"])
        self.assertTrue(snapshot["lock"]["stale"])
        self.assertIn("runtime", snapshot)

    def test_dream_run_ingests_transcript_only_fixture_and_normalizes_dates(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "transcript_only_dream.jsonl"
        result = run_cli(
            "dream",
            "run",
            "--workspace",
            str(self.workspace),
            "--episodes",
            str(fixture),
            "--now",
            FIXED_NOW,
            "--memory-dir",
            ".dream-memory",
            "--compat-mode",
            "autodream",
        )
        self.assertEqual(result["status"], "completed")
        memory_root = self.workspace / ".dream-memory"
        self.assertTrue((memory_root / "MEMORY.md").exists())
        self.assertTrue((memory_root / "project.md").exists())
        self.assertTrue((memory_root / "user.md").exists())
        records = json.loads((memory_root / "state" / "durable_records.json").read_text(encoding="utf-8"))
        self.assertTrue(any("2026-03-27" in record["body"] for record in records))
        status_snapshot = run_cli(
            "status",
            "--workspace",
            str(self.workspace),
            "--memory-dir",
            ".dream-memory",
            "--now",
            FIXED_NOW,
        )
        self.assertEqual(status_snapshot["dream"]["state"], "idle")
        self.assertEqual(status_snapshot["dream"]["last_ran_at"], FIXED_NOW)

    def test_dream_run_skips_when_lock_is_held(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "transcript_only_dream.jsonl"
        run_cli("init", "--workspace", str(self.workspace))
        lock_path = self.workspace / DEFAULT_MEMORY_DIR / "locks" / "dream.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps({"pid": 9999, "acquired_at": FIXED_NOW}), encoding="utf-8")

        result = run_cli(
            "dream",
            "run",
            "--workspace",
            str(self.workspace),
            "--episodes",
            str(fixture),
            "--now",
            FIXED_NOW,
        )
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "lock-held")

    def test_dream_run_without_episodes_returns_explicit_skip(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        result = run_cli("dream", "run", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        status_snapshot = run_cli("dream", "status", "--workspace", str(self.workspace), "--now", FIXED_NOW)

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "no-episodes")
        self.assertEqual(status_snapshot["dream"]["last_run_reason"], "no-episodes")

    def test_dream_enqueue_without_episodes_returns_explicit_skip(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        result = run_cli("dream", "enqueue", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        status_snapshot = run_cli("dream", "status", "--workspace", str(self.workspace), "--now", FIXED_NOW)

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "no-episodes")
        self.assertEqual(result["queue_depth"], 0)
        self.assertEqual(status_snapshot["dream"]["queue_depth"], 0)

    def test_consolidate_emits_plan_and_verifier_artifacts(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
        run_cli("append-event", "--workspace", str(self.workspace), "--events", str(fixture))
        run_cli("extract", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        result = run_cli("consolidate", "--workspace", str(self.workspace), "--now", FIXED_NOW)

        plan_path = self.workspace / result["planner_artifact"]
        verifier_path = self.workspace / result["verifier_artifact"]
        self.assertTrue(plan_path.exists())
        self.assertTrue(verifier_path.exists())
        validate_document("dream-plan.schema.json", json.loads(plan_path.read_text(encoding="utf-8")))
        validate_document("verifier-report.schema.json", json.loads(verifier_path.read_text(encoding="utf-8")))

    def test_dream_enqueue_and_worker_drain_queue_across_restarts(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "transcript_only_dream.jsonl"
        run_cli(
            "init",
            "--workspace",
            str(self.workspace),
            "--memory-dir",
            ".dream-memory",
            "--compat-mode",
            "autodream",
        )
        first = run_cli(
            "dream",
            "enqueue",
            "--workspace",
            str(self.workspace),
            "--episodes",
            str(fixture),
            "--now",
            FIXED_NOW,
            "--memory-dir",
            ".dream-memory",
            "--compat-mode",
            "autodream",
        )
        second = run_cli(
            "dream",
            "enqueue",
            "--workspace",
            str(self.workspace),
            "--episodes",
            str(fixture),
            "--now",
            "2026-03-26T12:01:00Z",
            "--memory-dir",
            ".dream-memory",
            "--compat-mode",
            "autodream",
        )
        self.assertEqual(first["queue_depth"], 1)
        self.assertEqual(second["queue_depth"], 2)

        status_before = run_cli(
            "dream",
            "status",
            "--workspace",
            str(self.workspace),
            "--memory-dir",
            ".dream-memory",
            "--now",
            FIXED_NOW,
        )
        self.assertEqual(status_before["dream"]["queue_depth"], 2)

        first_worker = run_cli(
            "dream",
            "worker",
            "--workspace",
            str(self.workspace),
            "--memory-dir",
            ".dream-memory",
            "--compat-mode",
            "autodream",
            "--now",
            FIXED_NOW,
            "--once",
            "--max-jobs-per-poll",
            "1",
        )
        second_worker = run_cli(
            "dream",
            "daemon",
            "--workspace",
            str(self.workspace),
            "--memory-dir",
            ".dream-memory",
            "--compat-mode",
            "autodream",
            "--now",
            "2026-03-26T12:02:00Z",
            "--once",
            "--max-jobs-per-poll",
            "1",
        )
        self.assertEqual(len(first_worker["processed_jobs"]), 1)
        self.assertEqual(len(second_worker["processed_jobs"]), 1)

        status_after = run_cli(
            "dream",
            "status",
            "--workspace",
            str(self.workspace),
            "--memory-dir",
            ".dream-memory",
            "--now",
            "2026-03-26T12:02:00Z",
        )
        self.assertEqual(status_after["dream"]["queue_depth"], 0)
        self.assertEqual(status_after["dream"]["worker"]["queue_depth"], 0)
        self.assertTrue((self.workspace / ".dream-memory" / "state" / "dream_queue.json").exists())

    def test_dream_status_and_tick_aliases_use_transcript_backlog(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "transcript_only_dream.jsonl"
        run_cli(
            "init",
            "--workspace",
            str(self.workspace),
            "--memory-dir",
            ".dream-memory",
            "--compat-mode",
            "autodream",
        )
        transcript_dir = self.workspace / ".dream-memory" / "state" / "transcripts"
        transcript_dir.mkdir(parents=True, exist_ok=True)
        (transcript_dir / "session-1.jsonl").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

        before = run_cli(
            "dream",
            "status",
            "--workspace",
            str(self.workspace),
            "--memory-dir",
            ".dream-memory",
            "--now",
            FIXED_NOW,
        )
        first = run_cli(
            "dream",
            "tick",
            "--workspace",
            str(self.workspace),
            "--memory-dir",
            ".dream-memory",
            "--compat-mode",
            "autodream",
            "--now",
            FIXED_NOW,
            "--min-interval-seconds",
            "60",
        )
        second = run_cli(
            "dream",
            "tick",
            "--workspace",
            str(self.workspace),
            "--memory-dir",
            ".dream-memory",
            "--compat-mode",
            "autodream",
            "--now",
            "2026-03-26T12:00:10Z",
            "--min-interval-seconds",
            "60",
        )
        after = run_cli(
            "dream",
            "status",
            "--workspace",
            str(self.workspace),
            "--memory-dir",
            ".dream-memory",
            "--now",
            "2026-03-26T12:00:10Z",
        )

        self.assertEqual(before["dream"]["state"], "never_ran")
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["trigger_class"], "transcript-backlog")
        self.assertEqual(second["status"], "skipped")
        self.assertEqual(second["reason"], "min-interval")
        self.assertEqual(after["dream"]["state"], "idle")
        self.assertEqual(after["dream"]["last_ran_at"], FIXED_NOW)
        self.assertEqual(after["dream"]["last_run_reason"], "transcript-backlog")

    def test_dream_backfill_narrative_updates_existing_summary(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        audit_dir = self.workspace / ".opendream" / "memory" / "audit" / "dream"
        audit_dir.mkdir(parents=True, exist_ok=True)
        summary_path = audit_dir / "dream-backfill-summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "action": "dream",
                    "run_id": "dream-backfill",
                    "workspace": str(self.workspace),
                    "memory_root": str(self.workspace / ".opendream" / "memory"),
                    "target_paths": [],
                    "summary": {
                        "run_id": "dream-backfill",
                        "status": "skipped",
                        "reason": "no-episodes",
                        "phases": ["orient"],
                    },
                }
            ),
            encoding="utf-8",
        )

        result = run_cli("dream", "backfill-narrative", "--workspace", str(self.workspace))

        self.assertEqual(result["narratives_backfilled"], 1)
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertIn("no agent transcripts", payload["summary"]["narrative"])

    def test_dream_help_clarifies_worker_and_daemon_roles(self) -> None:
        dream_help = run_cli_raw("dream", "-h", check=False)
        worker_help = run_cli_raw("dream", "worker", "-h", check=False)
        daemon_help = run_cli_raw("dream", "daemon", "-h", check=False)

        self.assertEqual(dream_help.returncode, 0)
        self.assertIn("one-shot or bounded worker poll", dream_help.stdout)
        self.assertIn("supervisor-friendly looping", dream_help.stdout)
        self.assertIn("Use `--once` for a single poll.", worker_help.stdout)
        self.assertIn("worker --once", daemon_help.stdout)

    def test_tick_reports_status_and_repeated_invocation(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        self.emit_runtime_event(
            self.workspace,
            kind="project_decision",
            content="Use the local-first memory runtime.",
            message_ref="tick-msg-1",
            tag="key:runtime",
        )
        first = run_cli(
            "tick",
            "--workspace",
            str(self.workspace),
            "--now",
            FIXED_NOW,
            "--min-interval-seconds",
            "60",
        )
        second = run_cli(
            "tick",
            "--workspace",
            str(self.workspace),
            "--now",
            "2026-03-26T12:00:10Z",
            "--min-interval-seconds",
            "60",
        )
        snapshot = run_cli(
            "status",
            "--workspace",
            str(self.workspace),
            "--now",
            "2026-03-26T12:00:10Z",
            "--min-interval-seconds",
            "60",
        )
        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "skipped")
        self.assertEqual(second["reason"], "min-interval")
        self.assertEqual(snapshot["last_run_at"], FIXED_NOW)
        self.assertEqual(snapshot["next_eligible_reason"], "min-interval")

    def test_tick_supports_manifest_store_groups(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        run_cli("init", "--workspace", str(self.global_workspace), "--store-kind", "global")
        self.emit_runtime_event(
            self.workspace,
            kind="project_decision",
            content="Use pnpm in this repo.",
            message_ref="tick-manifest-project",
            tag="key:package-manager",
        )
        self.emit_runtime_event(
            self.global_workspace,
            kind="preference_signal",
            content="Prefer concise summaries across repos.",
            message_ref="tick-manifest-global",
            scope="global",
            tag="key:summary-style",
        )
        manifest = self.write_manifest((self.workspace, "project"), (self.global_workspace, "global"))
        first = run_cli(
            "tick",
            "--workspace",
            str(self.workspace),
            "--stores-manifest",
            str(manifest),
            "--now",
            FIXED_NOW,
        )
        second = run_cli(
            "tick",
            "--workspace",
            str(self.workspace),
            "--stores-manifest",
            str(manifest),
            "--now",
            "2026-03-26T12:05:00Z",
        )
        self.assertEqual(first["store_count"], 2)
        self.assertEqual(first["status"], "completed")
        self.assertTrue(all(item["status"] == "completed" for item in first["stores"]))
        self.assertEqual(second["status"], "skipped")

    def test_automation_register_run_status_and_context(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
        run_cli("append-event", "--workspace", str(self.workspace), "--events", str(fixture))
        run_cli("maintain", "--workspace", str(self.workspace), "--now", FIXED_NOW)

        spec_path = self.write_automation_spec(
            {
                "job_id": "release-watch",
                "title": "Release watch",
                "description": "Track release-affecting workflow signals.",
                "skill_ref": "builtin://projection-engine",
                "trigger": {"type": "interval", "interval_seconds": 60},
                "input_selectors": {
                    "memory_types_any": [
                        "project_decision",
                        "environment_requirement",
                        "workflow",
                        "user_preference",
                    ],
                    "text_terms_any": ["redis", "migration", "package"],
                    "statuses_any": ["active"],
                    "limit": 10,
                },
                "output": {"record_type": "feature", "max_records": 10},
                "merge_policy": {"dedupe_by": "title"},
                "decay_policy": {"stale_after_runs": 1},
                "review_policy": {"require_manual_review": True, "auto_surface_limit": 3},
                "security_policy": {"allow_sensitive": False},
            }
        )
        registered = run_cli(
            "automation",
            "register",
            "--workspace",
            str(self.workspace),
            "--spec",
            str(spec_path),
            "--now",
            FIXED_NOW,
        )
        self.assertEqual(registered["status"], "registered")
        validate_document("automation-job.schema.json", registered["job"])

        snapshot_before = run_cli("status", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        self.assertIn("release-watch", snapshot_before["runtime"]["automation"]["due_job_ids"])
        self.assertIn("opendream tick", snapshot_before["next_action"])

        result = run_cli(
            "automation",
            "run",
            "--workspace",
            str(self.workspace),
            "--job",
            "release-watch",
            "--now",
            FIXED_NOW,
        )
        self.assertEqual(result["status"], "completed")
        validate_document(
            "automation-run-report.schema.json",
            {k: v for k, v in result.items() if k not in {"workspace", "memory_root"}},
        )

        records = json.loads(
            (
                self.workspace
                / DEFAULT_MEMORY_DIR
                / "automation"
                / "records"
                / "feature"
                / "release-watch.json"
            ).read_text(encoding="utf-8")
        )
        self.assertGreaterEqual(len(records), 1)
        for record in records:
            validate_document("automation-record.schema.json", record)

        status_payload = run_cli(
            "automation",
            "status",
            "--workspace",
            str(self.workspace),
            "--job",
            "release-watch",
            "--now",
            FIXED_NOW,
        )
        self.assertEqual(status_payload["automation"]["job_count"], 1)
        self.assertEqual(status_payload["job_state"]["last_status"], "completed")
        self.assertGreaterEqual(len(status_payload["records"]), 1)

        context = run_cli(
            "prepare-context",
            "--workspace",
            str(self.workspace),
            "--query",
            "migration runtime",
            "--now",
            FIXED_NOW,
        )
        self.assertIn("Active Automation Projections", context["prompt_context"])
        self.assertGreaterEqual(len(context["selected_automation_record_ids"]), 1)

    def test_automation_staleness_and_top_level_tick(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
        run_cli("append-event", "--workspace", str(self.workspace), "--events", str(fixture))
        run_cli("maintain", "--workspace", str(self.workspace), "--now", FIXED_NOW)

        initial_spec = self.write_automation_spec(
            {
                "job_id": "ops-radar",
                "title": "Ops radar",
                "description": "Track redis rollout work.",
                "skill_ref": "builtin://projection-engine",
                "trigger": {"type": "interval", "interval_seconds": 60},
                "input_selectors": {
                    "memory_types_any": [
                        "project_decision",
                        "environment_requirement",
                        "workflow",
                        "user_preference",
                    ],
                    "text_terms_any": ["redis"],
                    "statuses_any": ["active"],
                    "limit": 10,
                },
                "output": {"record_type": "bug", "max_records": 10},
                "merge_policy": {"dedupe_by": "title"},
                "decay_policy": {"stale_after_runs": 1},
                "review_policy": {"require_manual_review": True, "auto_surface_limit": 3},
                "security_policy": {"allow_sensitive": False},
            },
            name="ops-radar-initial.json",
        )
        run_cli(
            "automation",
            "register",
            "--workspace",
            str(self.workspace),
            "--spec",
            str(initial_spec),
            "--now",
            FIXED_NOW,
        )

        tick_result = run_cli("tick", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        self.assertEqual(tick_result["status"], "completed")
        self.assertEqual(tick_result["automation"]["status"], "completed")

        updated_spec = self.write_automation_spec(
            {
                "job_id": "ops-radar",
                "title": "Ops radar",
                "description": "Track redis rollout work.",
                "skill_ref": "builtin://projection-engine",
                "trigger": {"type": "interval", "interval_seconds": 60},
                "input_selectors": {
                    "memory_types_any": [
                        "project_decision",
                        "environment_requirement",
                        "workflow",
                        "user_preference",
                    ],
                    "text_terms_any": ["nonexistent-term"],
                    "statuses_any": ["active"],
                    "limit": 10,
                },
                "output": {"record_type": "bug", "max_records": 10},
                "merge_policy": {"dedupe_by": "title"},
                "decay_policy": {"stale_after_runs": 1},
                "review_policy": {"require_manual_review": True, "auto_surface_limit": 3},
                "security_policy": {"allow_sensitive": False},
            },
            name="ops-radar-updated.json",
        )
        run_cli(
            "automation",
            "register",
            "--workspace",
            str(self.workspace),
            "--spec",
            str(updated_spec),
            "--now",
            "2026-03-26T12:01:00Z",
        )
        run_cli(
            "automation",
            "run",
            "--workspace",
            str(self.workspace),
            "--job",
            "ops-radar",
            "--now",
            "2026-03-26T12:01:00Z",
        )

        review = run_cli(
            "automation",
            "review",
            "--workspace",
            str(self.workspace),
            "--job",
            "ops-radar",
            "--now",
            "2026-03-26T12:01:00Z",
        )
        self.assertTrue(any(record["status"] == "stale" for record in review["records"]))
        snapshot = run_cli(
            "status",
            "--workspace",
            str(self.workspace),
            "--now",
            "2026-03-26T12:01:00Z",
        )
        self.assertEqual(snapshot["runtime"]["automation"]["stale_records"], 1)

    def test_eval_memory_quality_command(self) -> None:
        result = run_cli(
            "eval",
            "memory-quality",
            "--workspace",
            str(self.workspace),
            "--now",
            FIXED_NOW,
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["paraphrase_hits"], result["query_count"])
        self.assertGreaterEqual(result["lexical_only_misses"], 1)

    def test_eval_memory_quality_failure_exits_nonzero(self) -> None:
        run_cli("demo", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        completed = run_cli_raw(
            "eval",
            "memory-quality",
            "--workspace",
            str(self.workspace),
            "--now",
            FIXED_NOW,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("fresh workspace", completed.stderr.lower())
        self.assertIn("isolated store", completed.stderr.lower())

    def test_eval_performance_hermetic_after_demo(self) -> None:
        baseline = run_cli(
            "eval",
            "performance",
            "--workspace",
            str(self.workspace),
            "--now",
            FIXED_NOW,
        )
        self.assertEqual(baseline["status"], "passed")
        weighted_baseline = baseline["scorecard"]["weighted_total"]

        run_cli("demo", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        after_demo = run_cli(
            "eval",
            "performance",
            "--workspace",
            str(self.workspace),
            "--now",
            FIXED_NOW,
        )
        self.assertEqual(after_demo["status"], "passed")
        deterministic_keys = (
            "write_precision",
            "retrieval_precision",
            "expected_answer_coverage",
            "concurrency_safety",
            "contradiction_handling",
            "procedural_reuse",
            "workflow_memory",
            "gating_accuracy",
        )
        for key in deterministic_keys:
            self.assertEqual(
                baseline["scorecard"][key],
                after_demo["scorecard"][key],
                msg="isolated eval scorecard should not depend on workspace demo state",
            )
        # `latency` includes maintain_ms from monotonic clocks; tiny jitter can move weighted_total by ~0.1.
        self.assertAlmostEqual(
            after_demo["scorecard"]["weighted_total"],
            weighted_baseline,
            delta=0.5,
        )

    def test_eval_showcase_is_hermetic_after_demo(self) -> None:
        run_cli("demo", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        result = run_cli(
            "eval",
            "showcase",
            "--scenario",
            "coding-agent-showcase",
            "--workspace",
            str(self.workspace),
            "--now",
            FIXED_NOW,
        )
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["checks"]["recall"]["passed"])
        self.assertTrue(result["checks"]["stale_update"]["passed"])
        self.assertTrue(result["checks"]["decoy_rejection"]["passed"])
        self.assertTrue(result["checks"]["negative_controls"]["passed"])
        self.assertTrue(result["checks"]["abstention"]["passed"])
        self.assertTrue(result["checks"]["memory_hurt"]["passed"])
        self.assertTrue(result["checks"]["provenance"]["passed"])
        self.assertTrue(result["checks"]["snippet"]["passed"])
        self.assertTrue(result["checks"]["answer_improvement"]["passed"])
        self.assertTrue(result["agent_answers"]["comparison"]["passed"])
        self.assertTrue(all(case["passed"] for case in result["negative_controls"]))
        self.assertTrue(all(case["abstained"] for case in result["abstention_cases"]))
        self.assertTrue(result["memory_hurt_cases"][0]["forced_memory_hurt"]["contradicted_recalled"])
        self.assertTrue(Path(result["report_path"]).exists())

    def test_init_file_workspace_errors_without_traceback(self) -> None:
        blocker = self.workspace / "not_a_directory"
        blocker.write_text("x", encoding="utf-8")
        completed = run_cli_raw("init", "--workspace", str(blocker), check=False)
        self.assertEqual(completed.returncode, 2)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertIn("error:", completed.stderr)

    def test_doctor_rejects_memory_shorthand_with_hint(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        completed = run_cli_raw(
            "doctor",
            "--workspace",
            str(self.workspace),
            "--memory",
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--surface memory", completed.stderr)
        self.assertNotIn("argument --memory-dir: expected one argument", completed.stderr)

    def test_cli_version_matches_pyproject(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        expected_ver = pyproject["project"]["version"]
        completed = run_cli_raw("--version", check=False)
        self.assertEqual(completed.returncode, 0)
        self.assertIn(expected_ver, completed.stdout)
        self.assertTrue(completed.stdout.strip().startswith("opendream "))

    def test_eval_dream_fidelity_failure_stderr_hint(self) -> None:
        completed = run_cli_raw(
            "eval",
            "dream-fidelity",
            "--workspace",
            str(self.workspace),
            "--now",
            FIXED_NOW,
            "--compat-mode",
            "canonical",
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("failing checks:", completed.stderr)
        self.assertIn("compatibility_views", completed.stderr)
        self.assertIn("autodream", completed.stderr)

    def test_contract_misplaced_workspace_prints_export_hint(self) -> None:
        completed = run_cli_raw("contract", "/tmp/opendream-contract-path-hint-test", check=False)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("Hint:", completed.stderr)
        self.assertIn("contract export", completed.stderr)

    def test_retrieve_help_mentions_query_gating(self) -> None:
        completed = run_cli_raw("retrieve", "-h", check=False)
        self.assertEqual(completed.returncode, 0)
        self.assertIn("gated", completed.stdout)

    def test_eval_dream_fidelity_command(self) -> None:
        result = run_cli(
            "eval",
            "dream-fidelity",
            "--workspace",
            str(self.workspace),
            "--now",
            FIXED_NOW,
            "--memory-dir",
            ".dream-memory",
            "--compat-mode",
            "autodream",
        )
        self.assertEqual(result["status"], "passed")
        self.assertTrue(all(result["checks"].values()))
        self.assertTrue(any("pnpm" in title.lower() for title in result["selected_titles"]))

    def test_service_lifecycle_status_and_doctor(self) -> None:
        transcript = REPO_ROOT / "tests" / "fixtures" / "transcript_only_dream.jsonl"
        memory_dir = ".dream-memory"
        run_cli(
            "dream",
            "enqueue",
            "--workspace",
            str(self.workspace),
            "--episodes",
            str(transcript),
            "--memory-dir",
            memory_dir,
        )
        install_root = Path(self.temp_dir.name) / "services"
        run_cli(
            "install-service",
            "--workspace",
            str(self.workspace),
            "--memory-dir",
            memory_dir,
            "--install-root",
            str(install_root),
            "--interval-seconds",
            "0.2",
            "--no-start",
        )
        try:
            started = run_cli("service", "start", "--workspace", str(self.workspace), "--memory-dir", memory_dir)
            self.assertTrue(started["running"])
            time.sleep(0.5)

            status = run_cli("service", "status", "--workspace", str(self.workspace), "--memory-dir", memory_dir)
            self.assertTrue(status["installed"])
            self.assertTrue(status["running"])
            self.assertIn(status["health"], {"healthy", "idle", "draining"})
            self.assertGreaterEqual(status["start_count"], 1)
            self.assertIn("worker_health", status)

            doctor = run_cli("service", "doctor", "--workspace", str(self.workspace), "--memory-dir", memory_dir)
            self.assertTrue(doctor["installed"])
            self.assertTrue(doctor["running"])
            self.assertIn("recommended_remediation", doctor)

            restarted = run_cli("service", "restart", "--workspace", str(self.workspace), "--memory-dir", memory_dir)
            self.assertEqual(restarted["status"], "restarted")

            stopped = run_cli("service", "stop", "--workspace", str(self.workspace), "--memory-dir", memory_dir)
            self.assertFalse(stopped["running"])

            stopped_status = run_cli(
                "service",
                "status",
                "--workspace",
                str(self.workspace),
                "--memory-dir",
                memory_dir,
            )
            self.assertEqual(stopped_status["health"], "stopped")
            self.assertFalse(stopped_status["running"])
        finally:
            run_cli_raw(
                "service",
                "stop",
                "--workspace",
                str(self.workspace),
                "--memory-dir",
                memory_dir,
                check=False,
            )
            run_cli_raw(
                "uninstall-service",
                "--workspace",
                str(self.workspace),
                "--memory-dir",
                memory_dir,
                "--purge",
                check=False,
            )

    def test_workspace_upgrade_ensures_background_runtime(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        try:
            result = run_cli("workspace", "upgrade", "--workspace", str(self.workspace))
            self.assertEqual(result["status"], "completed")
            upgraded = result["workspaces"][0]
            runtime = upgraded.get("runtime_management")
            self.assertIsInstance(runtime, dict)
            self.assertIn(runtime.get("status"), {"ensured", "started", "already-running"})

            service = run_cli("service", "status", "--workspace", str(self.workspace))
            self.assertTrue(service["installed"])
            self.assertTrue(service["running"])
            self.assertEqual(service["policy"]["management_mode"], "managed")
        finally:
            run_cli_raw("service", "disable", "--workspace", str(self.workspace), check=False)
            run_cli_raw("uninstall-service", "--workspace", str(self.workspace), "--purge", check=False)

    def test_service_enable_and_disable_manage_runtime_policy(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        try:
            enabled = run_cli("service", "enable", "--workspace", str(self.workspace))
            self.assertEqual(enabled["status"], "enabled")
            self.assertEqual(enabled["policy"]["management_mode"], "managed")
            self.assertTrue(enabled["service"]["running"])

            disabled = run_cli("service", "disable", "--workspace", str(self.workspace))
            self.assertEqual(disabled["status"], "disabled")
            self.assertEqual(disabled["policy"]["management_mode"], "disabled")
            self.assertFalse(disabled["service"]["running"])

            status = run_cli("service", "status", "--workspace", str(self.workspace))
            self.assertEqual(status["policy"]["management_mode"], "disabled")
            self.assertFalse(status["running"])
        finally:
            run_cli_raw("service", "disable", "--workspace", str(self.workspace), check=False)
            run_cli_raw("uninstall-service", "--workspace", str(self.workspace), "--purge", check=False)

    def test_service_autowire_is_idempotent_and_reversible(self) -> None:
        claude_settings = self.workspace / ".claude" / "settings.json"
        claude_settings.parent.mkdir(parents=True, exist_ok=True)
        existing_hooks = {
            "hooks": {
                "OtherEvent": [
                    {
                        "hooks": [
                            {"type": "command", "command": "echo keep-me"}
                        ]
                    }
                ]
            }
        }
        claude_settings.write_text(
            json.dumps(existing_hooks, indent=2) + "\n",
            encoding="utf-8",
        )
        agents_path = self.workspace / "AGENTS.md"
        agents_path.write_text("# AGENTS.md\n\nExisting repo guidance.\n", encoding="utf-8")

        first = run_cli("service", "autowire", "--workspace", str(self.workspace), "--target", "all", "--force")
        self.assertEqual(first["status"], "configured")
        self.assertTrue((self.workspace / ".opendream" / "hooks" / "claude-pre-task.sh").exists())
        self.assertTrue((self.workspace / ".opendream" / "hooks" / "codex-post-task.sh").exists())

        second = run_cli("service", "autowire", "--workspace", str(self.workspace), "--target", "all", "--force")
        self.assertEqual(second["status"], "configured")

        settings_payload = json.loads(claude_settings.read_text(encoding="utf-8"))
        # Check that the new event-based hooks are present
        self.assertIn("UserPromptSubmit", settings_payload["hooks"])
        self.assertIn("Stop", settings_payload["hooks"])
        # Verify the commands are only added once (idempotent)
        user_prompt_submit_hooks = settings_payload["hooks"]["UserPromptSubmit"]
        pre_cmd_count = sum(
            1 for matcher in user_prompt_submit_hooks
            if isinstance(matcher, dict) and "hooks" in matcher
            for h in matcher["hooks"]
            if isinstance(h, dict) and "claude-pre-task.sh" in h.get("command", "")
        )
        self.assertEqual(pre_cmd_count, 1)
        stop_hooks = settings_payload["hooks"]["Stop"]
        post_cmd_count = sum(
            1 for matcher in stop_hooks
            if isinstance(matcher, dict) and "hooks" in matcher
            for h in matcher["hooks"]
            if isinstance(h, dict) and "claude-post-task.sh" in h.get("command", "")
        )
        self.assertEqual(post_cmd_count, 1)

        agents_text = agents_path.read_text(encoding="utf-8")
        self.assertEqual(agents_text.count("<!-- BEGIN OPENDREAM MANAGED BLOCK: codex -->"), 1)
        self.assertEqual(agents_text.count("<!-- END OPENDREAM MANAGED BLOCK: codex -->"), 1)

        removed = run_cli(
            "service",
            "autowire",
            "--workspace",
            str(self.workspace),
            "--target",
            "codex",
            "--uninstall",
        )
        self.assertEqual(removed["status"], "removed")
        agents_text = agents_path.read_text(encoding="utf-8")
        self.assertNotIn("<!-- BEGIN OPENDREAM MANAGED BLOCK: codex -->", agents_text)
        self.assertNotIn("<!-- OPENDREAM:CODEX START -->", agents_text)

    def test_activate_is_idempotent_and_repairable(self) -> None:
        claude_settings = self.workspace / ".claude" / "settings.json"
        claude_settings.parent.mkdir(parents=True, exist_ok=True)
        existing_hooks = {
            "hooks": {
                "OtherEvent": [
                    {
                        "hooks": [
                            {"type": "command", "command": "echo keep-me"}
                        ]
                    }
                ]
            }
        }
        claude_settings.write_text(
            json.dumps(existing_hooks, indent=2) + "\n",
            encoding="utf-8",
        )
        codex_config = self.workspace / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True, exist_ok=True)
        codex_config.write_text('sandbox_mode = "workspace-write"\n', encoding="utf-8")
        openclaw_config = self.workspace / ".openclaw" / "config.json"
        openclaw_config.parent.mkdir(parents=True, exist_ok=True)
        openclaw_config.write_text(
            json.dumps({"hooks": {"postTask": ["echo keep-me-too"]}}, indent=2) + "\n",
            encoding="utf-8",
        )

        first = run_cli("activate", "--workspace", str(self.workspace), "--targets", "configured")
        self.assertEqual(first["status"], "applied")
        self.assertTrue((self.workspace / ".opendream" / "agents.json").exists())
        self.assertTrue((self.workspace / ".opendream" / "hooks" / "claude-pre-task.sh").exists())
        self.assertTrue((self.workspace / ".opendream" / "bin" / "codex-task-wrapper.sh").exists())
        self.assertIn("claude-code", {item["target_kind"] for item in first["targets"]})
        self.assertIn("codex", {item["target_kind"] for item in first["targets"]})
        self.assertIn("openclaw", {item["target_kind"] for item in first["targets"]})

        second = run_cli("activate", "--workspace", str(self.workspace), "--targets", "configured")
        self.assertEqual(second["status"], "noop")

        damaged = self.workspace / ".opendream" / "hooks" / "codex-post-task.sh"
        damaged.unlink()
        doctor = run_cli("doctor", "--workspace", str(self.workspace), "--surface", "agents")
        self.assertEqual(doctor["status"], "needs-repair")
        self.assertIn("codex", doctor["drifted_targets"])

        repair = run_cli("activate", "--workspace", str(self.workspace), "--repair")
        self.assertEqual(repair["status"], "repaired")
        self.assertTrue(damaged.exists())

    def test_repair_shorthand_repairs_drift(self) -> None:
        codex_config = self.workspace / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True, exist_ok=True)
        codex_config.write_text('sandbox_mode = "workspace-write"\n', encoding="utf-8")

        run_cli("activate", "--workspace", str(self.workspace), "--targets", "configured")

        damaged = self.workspace / ".opendream" / "hooks" / "codex-post-task.sh"
        damaged.unlink()

        repair = run_cli("repair", "--workspace", str(self.workspace))
        self.assertEqual(repair["status"], "repaired")
        self.assertTrue(damaged.exists())

    def test_workspace_upgrade_repairs_and_refreshes_catalog(self) -> None:
        previous_catalog_home = os.environ.get("OPENDREAM_CATALOG_HOME")
        catalog_home = Path(self.temp_dir.name) / "catalog"
        os.environ["OPENDREAM_CATALOG_HOME"] = str(catalog_home)
        try:
            codex_config = self.workspace / ".codex" / "config.toml"
            codex_config.parent.mkdir(parents=True, exist_ok=True)
            codex_config.write_text('sandbox_mode = "workspace-write"\n', encoding="utf-8")

            run_cli("init", "--workspace", str(self.workspace), "--activate-configured")
            run_cli("workspace", "forget", "--workspace", str(self.workspace))

            damaged = self.workspace / ".opendream" / "hooks" / "codex-post-task.sh"
            damaged.unlink()

            upgraded = run_cli("workspace", "upgrade", "--workspace", str(self.workspace))
            self.assertEqual(upgraded["status"], "completed")
            self.assertEqual(upgraded["workspace_count"], 1)
            self.assertEqual(upgraded["upgraded_count"], 1)
            self.assertEqual(upgraded["skipped_count"], 0)
            self.assertEqual(len(upgraded["workspaces"]), 1)
            self.assertEqual(upgraded["workspaces"][0]["status"], "completed")
            self.assertEqual(upgraded["workspaces"][0]["activation_repair_status"], "repaired")
            self.assertEqual(upgraded["workspaces"][0]["catalog_status_kind"], "ok")
            self.assertTrue(damaged.exists())

            refreshed = run_cli("workspace", "inspect", "--workspace", str(self.workspace))
            self.assertEqual(refreshed["status"], "ok")
            self.assertEqual(refreshed["entry"]["status_kind"], "ok")
        finally:
            if previous_catalog_home is None:
                os.environ.pop("OPENDREAM_CATALOG_HOME", None)
            else:
                os.environ["OPENDREAM_CATALOG_HOME"] = previous_catalog_home

    def test_top_level_upgrade_error_points_to_installer_and_workspace_refresh(self) -> None:
        completed = run_cli_raw("upgrade", "--workspace", str(self.workspace), check=False)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("uv tool upgrade opendream", completed.stderr)
        self.assertIn('opendream workspace upgrade --workspace "$PWD"', completed.stderr)

    def test_init_activate_configured_returns_activation_report(self) -> None:
        codex_config = self.workspace / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True, exist_ok=True)
        codex_config.write_text('sandbox_mode = "workspace-write"\n', encoding="utf-8")

        result = run_cli("init", "--workspace", str(self.workspace), "--activate-configured")
        self.assertEqual(result["status"], "initialized")
        self.assertEqual(result["activation"]["status"], "applied")
        self.assertTrue((self.workspace / "AGENTS.md").exists())
        self.assertTrue((self.workspace / ".opendream" / "agents.json").exists())
        self.assertTrue((self.workspace / ".opendream" / "targets.json").exists())
        self.assertTrue((self.workspace / ".opendream" / "activation-state.json").exists())

    def test_codex_agents_hook_instructions_skip_missing_hooks(self) -> None:
        codex_config = self.workspace / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True, exist_ok=True)
        codex_config.write_text('sandbox_mode = "workspace-write"\n', encoding="utf-8")

        run_cli("init", "--workspace", str(self.workspace), "--activate-configured")
        agents_text = (self.workspace / "AGENTS.md").read_text(encoding="utf-8")
        pre_cmd = (
            '[ -f .opendream/hooks/codex-pre-task.sh ] && '
            'sh .opendream/hooks/codex-pre-task.sh "${OPENDREAM_QUERY:-current task}" || true'
        )
        post_cmd = (
            '[ -f .opendream/hooks/codex-post-task.sh ] && '
            'sh .opendream/hooks/codex-post-task.sh "${OPENDREAM_SUMMARY:-Task completed.}" || true'
        )
        self.assertIn(pre_cmd, agents_text)
        self.assertIn(post_cmd, agents_text)

        (self.workspace / ".opendream" / "hooks" / "codex-pre-task.sh").unlink()
        completed = subprocess.run(
            ["sh", "-c", pre_cmd],
            cwd=self.workspace,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, "")

    def test_status_and_deactivate_round_trip_for_configured_target(self) -> None:
        codex_config = self.workspace / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True, exist_ok=True)
        codex_config.write_text('sandbox_mode = "workspace-write"\n', encoding="utf-8")

        run_cli("init", "--workspace", str(self.workspace), "--activate-configured")
        active = run_cli("status", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        self.assertEqual(active["overall_state"], "healthy")
        self.assertEqual(active["activation_state"]["status"], "active")
        self.assertEqual(active["targets"][0]["target_kind"], "codex")
        self.assertEqual(active["targets"][0]["state"], "active")

        removed = run_cli("deactivate", "--workspace", str(self.workspace))
        self.assertEqual(removed["status"], "deactivated")
        self.assertEqual(removed["deactivated_targets"], ["codex"])
        self.assertFalse((self.workspace / ".opendream" / "bin" / "codex-task-wrapper.sh").exists())

        after = run_cli("status", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        self.assertEqual(after["overall_state"], "inactive")
        self.assertEqual(after["activation_state"]["status"], "inactive")
        self.assertEqual(after["targets"][0]["state"], "configured")
        self.assertIn("opendream activate --workspace", after["next_action"])

        doctor = run_cli("doctor", "--workspace", str(self.workspace), "--surface", "agents")
        self.assertEqual(doctor["status"], "healthy")
        self.assertEqual(doctor["drifted_targets"], [])

    def test_codex_wrapper_preserves_exit_status(self) -> None:
        shim_path = self.write_opendream_shim()
        run_cli("init", "--workspace", str(self.workspace))
        run_cli("activate", "--workspace", str(self.workspace), "--targets", "codex")
        wrapper = self.workspace / ".opendream" / "bin" / "codex-task-wrapper.sh"
        env = {
            **os.environ,
            "PATH": f"{shim_path.parent}{os.pathsep}{os.environ.get('PATH', '')}",
            "PYTHONPATH": str(REPO_ROOT),
            "OPENDREAM_WORKSPACE": str(self.workspace),
            "OPENDREAM_QUERY": "verify wrapper path",
            "OPENDREAM_SUMMARY": "wrapper completed",
        }
        completed = subprocess.run(
            ["sh", str(wrapper), "--", "/bin/sh", "-c", "exit 7"],
            cwd=self.workspace,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 7)
        self.assertTrue((self.workspace / ".opendream" / "context" / "codex-pre-task.json").exists())
        self.assertTrue(any((self.workspace / DEFAULT_MEMORY_DIR / "state" / "events").glob("*.jsonl")))

    def test_claude_hooks_consume_native_stdin_payloads(self) -> None:
        shim_path = self.write_opendream_shim()
        run_cli("init", "--workspace", str(self.workspace))
        run_cli("activate", "--workspace", str(self.workspace), "--targets", "claude-code")
        env = {
            **os.environ,
            "PATH": f"{shim_path.parent}{os.pathsep}{os.environ.get('PATH', '')}",
            "PYTHONPATH": str(REPO_ROOT),
            "OPENDREAM_WORKSPACE": str(self.workspace),
            "CLAUDE_PROJECT_DIR": str(self.workspace),
        }

        pre_hook = self.workspace / ".opendream" / "hooks" / "claude-pre-task.sh"
        prompt_payload = {
            "session_id": "claude-session-1",
            "transcript_path": str(self.workspace / ".claude" / "projects" / "session.jsonl"),
            "cwd": str(self.workspace),
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Use the ledger-backed resolver in this task.",
        }
        pre = subprocess.run(
            ["sh", str(pre_hook)],
            cwd=self.workspace,
            env=env,
            input=json.dumps(prompt_payload),
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("Use the ledger-backed resolver", pre.stdout)
        context_text = (self.workspace / ".opendream" / "context" / "claude-pre-task.json").read_text(
            encoding="utf-8"
        )
        self.assertIn("Use the ledger-backed resolver", context_text)
        context_payload = json.loads(context_text)
        self.assertIn("prompt_context", context_payload)
        self.assertNotIn("suppressed", context_payload)

        transcript_path = self.workspace / ".claude" / "projects" / "session.jsonl"
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(
            "\n".join(
                [
                    json.dumps({"type": "user", "message": {"content": "Please fix the resolver."}}),
                    json.dumps(
                        {
                            "type": "assistant",
                            "message": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Implemented real Claude hook summary from the transcript.",
                                    }
                                ]
                            },
                        }
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        post_hook = self.workspace / ".opendream" / "hooks" / "claude-post-task.sh"
        stop_payload = {
            "session_id": "claude-session-1",
            "transcript_path": str(transcript_path),
            "cwd": str(self.workspace),
            "hook_event_name": "Stop",
        }
        subprocess.run(
            ["sh", str(post_hook)],
            cwd=self.workspace,
            env=env,
            input=json.dumps(stop_payload),
            check=True,
            capture_output=True,
            text=True,
        )
        event_path = next((self.workspace / DEFAULT_MEMORY_DIR / "state" / "events").glob("*.jsonl"))
        event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(event["content"], "Implemented real Claude hook summary from the transcript.")
        self.assertEqual(event["source"]["message_ref"], "claude-post-task")
        self.assertEqual(event["session_id"], "claude-session-1")
        self.assertEqual(event["reporting_agent"]["agent_id"], "claude-code")

    def test_activation_plan_does_not_write_files(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        codex_config = self.workspace / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True, exist_ok=True)
        codex_config.write_text('sandbox_mode = "workspace-write"\n', encoding="utf-8")
        plan = run_cli("activation-plan", "--workspace", str(self.workspace), "--targets", "codex")
        self.assertEqual(plan["selector"], "codex")
        self.assertEqual(plan["selected_targets"], ["codex"])
        self.assertFalse((self.workspace / ".opendream" / "hooks" / "codex-pre-task.sh").exists())

    def test_activate_cursor_gemini_and_github_copilot_round_trip(self) -> None:
        run_cli("init", "--workspace", str(self.workspace))
        for target in ("cursor", "gemini", "github-copilot"):
            applied = run_cli("activate", "--workspace", str(self.workspace), "--targets", target)
            self.assertIn(applied["status"], {"applied", "updated"})
        self.assertTrue((self.workspace / ".cursor" / "rules" / "opendream.mdc").exists())
        mdc = (self.workspace / ".cursor" / "rules" / "opendream.mdc").read_text(encoding="utf-8")
        self.assertIn("BEGIN OPENDREAM MANAGED BLOCK: cursor", mdc)
        self.assertIn("alwaysApply: true", mdc)
        self.assertTrue((self.workspace / "GEMINI.md").exists())
        self.assertIn(
            "BEGIN OPENDREAM MANAGED BLOCK: gemini",
            (self.workspace / "GEMINI.md").read_text(encoding="utf-8"),
        )
        copilot_path = self.workspace / ".github" / "copilot-instructions.md"
        self.assertTrue(copilot_path.exists())
        self.assertIn(
            "BEGIN OPENDREAM MANAGED BLOCK: github-copilot",
            copilot_path.read_text(encoding="utf-8"),
        )
        self.assertTrue((self.workspace / ".opendream" / "hooks" / "cursor-pre-task.sh").exists())
        self.assertTrue((self.workspace / ".opendream" / "hooks" / "gemini-post-task.sh").exists())
        self.assertTrue((self.workspace / ".opendream" / "hooks" / "github-copilot-pre-task.sh").exists())
        for hook_name in ("cursor-pre-task.sh", "gemini-pre-task.sh", "github-copilot-pre-task.sh"):
            hook_text = (self.workspace / ".opendream" / "hooks" / hook_name).read_text(
                encoding="utf-8"
            )
            self.assertIn("--output compact-json", hook_text)

        removed = run_cli("deactivate", "--workspace", str(self.workspace), "--targets", "all-supported")
        self.assertEqual(removed["status"], "deactivated")
        self.assertFalse((self.workspace / ".opendream" / "hooks" / "cursor-pre-task.sh").exists())
        if copilot_path.exists():
            self.assertNotIn(
                "OPENDREAM MANAGED BLOCK",
                copilot_path.read_text(encoding="utf-8"),
            )

    def test_activate_all_supported_installs_all_surfaces(self) -> None:
        claude_settings = self.workspace / ".claude" / "settings.json"
        claude_settings.parent.mkdir(parents=True, exist_ok=True)
        claude_settings.write_text("{}", encoding="utf-8")
        codex_config = self.workspace / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True, exist_ok=True)
        codex_config.write_text('sandbox_mode = "workspace-write"\n', encoding="utf-8")
        openclaw_config = self.workspace / ".openclaw" / "config.json"
        openclaw_config.parent.mkdir(parents=True, exist_ok=True)
        openclaw_config.write_text("{}", encoding="utf-8")
        run_cli("init", "--workspace", str(self.workspace))
        report = run_cli("activate", "--workspace", str(self.workspace), "--targets", "all-supported")
        self.assertEqual(report["status"], "applied")
        kinds = {item["target_kind"] for item in report["targets"]}
        self.assertEqual(
            kinds,
            {
                "claude-code",
                "codex",
                "openclaw",
                "cursor",
                "gemini",
                "github-copilot",
            },
        )


if __name__ == "__main__":
    unittest.main()
