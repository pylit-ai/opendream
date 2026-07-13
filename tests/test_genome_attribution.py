from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENOME_HASH = "b" * 64


class GenomeAttributionTests(unittest.TestCase):
    def _run(self, *args: str) -> dict[str, object]:
        completed = subprocess.run(
            [sys.executable, "-m", "opendream.cli", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def test_emit_event_and_prepared_context_preserve_genome_hash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            self._run("init", "--workspace", str(workspace))
            emitted = self._run(
                "emit-event",
                "--workspace",
                str(workspace),
                "--kind",
                "task_outcome",
                "--content",
                "Completed the contract inventory.",
                "--message-ref",
                "task-1",
                "--agent-id",
                "codex",
                "--agent-genome-hash",
                GENOME_HASH,
                "--timestamp",
                "2026-07-12T12:00:00Z",
            )
            context = self._run(
                "prepare-context",
                "--workspace",
                str(workspace),
                "--query",
                "contract inventory",
                "--agent-id",
                "codex",
                "--agent-genome-hash",
                GENOME_HASH,
                "--now",
                "2026-07-12T12:01:00Z",
            )

            event_path = workspace / str(emitted["event_path"])
            event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[-1])
            context_path = workspace / ".opendream" / "memory" / "audit" / "context" / f"{context['context_id']}.json"
            context_audit = json.loads(context_path.read_text(encoding="utf-8"))

        self.assertEqual(event["reporting_agent"]["genome_hash"], GENOME_HASH)
        self.assertEqual(context_audit["reporting_agent"]["genome_hash"], GENOME_HASH)


if __name__ == "__main__":
    unittest.main()
