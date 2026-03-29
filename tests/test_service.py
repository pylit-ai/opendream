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


if __name__ == "__main__":
    unittest.main()
