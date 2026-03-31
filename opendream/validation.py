from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .util import SCHEMA_ROOT

REQUIRED_SCHEMA_FILES = (
    "memory-event.schema.json",
    "memory-candidate.schema.json",
    "memory-topic.schema.json",
    "memory-index.schema.json",
    "consolidation-op.schema.json",
    "service-install-report.schema.json",
    "worker-health.schema.json",
    "supervisor-manifest.schema.json",
    "autowire-report.schema.json",
    "agent-target.schema.json",
    "activation-report.schema.json",
    "activation-plan.schema.json",
    "activation-state.schema.json",
    "compressed-status.schema.json",
    "managed-surface.schema.json",
    "repair-report.schema.json",
    "target-registry.schema.json",
    "adapter-manifest.schema.json",
    "automation-job.schema.json",
    "automation-record.schema.json",
    "automation-run-report.schema.json",
    "contract-export.schema.json",
)


ClassInfo = type[Any] | tuple[type[Any], ...]


TYPE_MAP: dict[str, ClassInfo] = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "null": type(None),
    "boolean": bool,
}


class SchemaValidationError(ValueError):
    """Raised when a payload fails schema validation."""


def load_schema(name: str) -> dict[str, Any]:
    path = SCHEMA_ROOT / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SchemaValidationError(f"schema {name} must decode to an object")
    return payload


def required_schema_files() -> tuple[str, ...]:
    return REQUIRED_SCHEMA_FILES


def _matches_type(expected: str | list[str], value: Any) -> bool:
    if isinstance(expected, list):
        return any(_matches_type(item, value) for item in expected)
    python_type = TYPE_MAP[expected]
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, python_type)


def _validate_format(value: Any, fmt: str, path: str) -> None:
    if fmt != "date-time" or value is None:
        return
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:  # pragma: no cover - defensive
        raise SchemaValidationError(f"{path}: invalid date-time {value!r}") from exc


def validate_payload(schema: dict[str, Any], payload: Any, path: str = "$") -> None:
    expected_type = schema.get("type")
    if expected_type and not _matches_type(expected_type, payload):
        raise SchemaValidationError(f"{path}: expected {expected_type}, got {type(payload).__name__}")

    if "enum" in schema and payload not in schema["enum"]:
        raise SchemaValidationError(f"{path}: value {payload!r} not in enum")

    if payload is None:
        return

    if isinstance(payload, (int, float)) and not isinstance(payload, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and payload < minimum:
            raise SchemaValidationError(f"{path}: {payload} < minimum {minimum}")
        if maximum is not None and payload > maximum:
            raise SchemaValidationError(f"{path}: {payload} > maximum {maximum}")

    fmt = schema.get("format")
    if fmt:
        _validate_format(payload, fmt, path)

    if isinstance(payload, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in payload:
                raise SchemaValidationError(f"{path}: missing required key {key!r}")

        properties = schema.get("properties", {})
        additional_allowed = schema.get("additionalProperties", True)
        for key, value in payload.items():
            if key in properties:
                validate_payload(properties[key], value, f"{path}.{key}")
            elif additional_allowed is False:
                raise SchemaValidationError(f"{path}: unexpected property {key!r}")

    if isinstance(payload, list):
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(payload):
                validate_payload(item_schema, item, f"{path}[{index}]")


def validate_document(schema_name: str, payload: Any) -> None:
    validate_payload(load_schema(schema_name), payload)


def validate_file(schema_name: str, path: Path) -> None:
    validate_document(schema_name, json.loads(path.read_text(encoding="utf-8")))
