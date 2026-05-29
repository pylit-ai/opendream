"""Tests for advanced memory platform release bundle (440).

Covers: advanced-runtime report, execution ownership, scaffold-dream,
status/observability extensions, contract export extensions, docs
wording checks, schema validation, and release gate integration.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from opendream.automation import scaffold_dream_job
from opendream.contract_export import build_contract_export
from opendream.evaluation import run_advanced_runtime_report
from opendream.models import AdvancedRuntimeReport
from opendream.observability import index_observability
from opendream.semantic_setup import EXECUTION_STRATEGIES, semantic_setup
from opendream.storage import MemoryStore
from opendream.validation import validate_document

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = "2026-04-01T12:00:00Z"


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


class TestAdvancedRuntimeReportSchema(unittest.TestCase):
    """WS2: Schema validation for advanced-runtime report."""

    def test_schema_exists_and_loads(self) -> None:
        from opendream.validation import load_schema
        schema = load_schema("advanced-runtime-report.schema.json")
        self.assertIsInstance(schema, dict)
        self.assertIn("report_id", schema.get("required", []))

    def test_schema_in_required_list(self) -> None:
        from opendream.validation import required_schema_files
        self.assertIn("advanced-runtime-report.schema.json", required_schema_files())

    def test_model_validates_against_schema(self) -> None:
        report = AdvancedRuntimeReport(
            report_id="test-report-1",
            generated_at=FIXED_NOW,
            modes=[
                {"mode": "deterministic", "tested": True, "scorecard_passed": True},
                {"mode": "direct-provider", "tested": False, "scorecard_passed": None},
            ],
            memory_excellence_summary={
                "scorecard_passed": True,
                "scores": {"stale_claim_rate": 0.0},
            },
            docs_truthfulness={
                "passed": True,
                "checks": [{"check": "no forbidden wording in README.md", "passed": True}],
            },
            release_verdict="pass",
        )
        validate_document("advanced-runtime-report.schema.json", report.to_dict())


class TestAdvancedRuntimeReportGeneration(unittest.TestCase):
    """WS12: Advanced-runtime report generation."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(self.workspace)
        self.store.initialize(store_kind="project")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_report_on_clean_store(self) -> None:
        report = run_advanced_runtime_report(self.store, now=FIXED_NOW)
        self.assertIn("report_id", report)
        self.assertIn("modes", report)
        self.assertIn("memory_excellence_summary", report)
        self.assertIn("docs_truthfulness", report)
        self.assertIn("release_verdict", report)
        validate_document("advanced-runtime-report.schema.json", report)

    def test_report_includes_all_execution_modes(self) -> None:
        report = run_advanced_runtime_report(self.store, now=FIXED_NOW)
        mode_names = [m["mode"] for m in report["modes"]]
        for strategy in EXECUTION_STRATEGIES:
            self.assertIn(strategy, mode_names)

    def test_report_deterministic_always_tested(self) -> None:
        report = run_advanced_runtime_report(self.store, now=FIXED_NOW)
        det = [m for m in report["modes"] if m["mode"] == "deterministic"][0]
        self.assertTrue(det["tested"])

    def test_report_archives_to_disk(self) -> None:
        run_advanced_runtime_report(self.store, now=FIXED_NOW)
        report_dir = self.workspace / ".opendream" / "reports" / "advanced-runtime"
        self.assertTrue(report_dir.exists())
        report_files = list(report_dir.glob("*.json"))
        self.assertGreater(len(report_files), 0)

    def test_clean_store_passes(self) -> None:
        report = run_advanced_runtime_report(self.store, now=FIXED_NOW)
        self.assertEqual(report["memory_excellence_summary"]["scorecard_passed"], True)


class TestScaffoldDreamJob(unittest.TestCase):
    """WS8: Feature mining and radar scaffold generation."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_scaffold_feature_radar_claude(self) -> None:
        result = scaffold_dream_job(self.workspace, "claude-scheduled-task", "feature-radar")
        self.assertEqual(result["adapter_id"], "claude-scheduled-task")
        self.assertEqual(result["kind"], "feature-radar")
        self.assertEqual(result["ingest_mode"], "delegated-envelope")
        self.assertIn("created_files", result)
        # Should have job spec and prompt
        self.assertTrue(len(result["created_files"]) >= 2)

    def test_scaffold_semantic_refresh_cursor(self) -> None:
        result = scaffold_dream_job(self.workspace, "cursor-automation", "semantic-refresh")
        self.assertEqual(result["adapter_id"], "cursor-automation")
        self.assertEqual(result["kind"], "semantic-refresh")

    def test_scaffold_bug_radar_codex(self) -> None:
        result = scaffold_dream_job(self.workspace, "codex-account", "bug-radar")
        self.assertEqual(result["adapter_id"], "codex-account")
        self.assertEqual(result["ingest_mode"], "direct-report")
        # Codex is direct-report, so no prompt file
        self.assertEqual(len(result["created_files"]), 1)

    def test_scaffold_fix_radar(self) -> None:
        result = scaffold_dream_job(self.workspace, "claude-scheduled-task", "fix-radar")
        self.assertEqual(result["kind"], "fix-radar")

    def test_scaffold_creates_job_spec_file(self) -> None:
        scaffold_dream_job(self.workspace, "claude-scheduled-task", "feature-radar")
        job_path = self.workspace / ".opendream" / "dream-jobs" / "claude-scheduled-task" / "feature-radar.json"
        self.assertTrue(job_path.exists())
        job = json.loads(job_path.read_text(encoding="utf-8"))
        self.assertEqual(job["job_id"], "feature-radar-claude-scheduled-task")
        self.assertIn("trigger", job)
        self.assertIn("input_selectors", job)

    def test_scaffold_creates_inbox_for_delegated(self) -> None:
        scaffold_dream_job(self.workspace, "claude-scheduled-task", "feature-radar")
        inbox = self.workspace / ".opendream" / "inbox" / "semantic" / "claude-scheduled-task"
        self.assertTrue(inbox.exists())

    def test_scaffold_invalid_kind_raises(self) -> None:
        with self.assertRaises(ValueError):
            scaffold_dream_job(self.workspace, "claude-scheduled-task", "invalid-kind")

    def test_scaffold_invalid_adapter_raises(self) -> None:
        with self.assertRaises(ValueError):
            scaffold_dream_job(self.workspace, "gemini-reuse", "feature-radar")

    def test_all_kinds_for_all_adapters(self) -> None:
        """Every valid kind/adapter combination should scaffold successfully."""
        kinds = ("feature-radar", "bug-radar", "fix-radar", "semantic-refresh")
        adapters = ("codex-account", "claude-scheduled-task", "cursor-automation")
        for adapter in adapters:
            for kind in kinds:
                result = scaffold_dream_job(self.workspace, adapter, kind)
                self.assertEqual(result["adapter_id"], adapter)
                self.assertEqual(result["kind"], kind)


class TestExecutionOwnershipInContract(unittest.TestCase):
    """WS9/T10: Contract export includes execution ownership."""

    def test_export_includes_execution_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            contract = build_contract_export(Path(td))
            self.assertIn("execution_ownership", contract)
            ownership = contract["execution_ownership"]
            self.assertIn("execution_owners", ownership)
            self.assertIn("supported_strategies", ownership)
            self.assertIn("unsupported_strategies", ownership)
            self.assertIn("trust_boundaries", ownership)
            self.assertIn("gemini-oauth-reuse", ownership["unsupported_strategies"])

    def test_trust_boundaries_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            contract = build_contract_export(Path(td))
            boundaries = contract["execution_ownership"]["trust_boundaries"]
            self.assertEqual(boundaries["codex-account"], "trusted-local-or-controlled-infrastructure-only")
            self.assertEqual(boundaries["claude-scheduled-task"], "vendor-owned-runtime")
            self.assertEqual(boundaries["cursor-automation"], "vendor-owned-runtime")
            self.assertEqual(boundaries["direct-provider"], "operator-managed-api-key")
            self.assertEqual(boundaries["deterministic"], "no-model-call")


class TestObservabilityExecutionOwnership(unittest.TestCase):
    """WS9: Observability index includes execution ownership."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(self.workspace)
        self.store.initialize(store_kind="project")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_observability_includes_execution_ownership(self) -> None:
        index = index_observability(self.store)
        overview = index["overview"]
        self.assertIn("execution_ownership", overview)
        ownership = overview["execution_ownership"]
        self.assertIn("active_strategy", ownership)
        self.assertIn("preferred_auth_mode", ownership)

    def test_default_strategy_is_deterministic(self) -> None:
        index = index_observability(self.store)
        ownership = index["overview"]["execution_ownership"]
        self.assertEqual(ownership["active_strategy"], "deterministic")


class TestSemanticStatusTrustBoundary(unittest.TestCase):
    """WS9: Semantic status includes trust boundary."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(self.workspace)
        self.store.initialize(store_kind="project")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_status_includes_trust_boundary(self) -> None:
        from opendream.semantic_dreamer import dream_status_semantic
        status = dream_status_semantic(self.store)
        self.assertIn("trust_boundary", status)
        self.assertEqual(status["trust_boundary"], "no-model-call")


class TestPublicSchemaEntry(unittest.TestCase):
    """WS1: Verify advanced runtime schema is stable."""

    def test_advanced_runtime_schema_is_public(self) -> None:
        schema_path = REPO_ROOT / "opendream" / "schema" / "advanced-runtime-report.schema.json"
        content = schema_path.read_text(encoding="utf-8")
        self.assertIn("advanced-runtime-report", content)


class TestADRs(unittest.TestCase):
    """WS1: Verify ADRs exist."""

    def test_adr_014_exists(self) -> None:
        path = REPO_ROOT / "docs" / "adr" / "ADR-014-execution-ownership-matrix.md"
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("Accepted", content)

    def test_adr_015_exists(self) -> None:
        path = REPO_ROOT / "docs" / "adr" / "ADR-015-codex-trust-boundary.md"
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("Accepted", content)

    def test_adr_016_exists(self) -> None:
        path = REPO_ROOT / "docs" / "adr" / "ADR-016-advanced-runtime-proof-contract.md"
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("Accepted", content)


class TestDocsHonestyExtended(unittest.TestCase):
    """WS10: Extended docs honesty checks for 440 bundle."""

    FORBIDDEN_PHRASES = [
        "borrows OAuth",
        "reuses OAuth",
        "uses Gemini account",
        "piggybacking",
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

    def test_no_forbidden_wording(self) -> None:
        for doc_path in self.DOC_FILES:
            if not doc_path.exists():
                continue
            content = doc_path.read_text(encoding="utf-8").lower()
            for phrase in self.FORBIDDEN_PHRASES:
                if phrase.lower() in content:
                    self.fail(f"Forbidden phrase '{phrase}' found in {doc_path.name}")

    def test_architecture_mentions_control_plane(self) -> None:
        overview = REPO_ROOT / "docs" / "architecture" / "overview.md"
        content = overview.read_text(encoding="utf-8")
        self.assertIn("memory control plane", content)

    def test_architecture_mentions_execution_surfaces(self) -> None:
        overview = REPO_ROOT / "docs" / "architecture" / "overview.md"
        content = overview.read_text(encoding="utf-8")
        self.assertIn("feature mining", content.lower())
        self.assertIn("advanced runtime", content.lower())


class TestCLIScaffoldDream(unittest.TestCase):
    """WS8: CLI scaffold-dream smoke test."""

    def test_scaffold_dream_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "ws"
            ws.mkdir()
            result = run_cli_json(
                "automation", "scaffold-dream",
                "--workspace", str(ws),
                "--adapter", "claude-scheduled-task",
                "--kind", "feature-radar",
            )
            self.assertEqual(result["adapter_id"], "claude-scheduled-task")
            self.assertEqual(result["kind"], "feature-radar")


class TestCLIAdvancedRuntime(unittest.TestCase):
    """WS12: CLI eval advanced-runtime smoke test."""

    def test_eval_advanced_runtime_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "ws"
            ws.mkdir()
            run_cli("init", "--workspace", str(ws))
            result = run_cli_json(
                "eval", "advanced-runtime",
                "--workspace", str(ws),
                "--now", FIXED_NOW,
            )
            self.assertIn("report_id", result)
            self.assertIn("release_verdict", result)


class TestUnsupportedPathGuardrails(unittest.TestCase):
    """WS11: Unsupported path guardrails."""

    def test_gemini_never_in_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "ws"
            ws.mkdir()
            report = semantic_setup(ws)
            strategies = [c["strategy"] for c in report["candidates"]]
            self.assertNotIn("gemini-oauth-reuse", strategies)

    def test_gemini_always_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "ws"
            ws.mkdir()
            report = semantic_setup(ws)
            blocked = [b["strategy"] for b in report["blocked_strategies"]]
            self.assertIn("gemini-oauth-reuse", blocked)


if __name__ == "__main__":
    unittest.main()
