from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from opendream.consolidator import consolidate
from opendream.storage import MemoryStore
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

    def test_demo_creates_reproducible_artifacts(self) -> None:
        result = run_cli("demo", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        memory_root = self.workspace / "memory"
        self.assertTrue((memory_root / "MEMORY.md").exists())
        self.assertTrue((memory_root / "state" / "durable_records.json").exists())
        self.assertTrue(any((memory_root / "topics").glob("*.md")))
        self.assertTrue(any((memory_root / "audit" / "consolidation").glob("*.diff")))
        self.assertGreater(result["extract"]["created_candidates"], 0)
        self.assertGreater(len(result["retrieve"]["selected_memory_ids"]), 0)

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
        self.assertEqual(len(list((self.workspace / "memory" / "topics").glob("*.md"))), 0)
        reports = list((self.workspace / "memory" / "audit" / "bootstrap").glob("*.json"))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(report["raw_only_ids"]), 1)
        self.assertGreaterEqual(len(report["quarantine_ids"]), 1)

    def test_init_persists_store_kind_metadata(self) -> None:
        project_result = run_cli("init", "--workspace", str(self.workspace))
        global_result = run_cli("init", "--workspace", str(self.global_workspace), "--store-kind", "global")

        project_store = json.loads((self.workspace / "memory" / "state" / "store.json").read_text(encoding="utf-8"))
        global_store = json.loads(
            (self.global_workspace / "memory" / "state" / "store.json").read_text(encoding="utf-8")
        )

        self.assertEqual(project_result["store_kind"], "project")
        self.assertEqual(global_result["store_kind"], "global")
        self.assertEqual(project_store["store_kind"], "project")
        self.assertEqual(global_store["store_kind"], "global")

    def test_deterministic_consolidation_and_schema_validation(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
        run_cli("append-event", "--workspace", str(self.workspace), "--events", str(fixture))
        run_cli("extract", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        first = run_cli("consolidate", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        durable_before = (self.workspace / "memory" / "state" / "durable_records.json").read_text(encoding="utf-8")
        index_before = (self.workspace / "memory" / "MEMORY.md").read_text(encoding="utf-8")
        second = run_cli("consolidate", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        durable_after = (self.workspace / "memory" / "state" / "durable_records.json").read_text(encoding="utf-8")
        index_after = (self.workspace / "memory" / "MEMORY.md").read_text(encoding="utf-8")

        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["created"], 0)
        self.assertEqual(durable_before, durable_after)
        self.assertEqual(index_before, index_after)

        records = json.loads(durable_after)
        for record in records:
            validate_document("memory-topic.schema.json", record)
        index = json.loads((self.workspace / "memory" / "state" / "index.json").read_text(encoding="utf-8"))
        validate_document("memory-index.schema.json", index)
        audit_file = next((self.workspace / "memory" / "audit" / "consolidation").glob("*.jsonl"))
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
                (self.workspace / "memory" / "state" / "durable_records.json").read_text(encoding="utf-8")
            )
        }
        selected_titles = {records[memory_id]["title"] for memory_id in retrieval["selected_memory_ids"]}
        self.assertIn("Preference: package-manager", selected_titles)
        self.assertIn("Environment: redis", selected_titles)
        self.assertIn("Workflow: schema-migration", selected_titles)
        self.assertTrue(any((self.workspace / "memory" / "audit" / "retrieval").glob("*.json")))

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
        self.assertFalse((self.workspace / "memory" / "locks" / "consolidator.lock").exists())

    def test_memory_commands_write_only_inside_memory_store(self) -> None:
        fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
        run_cli("append-event", "--workspace", str(self.workspace), "--events", str(fixture))
        run_cli("extract", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        run_cli("consolidate", "--workspace", str(self.workspace), "--now", FIXED_NOW)

        non_memory_files = [path for path in self.workspace.rglob("*") if path.is_file() and "memory" not in path.parts]
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
        event_files = list((self.workspace / "memory" / "state" / "events").glob("*.jsonl"))
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
        self.assertFalse((self.workspace / "memory").exists())

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
        self.assertFalse((self.workspace / "memory" / "state" / "events").exists())
        event_files = list((self.global_workspace / "memory" / "state" / "events").glob("*.jsonl"))
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
        lock_path = self.workspace / "memory" / "locks" / "consolidator.lock"
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
        lock_path = self.workspace / "memory" / "locks" / "dream.lock"
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

    def test_service_autowire_is_idempotent_and_reversible(self) -> None:
        claude_settings = self.workspace / ".claude" / "settings.json"
        claude_settings.parent.mkdir(parents=True, exist_ok=True)
        claude_settings.write_text(
            json.dumps({"hooks": {"preTask": ["echo keep-me"], "postTask": ["echo keep-me-too"]}}, indent=2) + "\n",
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
        self.assertEqual(
            settings_payload["hooks"]["preTask"].count('sh .opendream/hooks/claude-pre-task.sh "$CLAUDE_TASK"'),
            1,
        )
        self.assertEqual(
            settings_payload["hooks"]["postTask"].count('sh .opendream/hooks/claude-post-task.sh "$CLAUDE_SUMMARY"'),
            1,
        )

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
        claude_settings.write_text(
            json.dumps({"hooks": {"preTask": ["echo keep-me"]}}, indent=2) + "\n",
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
        self.assertTrue(any((self.workspace / "memory" / "state" / "events").glob("*.jsonl")))


if __name__ == "__main__":
    unittest.main()
