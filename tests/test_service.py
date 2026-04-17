from __future__ import annotations

import signal
import unittest
from unittest.mock import patch

from opendream import service


class ServiceSignalTests(unittest.TestCase):
    def test_signal_process_tree_falls_back_to_single_pid_on_permission_error(self) -> None:
        with patch.object(service.os, "killpg", side_effect=PermissionError), patch.object(service.os, "kill") as kill:
            service._signal_process_tree(4242, signal.SIGTERM)

        kill.assert_called_once_with(4242, signal.SIGTERM)

    def test_codex_hook_script_passes_agent_provenance(self) -> None:
        pre_script = service._hook_script("codex", "pre")
        post_script = service._hook_script("codex", "post")

        self.assertIn("--agent-id", pre_script)
        self.assertIn("codex", pre_script)
        self.assertIn("--agent-model-id", pre_script)
        self.assertIn("--agent-id", post_script)
        self.assertIn("--agent-model-id", post_script)


if __name__ == "__main__":
    unittest.main()
