"""Global test isolation for the OpenDream test suite.

Ensures the machine-local workspace catalog never points at the operator's
real ``~/.opendream/`` directory during tests. Tests that want to exercise the
catalog must either opt in by pointing ``OPENDREAM_CATALOG_HOME`` at their own
temp directory or accept the shared per-session sandbox set up here.

This guard is belt-and-suspenders: ``workspace_catalog.safe_update`` also
refuses to write when ``PYTEST_CURRENT_TEST`` is set and no explicit
``OPENDREAM_CATALOG_HOME`` is configured.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def pytest_configure(config):  # noqa: ARG001
    if not os.environ.get("OPENDREAM_CATALOG_HOME"):
        sandbox = Path(tempfile.mkdtemp(prefix="opendream-catalog-sandbox-"))
        os.environ["OPENDREAM_CATALOG_HOME"] = str(sandbox)
