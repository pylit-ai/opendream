from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_PATH = REPO_ROOT / "scripts" / "verify.py"
SPEC = importlib.util.spec_from_file_location("opendream_verify_script", VERIFY_PATH)
assert SPEC is not None and SPEC.loader is not None
verify_script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_script)


class VerifyScriptTests(unittest.TestCase):
    def test_timeout_output_is_json_serializable_text(self) -> None:
        timeout = subprocess.TimeoutExpired(
            cmd=["slow-check"],
            timeout=1,
            output=b"partial stdout",
            stderr=b"partial stderr \xff",
        )
        with mock.patch.object(verify_script.subprocess, "run", side_effect=timeout):
            result = verify_script.run_command(["slow-check"], timeout_seconds=1)

        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["error"], "timeout")
        self.assertEqual(result["stdout"], "partial stdout")
        self.assertEqual(result["stderr"], "partial stderr \ufffd")


if __name__ == "__main__":
    unittest.main()
