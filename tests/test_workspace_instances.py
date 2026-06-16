from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from opendream import workspace_catalog, workspace_instances
from opendream.storage import MemoryStore


class WorkspaceInstanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="od-inst-")
        self.catalog_home = Path(self.tmpdir) / "catalog"
        self.workspace_root = Path(self.tmpdir) / "workspaces"
        self.workspace_root.mkdir(parents=True)
        self._prev_env = os.environ.get("OPENDREAM_CATALOG_HOME")
        os.environ["OPENDREAM_CATALOG_HOME"] = str(self.catalog_home)

    def tearDown(self) -> None:
        if self._prev_env is None:
            os.environ.pop("OPENDREAM_CATALOG_HOME", None)
        else:
            os.environ["OPENDREAM_CATALOG_HOME"] = self._prev_env
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_workspace(self, name: str) -> Path:
        workspace = self.workspace_root / name
        workspace.mkdir(parents=True, exist_ok=True)
        MemoryStore(workspace).initialize(store_kind="project")
        return workspace

    def test_current_context_finds_initialized_ancestor(self) -> None:
        workspace = self._make_workspace("alpha")
        child = workspace / "src" / "pkg"
        child.mkdir(parents=True)

        context = workspace_instances.resolve_current_context(child)

        self.assertEqual(context["status"], "workspace")
        self.assertEqual(context["workspace_path"], str(workspace.resolve()))
        self.assertEqual(context["source"], "ancestor")

    def test_current_context_uninitialized_does_not_create_workspace_state(self) -> None:
        current = self.workspace_root / "not-yet"
        current.mkdir()

        context = workspace_instances.resolve_current_context(current)

        self.assertEqual(context["status"], "not_initialized")
        self.assertTrue(context["not_initialized"])
        self.assertFalse((current / ".opendream").exists())

    def test_instance_state_marks_dead_owned_process_stale(self) -> None:
        workspace = self._make_workspace("beta")
        workspace_catalog.upsert_entry(workspace, discovered_by="init")
        workspace_instances.save_registry(
            {
                "version": 1,
                "instances": [
                    {
                        "workspace_path": str(workspace.resolve()),
                        "host": "127.0.0.1",
                        "port": 9,
                        "pid": 99999999,
                        "owned": True,
                    }
                ],
            }
        )

        state = workspace_instances.instance_state(workspace)

        self.assertEqual(state["state"], "stale")
        self.assertTrue(state["owned"])

    def test_stop_refuses_unmanaged_instance(self) -> None:
        workspace = self._make_workspace("gamma")
        workspace_instances.save_registry(
            {
                "version": 1,
                "instances": [
                    {
                        "workspace_path": str(workspace.resolve()),
                        "host": "127.0.0.1",
                        "port": 9,
                        "pid": 99999999,
                        "owned": False,
                    }
                ],
            }
        )

        with self.assertRaises(ValueError):
            workspace_instances.stop_workspace(workspace)


if __name__ == "__main__":
    unittest.main()
