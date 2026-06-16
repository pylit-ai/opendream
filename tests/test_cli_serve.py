from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from opendream import cli


class _FakeServer:
    server_address = ("127.0.0.1", 43210)

    def serve_forever(self) -> None:
        return

    def server_close(self) -> None:
        return


class ServeCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="od-serve-")
        self.catalog_home = Path(self.tmpdir) / "catalog"
        self._prev_env = os.environ.get("OPENDREAM_CATALOG_HOME")
        os.environ["OPENDREAM_CATALOG_HOME"] = str(self.catalog_home)
        self._old_cwd = Path.cwd()

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)
        if self._prev_env is None:
            os.environ.pop("OPENDREAM_CATALOG_HOME", None)
        else:
            os.environ["OPENDREAM_CATALOG_HOME"] = self._prev_env
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_serve(self, *argv: str) -> tuple[dict[str, object], dict[str, object]]:
        parser = cli.build_parser()
        args = parser.parse_args(["serve", "--no-open", "--json", *argv])
        buf = io.StringIO()
        with patch("opendream.cli.build_server", return_value=_FakeServer()), contextlib.redirect_stdout(buf):
            result = args.func(args)
        text = buf.getvalue()
        start = text.find("{")
        if start < 0:
            self.fail(f"expected JSON output, got: {text!r}")
        payload, _end = json.JSONDecoder().raw_decode(text[start:])
        return payload, result

    def test_serve_from_uninitialized_directory_opens_hub_without_init(self) -> None:
        current = Path(self.tmpdir) / "plain"
        current.mkdir()
        os.chdir(current)

        serving, result = self._run_serve()

        self.assertEqual(serving["kind"], "hub")
        self.assertEqual(serving["current_context"]["status"], "not_initialized")
        self.assertTrue(serving["url"].endswith("/workspaces"))
        self.assertEqual(result["status"], "stopped")
        self.assertFalse((current / ".opendream").exists())

    def test_serve_with_explicit_workspace_preserves_initializing_semantics(self) -> None:
        workspace = Path(self.tmpdir) / "workspace"
        workspace.mkdir()

        serving, _result = self._run_serve("--workspace", str(workspace))

        self.assertEqual(serving["kind"], "workspace")
        self.assertEqual(serving["workspace"], str(workspace.resolve()))
        self.assertTrue((workspace / ".opendream" / "memory" / "state" / "store.json").exists())


if __name__ == "__main__":
    unittest.main()
