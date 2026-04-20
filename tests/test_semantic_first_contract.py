from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from opendream.activation import compressed_status, doctor_memory
from opendream.contract_export import build_contract_export
from opendream.observability import index_observability
from opendream.storage import MemoryStore


class SemanticFirstContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(self.workspace)
        self.store.initialize(store_kind="project")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_status_marks_deterministic_choice_without_degraded_claim(self) -> None:
        self.store.save_semantic_config(
            {
                **self.store.load_semantic_config(),
                "mode": "deterministic",
                "execution_strategy": "deterministic",
                "candidate_strategies": ["deterministic"],
            }
        )

        payload = compressed_status(self.store, now="2026-04-19T12:00:00Z")

        self.assertEqual(payload["product_posture"], "deterministic-by-choice")
        self.assertEqual(payload["semantic_capability_state"], "disabled_by_choice")
        self.assertIsNone(payload["semantic_unavailability_reason"])
        self.assertIn("memory_quality", payload)
        self.assertIn("context_pruning", payload)

    def test_status_marks_semantic_first_without_applied_path_as_setup_required(self) -> None:
        self.store.save_semantic_config(
            {
                **self.store.load_semantic_config(),
                "mode": "semantic",
                "execution_strategy": "deterministic",
                "candidate_strategies": ["codex-account", "deterministic"],
                "preferred_auth_mode": "no-extra-key",
            }
        )

        payload = compressed_status(self.store, now="2026-04-19T12:00:00Z")

        self.assertEqual(payload["product_posture"], "semantic-first")
        self.assertEqual(payload["semantic_capability_state"], "setup_required")
        self.assertIsInstance(payload["semantic_unavailability_reason"], str)
        self.assertTrue(payload["semantic_unavailability_reason"])
        self.assertIsInstance(payload["next_action"], str)
        self.assertTrue(payload["next_action"])

    def test_overview_exposes_semantic_truth_and_quality_blocks(self) -> None:
        self.store.save_semantic_config(
            {
                **self.store.load_semantic_config(),
                "mode": "semantic",
                "execution_strategy": "deterministic",
                "candidate_strategies": ["codex-account", "deterministic"],
            }
        )

        overview = index_observability(self.store, now="2026-04-19T12:00:00Z")["overview"]

        self.assertEqual(overview["product_posture"], "semantic-first")
        self.assertEqual(overview["semantic_capability_state"], "setup_required")
        self.assertIn("memory_quality", overview)
        self.assertIn("context_pruning", overview)
        self.assertIn("next_action", overview)

    def test_memory_doctor_exposes_semantic_truth_and_warnings(self) -> None:
        self.store.save_semantic_config(
            {
                **self.store.load_semantic_config(),
                "mode": "semantic",
                "execution_strategy": "deterministic",
                "candidate_strategies": ["codex-account", "deterministic"],
            }
        )

        payload = doctor_memory(self.store)

        self.assertEqual(payload["product_posture"], "semantic-first")
        self.assertEqual(payload["semantic_capability_state"], "setup_required")
        self.assertIn("memory_quality", payload)
        self.assertIn("next_action", payload)

    def test_contract_export_describes_semantic_read_model_fields(self) -> None:
        payload = build_contract_export(self.workspace)

        contract = payload["semantic_read_model_contract"]
        self.assertEqual(
            contract["required_fields"],
            [
                "product_posture",
                "semantic_capability_state",
                "semantic_unavailability_reason",
                "memory_quality",
                "context_pruning",
                "next_action",
            ],
        )
