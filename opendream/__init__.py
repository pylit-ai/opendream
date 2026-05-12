"""Local-first memory subsystem for coding agents."""

from __future__ import annotations

import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

__all__ = ["__version__"]


def _fallback_version_from_pyproject() -> str:
    root = Path(__file__).resolve().parent.parent
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return "0.0.0+unknown"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project")
    if isinstance(project, dict):
        ver = project.get("version")
        if isinstance(ver, str) and ver:
            return ver
    return "0.0.0+unknown"


def _resolve_version() -> str:
    pyproject_version = _fallback_version_from_pyproject()
    if pyproject_version != "0.0.0+unknown":
        return pyproject_version
    try:
        return version("opendream")
    except PackageNotFoundError:
        return pyproject_version


__version__ = _resolve_version()
