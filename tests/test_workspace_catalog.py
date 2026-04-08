"""Tests for the machine-local workspace catalog and dashboard.

See ``openspec/changes/441-workspace-catalog-dashboard-bundle``.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from opendream import workspace_catalog
from opendream.cli import build_parser
from opendream.storage import MemoryStore
from opendream.webapp import _workspace_dashboard_payload


class _CatalogTestCase(unittest.TestCase):
    """Base case that isolates the catalog home to a temp dir."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="od-cat-")
        self.catalog_home = Path(self.tmpdir) / "catalog"
        self.ws_root = Path(self.tmpdir) / "workspaces"
        self.ws_root.mkdir(parents=True, exist_ok=True)
        self._prev_env = os.environ.get("OPENDREAM_CATALOG_HOME")
        os.environ["OPENDREAM_CATALOG_HOME"] = str(self.catalog_home)

    def tearDown(self) -> None:
        if self._prev_env is None:
            os.environ.pop("OPENDREAM_CATALOG_HOME", None)
        else:
            os.environ["OPENDREAM_CATALOG_HOME"] = self._prev_env
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_workspace(self, name: str) -> Path:
        ws = self.ws_root / name
        ws.mkdir(parents=True, exist_ok=True)
        store = MemoryStore(ws)
        store.initialize(store_kind="project")
        return ws


class CatalogStorageTests(_CatalogTestCase):
    def test_empty_catalog_roundtrip(self) -> None:
        self.assertEqual(workspace_catalog.list_entries(), [])
        self.assertEqual(workspace_catalog.list_roots(), [])

    def test_upsert_and_list(self) -> None:
        ws = self._make_workspace("alpha")
        entry = workspace_catalog.upsert_entry(ws, discovered_by="init")
        self.assertEqual(entry["workspace_name"], "alpha")
        self.assertEqual(entry["status_kind"], "ok")
        self.assertEqual(entry["memory_dir"], ".opendream/memory")

        entries = workspace_catalog.list_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["workspace_path"], str(ws.resolve()))

    def test_upsert_is_idempotent_and_updates_last_seen(self) -> None:
        ws = self._make_workspace("beta")
        first = workspace_catalog.upsert_entry(ws, discovered_by="init")
        second = workspace_catalog.upsert_entry(ws, discovered_by="activate")
        self.assertEqual(first["first_seen_at"], second["first_seen_at"])
        self.assertEqual(second["discovered_by"], "activate")
        self.assertEqual(len(workspace_catalog.list_entries()), 1)

    def test_missing_workspace_marked_missing_not_deleted(self) -> None:
        ws = self._make_workspace("gamma")
        workspace_catalog.upsert_entry(ws, discovered_by="init")
        shutil.rmtree(ws)
        refreshed = workspace_catalog.refresh_entry(ws)
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed["status_kind"], "missing")
        # Still present in the catalog — diagnostic, not silently deleted.
        self.assertEqual(len(workspace_catalog.list_entries()), 1)

    def test_broken_workspace_detected(self) -> None:
        ws = self.ws_root / "delta"
        ws.mkdir()
        (ws / ".opendream").mkdir()  # no /memory subtree
        result = workspace_catalog.probe_workspace(ws)
        self.assertEqual(result.status_kind, "broken")

    def test_forget_removes_entry_only(self) -> None:
        ws = self._make_workspace("epsilon")
        workspace_catalog.upsert_entry(ws, discovered_by="init")
        self.assertTrue(workspace_catalog.forget_workspace(ws))
        self.assertEqual(workspace_catalog.list_entries(), [])
        # Workspace-local state untouched.
        self.assertTrue((ws / ".opendream" / "memory" / "state" / "store.json").exists())

    def test_roots_add_remove_are_persisted(self) -> None:
        root = self.ws_root
        self.assertTrue(workspace_catalog.add_root(root))
        self.assertFalse(workspace_catalog.add_root(root))
        self.assertIn(str(root.resolve()), workspace_catalog.list_roots())
        self.assertTrue(workspace_catalog.remove_root(root))
        self.assertEqual(workspace_catalog.list_roots(), [])

    def test_safe_update_never_raises(self) -> None:
        ws = self._make_workspace("zeta")
        result = workspace_catalog.safe_update(ws, discovered_by="init")
        self.assertEqual(result["status"], "ok")

        # If the catalog write path is un-writable, safe_update should surface
        # a failure status rather than raising.
        bad_home = self.catalog_home / "conflict"
        bad_home.parent.mkdir(parents=True, exist_ok=True)
        bad_home.write_text("not a directory", encoding="utf-8")
        os.environ["OPENDREAM_CATALOG_HOME"] = str(bad_home)
        try:
            broken = workspace_catalog.safe_update(ws, discovered_by="init")
            self.assertEqual(broken["status"], "failed")
            self.assertIn("error", broken)
        finally:
            os.environ["OPENDREAM_CATALOG_HOME"] = str(self.catalog_home)


class ScanTests(_CatalogTestCase):
    def test_scan_with_no_roots_reports_error_not_silent(self) -> None:
        report = workspace_catalog.scan_roots(all_roots=True)
        self.assertEqual(report["roots_scanned"], [])
        self.assertTrue(any("no roots" in err for err in report["errors"]))

    def test_scan_discovers_nested_workspaces(self) -> None:
        self._make_workspace("a")
        self._make_workspace("b")
        self._make_workspace("c")
        report = workspace_catalog.scan_roots([self.ws_root])
        self.assertEqual(len(report["discovered"]), 3)
        self.assertEqual(report["errors"], [])
        self.assertEqual(len(workspace_catalog.list_entries()), 3)

    def test_scan_is_idempotent(self) -> None:
        self._make_workspace("a")
        workspace_catalog.scan_roots([self.ws_root])
        report = workspace_catalog.scan_roots([self.ws_root])
        self.assertEqual(report["discovered"], [])
        self.assertEqual(len(report["updated"]), 1)

    def test_scan_prunes_noisy_dirs(self) -> None:
        self._make_workspace("keep")
        noise = self.ws_root / "node_modules" / "ignored"
        noise.mkdir(parents=True)
        MemoryStore(noise).initialize(store_kind="project")
        report = workspace_catalog.scan_roots([self.ws_root])
        for discovered in report["discovered"]:
            self.assertNotIn("node_modules", discovered)


class CliIntegrationTests(_CatalogTestCase):
    def _run(self, *argv: str) -> int:
        parser = build_parser()
        parsed = parser.parse_args(list(argv))
        result = parsed.func(parsed)
        self.assertIsInstance(result, dict)
        return 0

    def test_workspace_list_command(self) -> None:
        ws = self._make_workspace("one")
        workspace_catalog.upsert_entry(ws, discovered_by="init")
        parser = build_parser()
        args = parser.parse_args(["workspace", "list"])
        result = args.func(args)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["entries"][0]["workspace_name"], "one")

    def test_workspace_roots_add_remove_cli(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["workspace", "roots", "add", "--path", str(self.ws_root)])
        result = args.func(args)
        self.assertEqual(result["status"], "added")

        args = parser.parse_args(["workspace", "roots", "list"])
        result = args.func(args)
        self.assertIn(str(self.ws_root.resolve()), result["roots"])

        args = parser.parse_args(["workspace", "roots", "remove", "--path", str(self.ws_root)])
        result = args.func(args)
        self.assertEqual(result["status"], "removed")

    def test_init_command_emits_catalog_update(self) -> None:
        ws = self.ws_root / "from-init"
        parser = build_parser()
        args = parser.parse_args(["init", "--workspace", str(ws)])
        result = args.func(args)
        self.assertIn("catalog_update", result)
        self.assertEqual(result["catalog_update"]["status"], "ok")
        entries = workspace_catalog.list_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["discovered_by"], "init")

    def test_workspace_forget_cli(self) -> None:
        ws = self._make_workspace("forget-me")
        workspace_catalog.upsert_entry(ws, discovered_by="init")
        parser = build_parser()
        args = parser.parse_args(["workspace", "forget", "--workspace", str(ws)])
        result = args.func(args)
        self.assertEqual(result["status"], "forgotten")
        self.assertEqual(workspace_catalog.list_entries(), [])

    def test_workspace_doctor_requires_scope(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["workspace", "doctor"])
        with self.assertRaises(ValueError):
            args.func(args)


class DashboardPayloadTests(_CatalogTestCase):
    def test_dashboard_payload_summary_counts(self) -> None:
        ws1 = self._make_workspace("ok1")
        ws2 = self._make_workspace("ok2")
        workspace_catalog.upsert_entry(ws1, discovered_by="init")
        workspace_catalog.upsert_entry(ws2, discovered_by="init")
        shutil.rmtree(ws2)
        workspace_catalog.refresh_entry(ws2)

        payload = _workspace_dashboard_payload()
        self.assertEqual(payload["summary"]["total"], 2)
        self.assertEqual(payload["summary"]["ok"], 1)
        self.assertEqual(payload["summary"]["missing"], 1)
        self.assertEqual(len(payload["entries"]), 2)


class SchemaValidationTests(_CatalogTestCase):
    def test_catalog_schema_enforces_status_kind_enum(self) -> None:
        from opendream.validation import SchemaValidationError, validate_document

        bad = {
            "version": 1,
            "entries": [
                {
                    "workspace_path": "/x",
                    "workspace_name": "x",
                    "first_seen_at": "2026-01-01T00:00:00Z",
                    "last_seen_at": "2026-01-01T00:00:00Z",
                    "discovered_by": "init",
                    "status_kind": "weird-value",
                }
            ],
        }
        with self.assertRaises(SchemaValidationError):
            validate_document("workspace-catalog.schema.json", bad)


if __name__ == "__main__":
    unittest.main()
