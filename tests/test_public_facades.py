from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class PublicFacadeTests(unittest.TestCase):
    def test_spec_facade_exports_contract(self) -> None:
        from opendream.spec import build_public_contract, schema_names

        contract = build_public_contract(Path.cwd())
        self.assertIn("opendream_version", contract)
        self.assertIn("contract-export.schema.json", schema_names())

    def test_runtime_facade_runs_default_dream(self) -> None:
        from opendream.runtime import dream_run
        from opendream.storage import MemoryStore

        with tempfile.TemporaryDirectory() as temp_dir:
            result = dream_run(MemoryStore(Path(temp_dir)), episode_paths=[])
        self.assertEqual(result["status"], "skipped")

    def test_optional_backend_registry_is_lazy(self) -> None:
        from opendream.backends import BACKENDS

        self.assertIn("semantic", BACKENDS)
        self.assertEqual(BACKENDS["semantic"].module, "opendream.semantic_dreamer")

    def test_adapter_and_eval_facades_import(self) -> None:
        from opendream.adapters import load_bundled_adapters
        from opendream.evals import run_dream_fidelity_eval
        from opendream.ui import LOCAL_UI_CONTRACT

        self.assertIsInstance(load_bundled_adapters(), dict)
        self.assertTrue(callable(run_dream_fidelity_eval))
        self.assertEqual(LOCAL_UI_CONTRACT.runtime, "public")


if __name__ == "__main__":
    unittest.main()
