from __future__ import annotations

import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from opendream.util import atomic_write_text


class AtomicWriteTextTests(unittest.TestCase):
    def test_atomic_write_text_uses_unique_temp_paths_across_threads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "state" / "observability_index.json"
            replace_barrier = threading.Barrier(2)
            recorded_sources: list[str] = []
            recorded_lock = threading.Lock()
            failures: list[BaseException] = []

            real_replace = os.replace

            def coordinated_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
                src_name = Path(src).name
                if src_name.startswith(f".{target.name}.tmp-"):
                    with recorded_lock:
                        recorded_sources.append(src_name)
                    replace_barrier.wait(timeout=2)
                real_replace(src, dst)

            def worker(text: str) -> None:
                try:
                    atomic_write_text(target, text)
                except BaseException as exc:  # pragma: no cover - captured for assertion
                    failures.append(exc)

            with patch("opendream.util.os.replace", side_effect=coordinated_replace):
                threads = [
                    threading.Thread(target=worker, args=("first\n",)),
                    threading.Thread(target=worker, args=("second\n",)),
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=2)

            self.assertEqual(len(recorded_sources), 2)
            self.assertEqual(len(set(recorded_sources)), 2)
            self.assertFalse(failures, failures)
            self.assertTrue(target.exists())
            self.assertIn(target.read_text(encoding="utf-8"), {"first\n", "second\n"})
