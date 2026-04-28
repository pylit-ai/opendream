from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from opendream.memory_quality import analyze_memory_quality
from opendream.storage import MemoryStore
from opendream.util import read_json, write_json

FIXTURE_ROOT = Path(__file__).parent / "fixtures"


class MemoryQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="memory-quality-")
        self.workspace = Path(self.tmp.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(self.workspace)
        self.store.initialize(store_kind="project")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _load_fixture_store(self, name: str) -> str:
        fixture = read_json(FIXTURE_ROOT / name, {})
        write_json(self.store.semantic_config_path, fixture["semantic_config"])
        write_json(self.store.provider_registry_path, fixture["providers"])
        write_json(self.store.durable_records_path, fixture["durable_records"])
        write_json(self.store.learned_context_path, fixture["learned_context_records"])
        return str(fixture["now"])

    def test_homogeneous_memory_fixture_reports_degraded_semantic_and_warnings(self) -> None:
        now = self._load_fixture_store("homogeneous_memory_quality.json")

        report = analyze_memory_quality(self.store, now=now)

        self.assertEqual(report["product_posture"], "semantic_first")
        self.assertEqual(report["semantic_capability_state"], "degraded")
        self.assertEqual(report["semantic_unavailability_reason"], "no providers registered")
        self.assertEqual(report["next_action"], "configure a semantic provider or delegated adapter")
        self.assertEqual(report["memory_quality"]["state"], "warning")
        codes = {warning["code"] for warning in report["memory_quality"]["warnings"]}
        self.assertEqual(
            codes,
            {
                "semantic_unavailable",
                "homogeneous_type_mix",
                "ephemera_heavy",
                "missing_learned_context_activity",
            },
        )
        metrics = report["memory_quality"]["metrics"]
        self.assertAlmostEqual(metrics["dominant_type_share"], 1.0)
        self.assertAlmostEqual(metrics["ephemera_ratio"], 1.0)
        self.assertEqual(metrics["active_learned_context_count"], 0)

    def test_deterministic_by_choice_is_not_reported_as_degraded(self) -> None:
        write_json(
            self.store.semantic_config_path,
            {
                "mode": "deterministic",
                "execution_strategy": "deterministic",
                "fallback_policy": "fallback_to_deterministic",
            },
        )
        write_json(self.store.provider_registry_path, [])
        write_json(self.store.durable_records_path, [])
        write_json(self.store.learned_context_path, [])

        report = analyze_memory_quality(self.store, now="2026-04-19T12:00:00Z")

        self.assertEqual(report["product_posture"], "deterministic_only")
        self.assertEqual(report["semantic_capability_state"], "disabled_by_choice")
        self.assertIsNone(report["semantic_unavailability_reason"])
        self.assertEqual(report["next_action"], "re-enable semantic mode when you want semantic memory value")
        warning_codes = {warning["code"] for warning in report["memory_quality"]["warnings"]}
        self.assertNotIn("semantic_unavailable", warning_codes)
        self.assertNotIn("missing_learned_context_activity", warning_codes)

    def test_stale_active_learned_context_emits_memory_health_warning(self) -> None:
        write_json(
            self.store.semantic_config_path,
            {
                "mode": "semantic",
                "execution_strategy": "direct-provider",
                "fallback_policy": "fallback_to_deterministic",
            },
        )
        write_json(
            self.store.provider_registry_path,
            [{"provider_id": "local", "health_status": "healthy", "roles": ["synthesis", "verification"]}],
        )
        write_json(self.store.durable_records_path, [])
        write_json(
            self.store.learned_context_path,
            [
                {
                    "record_id": "lc-stale-active",
                    "workspace_id": "workspace",
                    "source_event_ids": ["event-1"],
                    "summary": "Stale context",
                    "details": "This learned context is stale but still active.",
                    "assumptions": "",
                    "provider_id": "local",
                    "model_id": "deterministic",
                    "prompt_version": "v1",
                    "created_at": "2026-04-01T00:00:00Z",
                    "fresh_until": "2026-04-10T00:00:00Z",
                    "confidence": 0.8,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "promotion_target": "learned_context",
                    "status": "active",
                }
            ],
        )

        report = analyze_memory_quality(self.store, now="2026-04-19T12:00:00Z")
        warning_codes = {warning["code"] for warning in report["memory_quality"]["warnings"]}

        self.assertIn("stale_active_learned_context", warning_codes)
        self.assertEqual(
            report["memory_quality"]["metrics"]["stale_active_learned_context_count"],
            1,
        )

    def test_semantic_ready_workspace_without_quality_issues_is_healthy(self) -> None:
        now = "2026-04-19T12:00:00Z"
        write_json(
            self.store.semantic_config_path,
            {
                "mode": "semantic",
                "execution_strategy": "direct-provider",
                "fallback_policy": "fallback_to_deterministic",
            },
        )
        write_json(
            self.store.provider_registry_path,
            [
                {
                    "provider_id": "openai-primary",
                    "transport": "openai",
                    "model_id": "gpt-5.4",
                    "roles": ["synthesis", "verification"],
                    "health_status": "healthy",
                }
            ],
        )
        write_json(
            self.store.durable_records_path,
            [
                {
                    "memory_id": "decision-1",
                    "type": "project_decision",
                    "scope": "project",
                    "title": "Decision: package-manager",
                    "summary": "Use uv for local Python tasks.",
                    "body": "Use uv for local Python tasks.",
                    "status": "active",
                    "confidence": 0.93,
                    "salience": 0.88,
                    "source_event_ids": ["evt-1"],
                    "supersedes": [],
                    "conflicts_with": [],
                    "valid_from": "2026-04-18T10:00:00Z",
                    "valid_to": None,
                    "access_count": 0,
                    "last_accessed_at": None,
                    "created_at": "2026-04-18T10:00:00Z",
                    "updated_at": "2026-04-18T10:00:00Z",
                    "provenance_tier": "source_backed",
                    "claim_class": "externally_checkable"
                },
                {
                    "memory_id": "workflow-1",
                    "type": "procedural_workflow",
                    "scope": "project",
                    "title": "Workflow: verify",
                    "summary": "Run ruff, mypy, and make verify before completion.",
                    "body": "Run ruff, mypy, and make verify before completion.",
                    "status": "active",
                    "confidence": 0.9,
                    "salience": 0.84,
                    "source_event_ids": ["evt-2"],
                    "supersedes": [],
                    "conflicts_with": [],
                    "valid_from": "2026-04-18T10:05:00Z",
                    "valid_to": None,
                    "access_count": 0,
                    "last_accessed_at": None,
                    "created_at": "2026-04-18T10:05:00Z",
                    "updated_at": "2026-04-18T10:05:00Z",
                    "provenance_tier": "source_backed",
                    "claim_class": "derived_abstraction"
                }
            ],
        )
        write_json(
            self.store.learned_context_path,
            [
                {
                    "record_id": "lc-1",
                    "workspace_id": self.store.store_id,
                    "source_event_ids": ["evt-1", "evt-2"],
                    "query_family_tags": ["python", "verification"],
                    "summary": "The workspace repeatedly needs Python verification guidance.",
                    "details": "Recent tasks often ask for verification and local Python tooling.",
                    "assumptions": "Python workflow remains stable.",
                    "provider_id": "openai-primary",
                    "model_id": "gpt-5.4",
                    "prompt_version": "2026-04-18",
                    "created_at": "2026-04-18T11:00:00Z",
                    "fresh_until": "2026-04-26T11:00:00Z",
                    "confidence": 0.87,
                    "verifier_status": "approved",
                    "conflict_state": "none",
                    "harm_signals": [],
                    "promotion_target": "learned_context",
                    "status": "active"
                }
            ],
        )

        report = analyze_memory_quality(self.store, now=now)

        self.assertEqual(report["product_posture"], "semantic_first")
        self.assertEqual(report["semantic_capability_state"], "ready")
        self.assertIsNone(report["semantic_unavailability_reason"])
        self.assertEqual(report["next_action"], "none")
        self.assertEqual(report["memory_quality"]["state"], "healthy")
        self.assertEqual(report["memory_quality"]["warnings"], [])

    def test_detected_unapplied_adapter_reports_setup_required(self) -> None:
        write_json(
            self.store.semantic_config_path,
            {
                "mode": "semantic",
                "execution_strategy": "deterministic",
                "preferred_auth_mode": "no-extra-key",
                "fallback_policy": "fallback_to_deterministic",
            },
        )
        write_json(self.store.provider_registry_path, [])
        write_json(self.store.durable_records_path, [])
        write_json(self.store.learned_context_path, [])

        with patch(
            "opendream.semantic_setup.detect_all_tools",
            return_value={
                "detected_tools": ["codex"],
                "details": [
                    {
                        "tool": "codex",
                        "detected": True,
                        "binary_found": True,
                        "config_found": True,
                    }
                ],
            },
        ):
            report = analyze_memory_quality(self.store, now="2026-04-19T12:00:00Z")

        self.assertEqual(report["semantic_capability_state"], "setup_required")
        self.assertEqual(
            report["semantic_unavailability_reason"],
            "recommended strategy codex-account is available but has not been applied",
        )
        self.assertEqual(report["next_action"], "apply the recommended semantic strategy")

    def test_runnable_semantic_path_without_learning_evidence_is_degraded(self) -> None:
        now = "2026-04-19T12:00:00Z"
        write_json(
            self.store.semantic_config_path,
            {
                "mode": "semantic",
                "execution_strategy": "direct-provider",
                "preferred_auth_mode": "direct-provider",
                "fallback_policy": "fallback_to_deterministic",
            },
        )
        write_json(
            self.store.provider_registry_path,
            [
                {
                    "provider_id": "openai-primary",
                    "transport": "openai",
                    "model_id": "gpt-5.4",
                    "roles": ["synthesis", "verification"],
                    "health_status": "healthy",
                }
            ],
        )
        write_json(
            self.store.durable_records_path,
            [
                {
                    "memory_id": "decision-1",
                    "type": "project_decision",
                    "scope": "project",
                    "title": "Decision: package-manager",
                    "summary": "Use uv for local Python tasks.",
                    "body": "Use uv for local Python tasks.",
                    "status": "active",
                    "confidence": 0.93,
                    "salience": 0.88,
                    "source_event_ids": ["evt-1"],
                    "supersedes": [],
                    "conflicts_with": [],
                    "valid_from": "2026-04-18T10:00:00Z",
                    "valid_to": None,
                    "access_count": 0,
                    "last_accessed_at": None,
                    "created_at": "2026-04-18T10:00:00Z",
                    "updated_at": "2026-04-18T10:00:00Z",
                    "provenance_tier": "source_backed",
                    "claim_class": "externally_checkable",
                }
            ],
        )
        write_json(self.store.learned_context_path, [])

        report = analyze_memory_quality(self.store, now=now)

        self.assertEqual(report["semantic_capability_state"], "degraded")
        self.assertEqual(
            report["semantic_unavailability_reason"],
            "semantic path is configured, but learned-context activity has not materialized yet",
        )
        self.assertEqual(
            report["next_action"],
            "run a semantic dream cycle so learned-context starts materializing",
        )
        codes = {warning["code"] for warning in report["memory_quality"]["warnings"]}
        self.assertIn("missing_learned_context_activity", codes)
        self.assertNotIn("semantic_unavailable", codes)


if __name__ == "__main__":
    unittest.main()
