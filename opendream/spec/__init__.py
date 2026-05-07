from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

from opendream.contract_export import build_contract_export
from opendream.util import SCHEMA_ROOT
from opendream.validation import validate_document


def schema_names() -> tuple[str, ...]:
    return tuple(sorted(path.name for path in Path(str(files("opendream") / "schema")).glob("*.schema.json")))


def build_public_contract(workspace: Path) -> dict[str, Any]:
    return build_contract_export(workspace)


__all__ = [
    "SCHEMA_ROOT",
    "build_contract_export",
    "build_public_contract",
    "schema_names",
    "validate_document",
]
