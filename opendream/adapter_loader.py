from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .validation import validate_document

BUNDLE_DIR = Path(__file__).resolve().parent / "bundled_adapters"
WORKSPACE_ADAPTER_DIR = Path(".opendream/adapters")


def _read_adapter_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"adapter manifest must be an object: {path}")
    validate_document("adapter-manifest.schema.json", payload)
    file_id = path.stem
    manifest_id = payload.get("id")
    if not isinstance(manifest_id, str):
        raise ValueError(f"adapter {path} missing string id")
    if manifest_id != file_id:
        raise ValueError(
            f"adapter id {manifest_id!r} must match filename stem {file_id!r} ({path})"
        )
    return payload


def load_bundled_adapters() -> dict[str, dict[str, Any]]:
    adapters: dict[str, dict[str, Any]] = {}
    if not BUNDLE_DIR.is_dir():
        return adapters
    for path in sorted(BUNDLE_DIR.glob("*.json")):
        manifest = _read_adapter_file(path)
        adapters[manifest["id"]] = manifest
    return adapters


def load_workspace_adapters(workspace: Path) -> dict[str, dict[str, Any]]:
    adapters: dict[str, dict[str, Any]] = {}
    root = workspace / WORKSPACE_ADAPTER_DIR
    if not root.is_dir():
        return adapters
    for path in sorted(root.glob("*.json")):
        manifest = _read_adapter_file(path)
        adapters[manifest["id"]] = manifest
    return adapters


def load_merged_adapters(workspace: Path) -> dict[str, dict[str, Any]]:
    merged = dict(load_bundled_adapters())
    merged.update(load_workspace_adapters(workspace))
    return merged


def builtin_adapter_ids() -> tuple[str, ...]:
    return tuple(sorted(load_bundled_adapters().keys()))


def adapter_ids_for_workspace(workspace: Path, previous_ids: frozenset[str] | None = None) -> tuple[str, ...]:
    merged = load_merged_adapters(workspace)
    ids = set(merged.keys())
    if previous_ids:
        ids |= set(previous_ids)
    return tuple(sorted(ids))
