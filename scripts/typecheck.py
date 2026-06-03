from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "opendream", "scripts"],
        cwd=REPO_ROOT,
        text=True,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
