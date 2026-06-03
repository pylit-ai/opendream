from __future__ import annotations

from collections.abc import Iterable

WORKFLOW_MEMORY_TYPE = "workflow"
LEGACY_WORKFLOW_MEMORY_TYPE = "procedural_workflow"
WORKFLOW_MEMORY_TYPES = frozenset({WORKFLOW_MEMORY_TYPE, LEGACY_WORKFLOW_MEMORY_TYPE})


def canonical_memory_type(memory_type: object) -> str:
    value = str(memory_type or "").strip().lower()
    if value == LEGACY_WORKFLOW_MEMORY_TYPE:
        return WORKFLOW_MEMORY_TYPE
    return value


def is_workflow_memory_type(memory_type: object) -> bool:
    return canonical_memory_type(memory_type) == WORKFLOW_MEMORY_TYPE


def memory_type_matches(record_type: object, selectors: Iterable[object]) -> bool:
    selected = {canonical_memory_type(item) for item in selectors if str(item).strip()}
    return not selected or canonical_memory_type(record_type) in selected
