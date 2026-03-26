from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from opendream_memory.consolidator import consolidate
from opendream_memory.storage import MemoryStore
from opendream_memory.validation import validate_document


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = "2026-03-26T12:00:00Z"


def run_cli(*args: str, cwd: Path | None = None) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-m", "opendream_memory.cli", *args],
        cwd=cwd or REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


class MemoryCliIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_demo_creates_reproducible_artifacts(self) -> None:
        result = run_cli("demo", "--workspace", str(self.workspace), "--now", FIXED_NOW)
        memory_root = self.workspace / "memory"
        self.assertTrue((memory_root / "MEMORY.md").exists())
        self.assertTrue((memory_root / "state" / "durable_records.json").exists())
        self.assertTrue(any((memory_root / "topics").glob("*.md")))
        self.assertTrue(any((memory_root / "audit" / "consolidation").glob("*.diff")))
        self.assertGreater(result["extract"]["created_candidates"], 0)
        self.assertGreater(len(result["retrieve"]["selected_memory_ids"]), 0)

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
            for record in json.loads((self.workspace / "memory" / "state" / "durable_records.json").read_text(encoding="utf-8"))
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


if __name__ == "__main__":
    unittest.main()
