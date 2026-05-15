from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from opendream.util import SCHEMA_ROOT, canonical_schema_path
from opendream.validation import required_schema_files

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = "2026-03-26T12:00:00Z"


class ReleaseArtifactTests(unittest.TestCase):
    def test_schema_assets_are_present_and_consistent(self) -> None:
        for schema_name in required_schema_files():
            package_schema = SCHEMA_ROOT / schema_name
            canonical_schema = canonical_schema_path(schema_name)
            self.assertTrue(package_schema.exists(), schema_name)
            self.assertTrue(canonical_schema.exists(), schema_name)

            package_payload = json.loads(package_schema.read_text(encoding="utf-8"))
            canonical_payload = json.loads(canonical_schema.read_text(encoding="utf-8"))
            self.assertEqual(package_payload, canonical_payload, schema_name)

    def test_clean_venv_install_and_demo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            venv_dir = temp_path / "venv"
            workspace = temp_path / "demo-workspace"
            dream_workspace = temp_path / "dream-workspace"
            eval_workspace = temp_path / "eval-workspace"
            transcript_fixture = temp_path / "transcript.jsonl"
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            scripts_dir = "Scripts" if os.name == "nt" else "bin"
            venv_python = venv_dir / scripts_dir / "python"
            entrypoint = venv_dir / scripts_dir / "opendream"
            transcript_fixture.write_text(
                (
                    '{"timestamp":"2026-03-26T09:00:00Z","speaker":"user","text":"Use pnpm in this repo."}\n'
                    '{"timestamp":"2026-03-26T09:15:00Z","speaker":"assistant","text":"Schema migration workflow: '
                    'generate the SQL first, then apply it after review."}\n'
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "--no-deps", str(REPO_ROOT)],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            help_run = subprocess.run(
                [str(entrypoint), "--help"],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("opendream", help_run.stdout)
            self.assertIn("deactivate", help_run.stdout)
            self.assertIn('opendream status --workspace "$PWD"', help_run.stdout)

            demo_run = subprocess.run(
                [str(entrypoint), "demo", "--workspace", str(workspace), "--now", FIXED_NOW],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"events_appended": 20', demo_run.stdout)
            self.assertTrue((workspace / ".opendream" / "memory" / "MEMORY.md").exists())

            dream_run = subprocess.run(
                [
                    str(entrypoint),
                    "dream",
                    "run",
                    "--workspace",
                    str(dream_workspace),
                    "--episodes",
                    str(transcript_fixture),
                    "--now",
                    FIXED_NOW,
                    "--compat-mode",
                    "autodream",
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "completed"', dream_run.stdout)

            dream_enqueue = subprocess.run(
                [
                    str(entrypoint),
                    "dream",
                    "enqueue",
                    "--workspace",
                    str(dream_workspace),
                    "--episodes",
                    str(transcript_fixture),
                    "--now",
                    FIXED_NOW,
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "queued"', dream_enqueue.stdout)

            dream_worker = subprocess.run(
                [
                    str(entrypoint),
                    "dream",
                    "worker",
                    "--workspace",
                    str(dream_workspace),
                    "--now",
                    FIXED_NOW,
                    "--memory-dir",
                    ".dream-memory",
                    "--once",
                    "--max-jobs-per-poll",
                    "1",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "completed"', dream_worker.stdout)

            service_install = subprocess.run(
                [
                    str(entrypoint),
                    "install-service",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                    "--install-root",
                    str(temp_path / "services"),
                    "--interval-seconds",
                    "0.2",
                    "--no-start",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "installed"', service_install.stdout)

            service_start = subprocess.run(
                [
                    str(entrypoint),
                    "service",
                    "start",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"running": true', service_start.stdout)
            time.sleep(0.5)

            service_status = subprocess.run(
                [
                    str(entrypoint),
                    "service",
                    "status",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"installed": true', service_status.stdout)
            self.assertIn('"running": true', service_status.stdout)

            service_restart = subprocess.run(
                [
                    str(entrypoint),
                    "service",
                    "restart",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "restarted"', service_restart.stdout)

            service_stop = subprocess.run(
                [
                    str(entrypoint),
                    "service",
                    "stop",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"running": false', service_stop.stdout)

            service_uninstall = subprocess.run(
                [
                    str(entrypoint),
                    "uninstall-service",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                    "--purge",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "uninstalled"', service_uninstall.stdout)

            (dream_workspace / ".claude").mkdir(parents=True, exist_ok=True)
            (dream_workspace / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
            (dream_workspace / ".codex").mkdir(parents=True, exist_ok=True)
            (dream_workspace / ".codex" / "config.toml").write_text(
                'sandbox_mode = "workspace-write"\n',
                encoding="utf-8",
            )
            (dream_workspace / ".openclaw").mkdir(parents=True, exist_ok=True)
            (dream_workspace / ".openclaw" / "config.json").write_text("{}", encoding="utf-8")

            activation = subprocess.run(
                [
                    str(entrypoint),
                    "activate",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                    "--targets",
                    "configured",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "applied"', activation.stdout)

            doctor = subprocess.run(
                [
                    str(entrypoint),
                    "doctor",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                    "--surface",
                    "agents",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "healthy"', doctor.stdout)

            compressed_status = subprocess.run(
                [
                    str(entrypoint),
                    "status",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"overall_state": "healthy"', compressed_status.stdout)

            deactivate = subprocess.run(
                [
                    str(entrypoint),
                    "deactivate",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "deactivated"', deactivate.stdout)

            inactive_status = subprocess.run(
                [
                    str(entrypoint),
                    "status",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"overall_state": "inactive"', inactive_status.stdout)

            reactivation = subprocess.run(
                [
                    str(entrypoint),
                    "activate",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                    "--targets",
                    "configured",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "updated"', reactivation.stdout)

            codex_wrapper = subprocess.run(
                [
                    "sh",
                    str(dream_workspace / ".opendream" / "bin" / "codex-task-wrapper.sh"),
                    "--summary",
                    "release smoke wrapper",
                    "--",
                    "/bin/sh",
                    "-c",
                    "exit 3",
                ],
                cwd=dream_workspace,
                check=False,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PATH": f"{venv_dir / scripts_dir}{os.pathsep}{os.environ.get('PATH', '')}",
                    "OPENDREAM_WORKSPACE": str(dream_workspace),
                    "OPENDREAM_QUERY": "release smoke query",
                },
            )
            self.assertEqual(codex_wrapper.returncode, 3)

            fidelity_eval = subprocess.run(
                [
                    str(entrypoint),
                    "eval",
                    "dream-fidelity",
                    "--workspace",
                    str(eval_workspace),
                    "--now",
                    FIXED_NOW,
                    "--compat-mode",
                    "autodream",
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "passed"', fidelity_eval.stdout)
            fidelity_payload = json.loads(fidelity_eval.stdout)
            self.assertEqual(fidelity_payload["boundary_enforcement"]["violations"], [])
            self.assertEqual(fidelity_payload["boundary_enforcement"]["blocked_code_writes"], [])

    def test_public_docs_do_not_contain_license_contradictions(self) -> None:
        forbidden = (
            "proprietary " "license",
            "all rights " "reserved",
            "not offered under an " "open-source license",
        )
        roots = [
            REPO_ROOT / "README.md",
            REPO_ROOT / "docs",
            *REPO_ROOT.glob("*.md"),
        ]
        hits: list[str] = []
        for root in roots:
            paths = [root] if root.is_file() else list(root.rglob("*.md"))
            for path in paths:
                rel = path.relative_to(REPO_ROOT).as_posix()
                text = path.read_text(encoding="utf-8").lower()
                for term in forbidden:
                    if term in text:
                        hits.append(f"{rel}: {term}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
