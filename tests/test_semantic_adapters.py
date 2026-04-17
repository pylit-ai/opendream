"""Tests for semantic auth adapters release bundle (438).

Covers: adapter manifests, setup wizard, detection, scaffolding,
delegated ingest, status surfaces, contract export, CLI commands,
security policy, and release wording checks.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from opendream.contract_export import build_contract_export
from opendream.semantic_adapters import (
    adapter_status,
    detect_all_tools,
    detect_tool,
    get_adapter_manifest,
    list_adapter_manifests,
    scaffold_adapter,
    validate_adapter_manifest,
)
from opendream.semantic_ingest import (
    ingest_envelope,
    ingest_file,
    scan_inbox,
    validate_envelope,
)
from opendream.semantic_setup import (
    UNSUPPORTED_STRATEGIES,
    semantic_setup,
)
from opendream.storage import MemoryStore
from opendream.validation import (
    SchemaValidationError,
    validate_document,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = "2026-03-31T12:00:00Z"


def run_cli(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "opendream.cli", *args],
        cwd=cwd or REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def run_cli_json(*args: str, cwd: Path | None = None) -> dict[str, object]:
    completed = run_cli(*args, cwd=cwd, check=True)
    return json.loads(completed.stdout)


class TestAdapterManifests(unittest.TestCase):
    """WS4-WS6: Adapter manifest validation."""

    def test_builtin_manifests_exist(self) -> None:
        manifests = list_adapter_manifests()
        self.assertEqual(len(manifests), 3)
        ids = {m["adapter_id"] for m in manifests}
        self.assertEqual(ids, {"codex-account", "claude-scheduled-task", "cursor-automation"})

    def test_codex_manifest_validates(self) -> None:
        manifest = get_adapter_manifest("codex-account")
        self.assertIsNotNone(manifest)
        result = validate_adapter_manifest(manifest)  # type: ignore[arg-type]
        self.assertTrue(result["valid"])

    def test_claude_manifest_validates(self) -> None:
        manifest = get_adapter_manifest("claude-scheduled-task")
        self.assertIsNotNone(manifest)
        result = validate_adapter_manifest(manifest)  # type: ignore[arg-type]
        self.assertTrue(result["valid"])

    def test_cursor_manifest_validates(self) -> None:
        manifest = get_adapter_manifest("cursor-automation")
        self.assertIsNotNone(manifest)
        result = validate_adapter_manifest(manifest)  # type: ignore[arg-type]
        self.assertTrue(result["valid"])

    def test_codex_is_local_execution(self) -> None:
        m = get_adapter_manifest("codex-account")
        assert m is not None
        self.assertEqual(m["execution_owner"], "opendream-local")
        self.assertEqual(m["ingest_mode"], "direct-report")

    def test_claude_is_delegated(self) -> None:
        m = get_adapter_manifest("claude-scheduled-task")
        assert m is not None
        self.assertEqual(m["execution_owner"], "vendor-runtime")
        self.assertEqual(m["ingest_mode"], "delegated-envelope")

    def test_cursor_is_delegated(self) -> None:
        m = get_adapter_manifest("cursor-automation")
        assert m is not None
        self.assertEqual(m["execution_owner"], "vendor-runtime")
        self.assertEqual(m["ingest_mode"], "delegated-envelope")

    def test_unknown_adapter_returns_none(self) -> None:
        self.assertIsNone(get_adapter_manifest("gemini-reuse"))

    def test_all_manifests_validate_against_schema(self) -> None:
        for manifest in list_adapter_manifests():
            validate_document("semantic-adapter-manifest.schema.json", manifest)


class TestAdapterDetection(unittest.TestCase):
    """WS3: Adapter detection."""

    def test_detect_tool_returns_dict(self) -> None:
        result = detect_tool("codex")
        self.assertIn("tool", result)
        self.assertIn("detected", result)
        self.assertIn("binary_found", result)
        self.assertIn("config_found", result)

    def test_detect_all_tools_returns_list(self) -> None:
        result = detect_all_tools()
        self.assertIn("detected_tools", result)
        self.assertIn("details", result)
        self.assertIsInstance(result["detected_tools"], list)
        self.assertIsInstance(result["details"], list)
        self.assertEqual(len(result["details"]), 4)


class TestSetupWizard(unittest.TestCase):
    """WS3: Setup wizard and recommendation."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_setup_produces_valid_report(self) -> None:
        report = semantic_setup(self.workspace, preference="no-extra-key")
        validate_document("semantic-setup-report.schema.json", report)

    def test_setup_with_direct_provider_preference(self) -> None:
        report = semantic_setup(self.workspace, preference="direct-provider")
        self.assertEqual(report["preference"], "direct-provider")
        validate_document("semantic-setup-report.schema.json", report)

    def test_setup_invalid_preference_raises(self) -> None:
        with self.assertRaises(ValueError):
            semantic_setup(self.workspace, preference="invalid")

    def test_setup_includes_blocked_strategies(self) -> None:
        report = semantic_setup(self.workspace)
        blocked = report["blocked_strategies"]
        self.assertIsInstance(blocked, list)
        # Gemini must always be blocked
        gemini_blocked = [b for b in blocked if b["strategy"] == "gemini-oauth-reuse"]
        self.assertEqual(len(gemini_blocked), 1)
        self.assertIn("unsupported", gemini_blocked[0]["reason"].lower())

    def test_setup_always_includes_deterministic_candidate(self) -> None:
        report = semantic_setup(self.workspace)
        strategies = [c["strategy"] for c in report["candidates"]]
        self.assertIn("deterministic", strategies)

    def test_setup_deterministic_is_always_supported(self) -> None:
        report = semantic_setup(self.workspace)
        det = [c for c in report["candidates"] if c["strategy"] == "deterministic"][0]
        self.assertTrue(det["supported"])

    def test_setup_has_next_actions(self) -> None:
        report = semantic_setup(self.workspace)
        self.assertIsInstance(report["next_actions"], list)


class TestAdapterScaffolding(unittest.TestCase):
    """WS4-WS6: Adapter scaffolding."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_scaffold_codex(self) -> None:
        result = scaffold_adapter(self.workspace, "codex-account")
        self.assertEqual(result["adapter_id"], "codex-account")
        self.assertIn("created_files", result)
        # Check manifest was written
        manifest_path = self.workspace / ".opendream" / "semantic-adapters" / "codex-account" / "manifest.json"
        self.assertTrue(manifest_path.exists())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["adapter_id"], "codex-account")

    def test_scaffold_claude(self) -> None:
        result = scaffold_adapter(self.workspace, "claude-scheduled-task")
        self.assertEqual(result["adapter_id"], "claude-scheduled-task")
        # Check inbox was created
        inbox = self.workspace / ".opendream" / "inbox" / "semantic" / "claude-scheduled-task"
        self.assertTrue(inbox.exists())

    def test_scaffold_cursor(self) -> None:
        result = scaffold_adapter(self.workspace, "cursor-automation")
        self.assertEqual(result["adapter_id"], "cursor-automation")
        inbox = self.workspace / ".opendream" / "inbox" / "semantic" / "cursor-automation"
        self.assertTrue(inbox.exists())

    def test_scaffold_unknown_raises(self) -> None:
        with self.assertRaises(ValueError):
            scaffold_adapter(self.workspace, "gemini-reuse")


class TestAdapterStatus(unittest.TestCase):
    """WS8: Adapter status reporting."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_status_validates_against_schema(self) -> None:
        status = adapter_status(self.workspace)
        validate_document("semantic-adapter-status.schema.json", status)

    def test_status_default_is_deterministic(self) -> None:
        status = adapter_status(self.workspace)
        self.assertEqual(status["active_strategy"], "deterministic")
        self.assertEqual(status["auth_source"], "none")
        self.assertEqual(status["status"], "ok")


class TestDelegatedEnvelopeValidation(unittest.TestCase):
    """WS7: Envelope validation."""

    def _valid_envelope(self) -> dict[str, object]:
        return {
            "adapter_id": "claude-scheduled-task",
            "run_id": "test-run-1",
            "execution_owner": "claude-scheduled-task",
            "created_at": "2026-03-31T12:00:00Z",
            "workspace_ref": "/tmp/test",
            "anticipated_query_families": ["continue-migration"],
            "proposals": [
                {
                    "summary": "Test proposal from delegated run",
                    "confidence": 0.7,
                    "query_family_tags": ["continue-migration"],
                }
            ],
        }

    def test_valid_envelope_passes(self) -> None:
        result = validate_envelope(self._valid_envelope())
        self.assertTrue(result["valid"])

    def test_empty_proposals_fails(self) -> None:
        env = self._valid_envelope()
        env["proposals"] = []
        result = validate_envelope(env)
        self.assertFalse(result["valid"])
        self.assertTrue(any("no proposals" in i for i in result["issues"]))

    def test_missing_adapter_id_fails(self) -> None:
        env = self._valid_envelope()
        del env["adapter_id"]
        result = validate_envelope(env)
        self.assertFalse(result["valid"])

    def test_envelope_validates_against_schema(self) -> None:
        env = self._valid_envelope()
        validate_document("delegated-semantic-envelope.schema.json", env)


class TestDelegatedIngest(unittest.TestCase):
    """WS7: Envelope ingestion pipeline."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(self.workspace)
        self.store.initialize(store_kind="project")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _valid_envelope(self) -> dict[str, object]:
        return {
            "adapter_id": "claude-scheduled-task",
            "run_id": "ingest-test-1",
            "execution_owner": "claude-scheduled-task",
            "created_at": "2026-03-31T12:00:00Z",
            "workspace_ref": str(self.workspace),
            "anticipated_query_families": ["continue-migration"],
            "proposals": [
                {
                    "summary": "Ingested proposal from Claude delegated run",
                    "confidence": 0.7,
                    "query_family_tags": ["continue-migration"],
                    "source_event_ids": [],
                }
            ],
        }

    def test_ingest_valid_envelope(self) -> None:
        result = ingest_envelope(self.store, self._valid_envelope(), now=FIXED_NOW)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["proposals_received"], 1)
        self.assertEqual(result["adapter_id"], "claude-scheduled-task")
        self.assertIn("provenance", result)

    def test_ingest_invalid_envelope_rejected(self) -> None:
        result = ingest_envelope(self.store, {"bad": "data"}, now=FIXED_NOW)
        self.assertEqual(result["status"], "rejected")

    def test_ingest_emits_proposed_events_with_agent_provenance(self) -> None:
        envelope = self._valid_envelope()
        envelope["proposed_events"] = [
            {
                "kind": "project_decision",
                "content": "Delegated event should be captured.",
                "scope": "project",
            }
        ]

        result = ingest_envelope(self.store, envelope, now=FIXED_NOW)

        self.assertEqual(result["events_emitted"], 1)
        events = self.store.load_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"]["channel"], "tool")
        self.assertEqual(events[0]["source"]["tool_refs"], ["delegated:claude-scheduled-task"])
        self.assertEqual(events[0]["reporting_agent"]["agent_id"], "claude-scheduled-task")
        self.assertEqual(events[0]["reporting_agent"]["agent_label"], "claude-scheduled-task")
        validate_document("memory-event.schema.json", events[0])

    def test_ingest_file_and_archive(self) -> None:
        inbox = self.workspace / ".opendream" / "inbox" / "semantic" / "claude-scheduled-task"
        inbox.mkdir(parents=True, exist_ok=True)
        envelope_path = inbox / "2026-03-31T12-00-00Z-test.json"
        envelope_path.write_text(json.dumps(self._valid_envelope()), encoding="utf-8")

        result = ingest_file(self.store, envelope_path, now=FIXED_NOW)
        self.assertEqual(result["status"], "completed")
        # File should be archived
        self.assertFalse(envelope_path.exists())

    def test_scan_inbox_empty(self) -> None:
        result = scan_inbox(self.store, now=FIXED_NOW)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["envelopes_found"], 0)

    def test_scan_inbox_with_envelopes(self) -> None:
        inbox = self.workspace / ".opendream" / "inbox" / "semantic" / "claude-scheduled-task"
        inbox.mkdir(parents=True, exist_ok=True)
        env = self._valid_envelope()
        (inbox / "envelope1.json").write_text(json.dumps(env), encoding="utf-8")

        result = scan_inbox(self.store, now=FIXED_NOW)
        self.assertEqual(result["envelopes_found"], 1)
        self.assertEqual(result["envelopes_ingested"], 1)

    def test_ingest_file_bad_json_archived(self) -> None:
        inbox = self.workspace / ".opendream" / "inbox" / "semantic" / "test"
        inbox.mkdir(parents=True, exist_ok=True)
        bad = inbox / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        result = ingest_file(self.store, bad, now=FIXED_NOW)
        self.assertEqual(result["status"], "rejected")


class TestSchemaFiles(unittest.TestCase):
    """WS2: Verify all new schemas exist and load."""

    NEW_SCHEMAS = (
        "semantic-adapter-manifest.schema.json",
        "semantic-adapter-status.schema.json",
        "semantic-setup-report.schema.json",
        "delegated-semantic-envelope.schema.json",
        "semantic-execution-policy.schema.json",
    )

    def test_new_schemas_exist(self) -> None:
        from opendream.util import SCHEMA_ROOT

        for name in self.NEW_SCHEMAS:
            path = SCHEMA_ROOT / name
            self.assertTrue(path.exists(), f"missing schema: {name}")

    def test_new_schemas_load(self) -> None:
        from opendream.validation import load_schema

        for name in self.NEW_SCHEMAS:
            schema = load_schema(name)
            self.assertIsInstance(schema, dict)

    def test_execution_policy_schema_validates(self) -> None:
        policy = {
            "preferred_auth_mode": "no-extra-key",
            "candidate_order": ["codex-account", "claude-scheduled-task", "direct-provider"],
            "unsupported_strategies": ["gemini-oauth-reuse"],
            "gemini_oauth_reuse": "unsupported",
        }
        validate_document("semantic-execution-policy.schema.json", policy)

    def test_execution_policy_gemini_must_be_unsupported(self) -> None:
        policy = {
            "preferred_auth_mode": "no-extra-key",
            "candidate_order": [],
            "unsupported_strategies": [],
            "gemini_oauth_reuse": "supported",
        }
        with self.assertRaises(SchemaValidationError):
            validate_document("semantic-execution-policy.schema.json", policy)


class TestContractExport(unittest.TestCase):
    """WS8: Contract export includes adapter inventory."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_export_includes_adapter_inventory(self) -> None:
        export = build_contract_export(self.workspace)
        self.assertIn("semantic_adapter_inventory", export)
        adapters = export["semantic_adapter_inventory"]
        self.assertEqual(len(adapters), 3)
        ids = {a["adapter_id"] for a in adapters}
        self.assertEqual(ids, {"codex-account", "claude-scheduled-task", "cursor-automation"})

    def test_export_includes_auth_matrix(self) -> None:
        export = build_contract_export(self.workspace)
        self.assertIn("semantic_auth_matrix", export)
        matrix = export["semantic_auth_matrix"]
        self.assertIn("strategies", matrix)
        self.assertIn("unsupported", matrix)
        self.assertIn("gemini-oauth-reuse", matrix["unsupported"])


class TestSemanticStatus(unittest.TestCase):
    """WS8: Semantic status includes execution strategy."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(self.workspace)
        self.store.initialize(store_kind="project")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_status_includes_execution_strategy(self) -> None:
        from opendream.semantic_dreamer import dream_status_semantic

        status = dream_status_semantic(self.store)
        self.assertIn("execution_strategy", status)
        self.assertIn("preferred_auth_mode", status)
        self.assertIn("auth_source", status)
        self.assertIn("candidate_strategies", status)

    def test_status_default_strategy_is_deterministic(self) -> None:
        from opendream.semantic_dreamer import dream_status_semantic

        status = dream_status_semantic(self.store)
        self.assertEqual(status["execution_strategy"], "deterministic")
        self.assertEqual(status["auth_source"], "none")


class TestSecurityPolicy(unittest.TestCase):
    """WS10: Security and unsupported-path policy tests."""

    def test_gemini_never_recommended(self) -> None:
        """Setup wizard must never recommend gemini-oauth-reuse."""
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "workspace"
            ws.mkdir()
            report = semantic_setup(ws)
            recommended = report["recommended_strategy"]
            self.assertNotEqual(recommended, "gemini-oauth-reuse")
            # Gemini must appear in blocked
            blocked_strategies = [b["strategy"] for b in report["blocked_strategies"]]
            self.assertIn("gemini-oauth-reuse", blocked_strategies)

    def test_unsupported_strategies_list(self) -> None:
        self.assertIn("gemini-oauth-reuse", UNSUPPORTED_STRATEGIES)


class TestDocsHonesty(unittest.TestCase):
    """WS9/WS11: Release wording checks — docs must not imply unsupported magic."""

    FORBIDDEN_PHRASES = [
        "borrows OAuth",
        "reuses OAuth",
        "uses Gemini account",
        "piggybacking",
        "magic",
        "just works",
    ]

    DOC_FILES = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "FAQ.md",
        REPO_ROOT / "docs" / "coding-agents.md",
        REPO_ROOT / "docs" / "automation" / "dream-task-playbook.md",
        REPO_ROOT / "docs" / "architecture" / "overview.md",
        REPO_ROOT / "CHANGELOG.md",
    ]

    def test_no_forbidden_wording_in_docs(self) -> None:
        for doc_path in self.DOC_FILES:
            if not doc_path.exists():
                continue
            content = doc_path.read_text(encoding="utf-8").lower()
            for phrase in self.FORBIDDEN_PHRASES:
                if phrase.lower() in content:
                    # Allow "magic" only in context of "implying magic" or "unsupported magic"
                    if phrase == "magic":
                        lines = [
                            line for line in content.split("\n")
                            if "magic" in line
                            and "imply" not in line
                            and "unsupported" not in line
                            and "stop" not in line
                        ]
                        if not lines:
                            continue
                    self.fail(f"Forbidden phrase '{phrase}' found in {doc_path.name}")


class TestCLICommands(unittest.TestCase):
    """WS3-WS7: CLI command smoke tests."""

    def test_semantic_adapters_list(self) -> None:
        result = run_cli_json("semantic", "adapters", "list")
        self.assertIn("adapters", result)
        self.assertEqual(len(result["adapters"]), 3)

    def test_semantic_adapters_validate_codex(self) -> None:
        result = run_cli_json("semantic", "adapters", "validate", "--adapter", "codex-account")
        self.assertTrue(result["valid"])

    def test_semantic_adapters_validate_claude(self) -> None:
        result = run_cli_json("semantic", "adapters", "validate", "--adapter", "claude-scheduled-task")
        self.assertTrue(result["valid"])

    def test_semantic_adapters_validate_cursor(self) -> None:
        result = run_cli_json("semantic", "adapters", "validate", "--adapter", "cursor-automation")
        self.assertTrue(result["valid"])

    def test_semantic_setup_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "ws"
            ws.mkdir()
            result = run_cli_json("semantic", "setup", "--workspace", str(ws))
            self.assertIn("recommended_strategy", result)
            self.assertIn("blocked_strategies", result)

    def test_semantic_adapters_detect_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "ws"
            ws.mkdir()
            result = run_cli_json("semantic", "adapters", "detect", "--workspace", str(ws))
            self.assertIn("detected_tools", result)

    def test_semantic_adapters_scaffold_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "ws"
            ws.mkdir()
            result = run_cli_json(
                "semantic", "adapters", "scaffold",
                "--workspace", str(ws),
                "--adapter", "codex-account",
            )
            self.assertEqual(result["adapter_id"], "codex-account")

    def test_semantic_ingest_scan_inbox_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "ws"
            ws.mkdir()
            # Initialize store
            run_cli("init", "--workspace", str(ws))
            result = run_cli_json(
                "semantic", "ingest",
                "--workspace", str(ws),
                "--scan-inbox",
                "--now", FIXED_NOW,
            )
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["envelopes_found"], 0)


if __name__ == "__main__":
    unittest.main()
