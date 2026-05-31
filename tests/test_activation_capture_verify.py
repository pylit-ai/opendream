from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from opendream.adapter_loader import load_bundled_adapters

REPO_ROOT = Path(__file__).resolve().parents[1]


class ActivationCaptureVerifyTests(unittest.TestCase):
    def run_cli(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "opendream.cli", *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

    def sandbox_env(self, temp_path: Path) -> dict[str, str]:
        bin_dir = temp_path / "bin"
        bin_dir.mkdir()
        opendream_bin = bin_dir / "opendream"
        opendream_bin.write_text(
            "#!/bin/sh\n"
            f"exec {shlex.quote(sys.executable)} -m opendream.cli \"$@\"\n",
            encoding="utf-8",
        )
        opendream_bin.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        env["OPENDREAM_BIN"] = str(opendream_bin)
        env["OPENDREAM_CATALOG_DISABLE"] = "1"
        env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
        return env

    def configure_target_marker(self, workspace: Path, target: str) -> None:
        if target == "claude-code":
            (workspace / ".claude").mkdir(parents=True, exist_ok=True)
            (workspace / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
            return
        if target == "codex":
            (workspace / ".codex").mkdir(parents=True, exist_ok=True)
            return
        if target == "cursor":
            (workspace / ".cursor").mkdir(parents=True, exist_ok=True)
            return
        if target == "gemini":
            (workspace / "GEMINI.md").write_text("# Gemini\n", encoding="utf-8")
            return
        if target == "github-copilot":
            (workspace / ".github").mkdir(parents=True, exist_ok=True)
            (workspace / ".github" / "copilot-instructions.md").write_text(
                "# Copilot\n", encoding="utf-8"
            )
            return
        if target == "openclaw":
            (workspace / ".openclaw").mkdir(parents=True, exist_ok=True)
            (workspace / ".openclaw" / "config.json").write_text("{}\n", encoding="utf-8")
            return
        raise AssertionError(f"test fixture lacks marker support for bundled target: {target}")

    def load_json(self, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIsInstance(payload, dict)
        return payload

    def load_events(self, workspace: Path) -> list[dict[str, object]]:
        events_dir = workspace / ".opendream" / "memory" / "state" / "events"
        events: list[dict[str, object]] = []
        for path in sorted(events_dir.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(json.loads(line))
        return events

    def assert_capture_passed(self, workspace: Path, payload: dict[str, object], target: str) -> None:
        self.assertEqual(payload["status"], "passed", payload)
        self.assertEqual(payload["selected_targets"], [target])
        self.assertGreaterEqual(int(payload["event_delta"]), 1)
        self.assertGreaterEqual(int(payload["durable_record_delta"]), 1)
        latest = workspace / ".opendream" / "reports" / "activation-capture-latest.json"
        self.assertTrue(latest.is_file())
        results = payload["results"]
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["target_kind"], target)
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["pre_context_ok"])
        self.assertTrue(result["post_capture_ok"])
        if target == "claude-code":
            settings = json.loads((workspace / ".claude" / "settings.json").read_text(encoding="utf-8"))
            self.assertIn("UserPromptSubmit", settings["hooks"])
            self.assertIn("Stop", settings["hooks"])
        elif target == "codex":
            self.assertTrue((workspace / ".opendream" / "bin" / "codex-task-wrapper.sh").is_file())
        elif target in {"cursor", "gemini", "github-copilot"}:
            self.assertTrue(result["instruction_only"])
            self.assertEqual(result["host_invocation"], "instruction-only")
        elif target == "openclaw":
            self.assertTrue((workspace / ".openclaw" / "opendream-event-map.md").is_file())

    def test_activation_capture_verifies_every_supported_adapter_in_sandbox(self) -> None:
        targets = sorted(load_bundled_adapters())
        for target in targets:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                temp_path = Path(tmp)
                workspace = temp_path / "workspace"
                workspace.mkdir()
                env = self.sandbox_env(temp_path)
                self.configure_target_marker(workspace, target)

                self.load_json(self.run_cli("init", "--workspace", str(workspace), env=env))
                self.load_json(
                    self.run_cli(
                        "activate",
                        "--workspace",
                        str(workspace),
                        "--targets",
                        target,
                        env=env,
                    )
                )
                doctor = self.load_json(
                    self.run_cli("doctor", "--workspace", str(workspace), "--surface", "agents", env=env)
                )
                self.assertIn(target, doctor["activated_targets"])

                verify = self.load_json(
                    self.run_cli(
                        "verify",
                        "activation-capture",
                        "--workspace",
                        str(workspace),
                        "--targets",
                        target,
                        env=env,
                    )
                )
                self.assert_capture_passed(workspace, verify, target)

                event_refs = {
                    str(event.get("source", {}).get("message_ref"))
                    for event in self.load_events(workspace)
                }
                self.assertIn(f"activation-capture:{target}", event_refs)

    def test_all_supported_selector_covers_manifest_ids(self) -> None:
        targets = sorted(load_bundled_adapters())
        with tempfile.TemporaryDirectory() as tmp:
            temp_path = Path(tmp)
            workspace = temp_path / "workspace"
            workspace.mkdir()
            env = self.sandbox_env(temp_path)
            for target in targets:
                self.configure_target_marker(workspace, target)

            self.load_json(self.run_cli("init", "--workspace", str(workspace), env=env))
            self.load_json(
                self.run_cli(
                    "activate",
                    "--workspace",
                    str(workspace),
                    "--targets",
                    "all-supported",
                    env=env,
                )
            )
            verify = self.load_json(
                self.run_cli(
                    "verify",
                    "activation-capture",
                    "--workspace",
                    str(workspace),
                    "--targets",
                    "all-supported",
                    env=env,
                )
            )
            self.assertEqual(verify["status"], "passed", verify)
            self.assertEqual(verify["selected_targets"], targets)
            self.assertEqual(
                sorted(result["target_kind"] for result in verify["results"]),
                targets,
            )
            events = self.load_events(workspace)
            for target in targets:
                matches = [
                    event
                    for event in events
                    if event.get("source", {}).get("message_ref") == f"activation-capture:{target}"
                ]
                self.assertTrue(matches, target)
                self.assertIn("diagnostic:activation-capture", matches[-1].get("tags", []))

    def test_configured_selector_only_verifies_configured_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_path = Path(tmp)
            workspace = temp_path / "workspace"
            workspace.mkdir()
            env = self.sandbox_env(temp_path)
            self.configure_target_marker(workspace, "codex")

            self.load_json(self.run_cli("init", "--workspace", str(workspace), env=env))
            self.load_json(
                self.run_cli(
                    "activate",
                    "--workspace",
                    str(workspace),
                    "--targets",
                    "configured",
                    env=env,
                )
            )
            verify = self.load_json(
                self.run_cli(
                    "verify",
                    "activation-capture",
                    "--workspace",
                    str(workspace),
                    "--targets",
                    "configured",
                    env=env,
                )
            )
            self.assertEqual(verify["selected_targets"], ["codex"])
            self.assertEqual(verify["status"], "passed", verify)

    def test_missing_hook_script_fails_with_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_path = Path(tmp)
            workspace = temp_path / "workspace"
            workspace.mkdir()
            env = self.sandbox_env(temp_path)
            self.configure_target_marker(workspace, "codex")

            self.load_json(self.run_cli("init", "--workspace", str(workspace), env=env))
            self.load_json(
                self.run_cli(
                    "activate",
                    "--workspace",
                    str(workspace),
                    "--targets",
                    "codex",
                    env=env,
                )
            )
            (workspace / ".opendream" / "bin" / "codex-task-wrapper.sh").unlink()
            result = self.run_cli(
                "verify",
                "activation-capture",
                "--workspace",
                str(workspace),
                "--targets",
                "codex",
                env=env,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "failed")
            self.assertIn("activate --workspace", payload["next_action"])
            self.assertIn("missing activation surface", payload["results"][0]["warnings"][0])

    def test_uninitialized_workspace_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_path = Path(tmp)
            workspace = temp_path / "workspace"
            workspace.mkdir()
            env = self.sandbox_env(temp_path)
            result = self.run_cli(
                "verify",
                "activation-capture",
                "--workspace",
                str(workspace),
                "--targets",
                "codex",
                env=env,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "failed")
            self.assertIn("workspace is not initialized", payload["warnings"])
            self.assertIn("opendream init --workspace", payload["next_action"])

    def test_direct_hook_wrong_cwd_has_workspace_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_path = Path(tmp)
            workspace = temp_path / "workspace"
            workspace.mkdir()
            other = temp_path / "other"
            other.mkdir()
            env = self.sandbox_env(temp_path)
            self.configure_target_marker(workspace, "codex")

            self.load_json(self.run_cli("init", "--workspace", str(workspace), env=env))
            self.load_json(
                self.run_cli(
                    "activate",
                    "--workspace",
                    str(workspace),
                    "--targets",
                    "codex",
                    env=env,
                )
            )
            hook = workspace / ".opendream" / "hooks" / "codex-post-task.sh"
            result = subprocess.run(
                ["sh", str(hook), "summary"],
                cwd=other,
                env={key: value for key, value in env.items() if key != "OPENDREAM_WORKSPACE"},
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("run from workspace root or set OPENDREAM_WORKSPACE", result.stderr)

    def test_codex_hooks_share_and_clear_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_path = Path(tmp)
            workspace = temp_path / "workspace"
            workspace.mkdir()
            env = self.sandbox_env(temp_path)
            self.configure_target_marker(workspace, "codex")

            self.load_json(self.run_cli("init", "--workspace", str(workspace), env=env))
            self.load_json(
                self.run_cli(
                    "activate",
                    "--workspace",
                    str(workspace),
                    "--targets",
                    "codex",
                    env=env,
                )
            )
            pre_hook = workspace / ".opendream" / "hooks" / "codex-pre-task.sh"
            post_hook = workspace / ".opendream" / "hooks" / "codex-post-task.sh"
            active_session_path = workspace / ".opendream" / "memory" / ".active_session"

            pre = subprocess.run(
                ["sh", str(pre_hook), "Investigate Redis retry behavior"],
                cwd=workspace,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(pre.returncode, 0, pre.stderr)
            context_path = workspace / ".opendream" / "context" / "codex-pre-task.json"
            context = json.loads(context_path.read_text(encoding="utf-8"))
            session_id = str(context["session_id"])
            self.assertTrue(session_id)
            self.assertEqual(active_session_path.read_text(encoding="utf-8").strip(), session_id)

            post = subprocess.run(
                ["sh", str(post_hook), "Redis retry behavior fixed."],
                cwd=workspace,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(post.returncode, 0, post.stderr)
            self.assertFalse(active_session_path.exists())
            captured = [
                event
                for event in self.load_events(workspace)
                if event.get("message_ref") == "codex-post-task"
                or event.get("source", {}).get("message_ref") == "codex-post-task"
            ]
            self.assertTrue(captured)
            self.assertEqual(captured[-1]["session_id"], session_id)

    def test_codex_wrapper_preserves_child_exit_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_path = Path(tmp)
            workspace = temp_path / "workspace"
            workspace.mkdir()
            env = self.sandbox_env(temp_path)
            self.configure_target_marker(workspace, "codex")

            self.load_json(self.run_cli("init", "--workspace", str(workspace), env=env))
            self.load_json(
                self.run_cli(
                    "activate",
                    "--workspace",
                    str(workspace),
                    "--targets",
                    "codex",
                    env=env,
                )
            )
            wrapper = workspace / ".opendream" / "bin" / "codex-task-wrapper.sh"
            result = subprocess.run(
                ["sh", str(wrapper), "--summary", "wrapper exit test", "--", "/bin/sh", "-c", "exit 3"],
                cwd=workspace,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            self.assertEqual(result.returncode, 3, result.stderr)

    def test_verify_help_lists_verification_targets(self) -> None:
        top = self.run_cli("verify", "--help")
        self.assertEqual(top.returncode, 0, top.stderr)
        for phrase in (
            "activation-capture",
            "memory-quality",
            "performance",
            "runtime",
            "release",
        ):
            self.assertIn(phrase, top.stdout)
        capture = self.run_cli("verify", "activation-capture", "--help")
        self.assertEqual(capture.returncode, 0, capture.stderr)
        self.assertIn("--targets", capture.stdout)
        self.assertIn("all-supported", capture.stdout)


if __name__ == "__main__":
    unittest.main()
