from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from opendream.provider_registry import check_provider_health


class NoNetworkDefaultsTests(unittest.TestCase):
    def run_cli(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "opendream.cli", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

    def test_default_demo_runs_without_api_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli("demo", "--workspace", tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["consolidate"]["status"], "completed")
        self.assertGreater(payload["events_appended"], 0)

    def test_status_uninitialized_is_actionable_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli("status", "--workspace", tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["initialized"])
        self.assertIn("opendream init", payload["next_action"])

    def test_provider_health_reports_setup_required_without_api_call(self) -> None:
        calls: list[object] = []

        def fail_socket(*args: object, **kwargs: object) -> socket.socket:
            calls.append((args, kwargs))
            raise AssertionError("network call attempted")

        provider = {"provider_id": "openai-default", "transport": "openai", "model_id": "gpt-test"}
        with patch.dict("os.environ", {}, clear=True), patch("socket.create_connection", fail_socket):
            result = check_provider_health(provider)
        self.assertEqual(result["health_status"], "unavailable")
        self.assertIn("OPENAI_API_KEY not set", result["issues"])
        self.assertEqual(calls, [])

    def test_runtime_sources_do_not_ship_hidden_telemetry_clients(self) -> None:
        root = Path(__file__).resolve().parents[1] / "opendream"
        forbidden = ("posthog", "segment", "sentry_sdk", "analytics")
        hits: list[str] = []
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                if marker in text.lower():
                    hits.append(f"{path.relative_to(root)}:{marker}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
