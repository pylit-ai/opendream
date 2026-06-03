"""Runtime boundary enforcement for dream and semantic workers.

Workers may read the repo within configured bounds but may only write under
memory/ and bounded audit artifact directories. This module provides path
allowlist enforcement, no-code-write diff verification, and boundary violation
reporting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .util import stable_id, to_iso, utc_now

VALID_RELATION_EDGE_KINDS = frozenset({
    "supports",
    "conflicts_with",
    "supersedes",
    "derived_from",
    "verified_by",
    "invalidated_by",
})


class BoundaryViolation(RuntimeError):
    """Raised when a worker attempts to write outside allowed paths."""


def default_allowed_write_roots(memory_root: Path) -> list[Path]:
    """Return the default set of directories workers are allowed to write to."""
    return [
        memory_root,
    ]


def check_write_allowed(
    target_path: Path,
    *,
    allowed_roots: list[Path],
) -> tuple[bool, str]:
    """Check whether a write to *target_path* is permitted.

    Returns (allowed, reason).
    """
    resolved = target_path.resolve()
    for root in allowed_roots:
        try:
            resolved.relative_to(root.resolve())
            return True, f"within allowed root {root}"
        except ValueError:
            continue
    return False, f"path {resolved} is outside all allowed write roots"


def enforce_write_boundary(
    target_path: Path,
    *,
    allowed_roots: list[Path],
) -> None:
    """Raise :class:`BoundaryViolation` if write is not allowed."""
    allowed, reason = check_write_allowed(target_path, allowed_roots=allowed_roots)
    if not allowed:
        raise BoundaryViolation(reason)


def verify_no_code_writes(
    before_snapshot: dict[str, str],
    after_snapshot: dict[str, str],
    *,
    memory_root: Path,
) -> dict[str, Any]:
    """Compare before/after file snapshots and verify only memory paths changed.

    Returns a verification report dict.
    """
    now = to_iso(utc_now())
    report_id = stable_id("boundary-verify", now)
    changed_paths: list[str] = []
    allowed_memory_writes: list[str] = []
    blocked_code_writes: list[str] = []
    memory_root_resolved = memory_root.resolve()

    all_paths = set(before_snapshot.keys()) | set(after_snapshot.keys())
    for path_str in sorted(all_paths):
        before = before_snapshot.get(path_str)
        after = after_snapshot.get(path_str)
        if before != after:
            changed_paths.append(path_str)
            if _snapshot_path_is_under_memory_root(path_str, memory_root_resolved):
                allowed_memory_writes.append(path_str)
            else:
                blocked_code_writes.append(path_str)

    return {
        "report_id": report_id,
        "verified_at": now,
        "changed_paths": changed_paths,
        "allowed_memory_writes": allowed_memory_writes,
        "blocked_code_writes": blocked_code_writes,
        "code_writes": blocked_code_writes,
        "passed": len(blocked_code_writes) == 0,
        "violations": [
            f"code write detected: {p}" for p in blocked_code_writes
        ],
    }


def _snapshot_path_is_under_memory_root(path_str: str, memory_root_resolved: Path) -> bool:
    path = Path(path_str)
    candidates: list[Path] = []
    if path.is_absolute():
        candidates.append(path)
    else:
        parts = path.parts
        if parts and parts[0] == memory_root_resolved.name:
            candidates.append(memory_root_resolved.parent / path)
        if (
            len(parts) >= 2
            and parts[0] == memory_root_resolved.parent.name
            and parts[1] == memory_root_resolved.name
        ):
            candidates.append(memory_root_resolved.parent.parent / path)
        candidates.append(Path.cwd() / path)

    for candidate in candidates:
        try:
            candidate.resolve().relative_to(memory_root_resolved)
            return True
        except ValueError:
            continue
    return False


def boundary_enforcement_report(
    *,
    worker_type: str,
    allowed_roots: list[Path],
    violations: list[dict[str, Any]] | None = None,
    allowed_memory_writes: list[str] | None = None,
    blocked_code_writes: list[str] | None = None,
) -> dict[str, Any]:
    """Produce a summary report of boundary enforcement for a worker run."""
    now = to_iso(utc_now())
    return {
        "report_id": stable_id("boundary-report", worker_type, now),
        "worker_type": worker_type,
        "runtime_mode": "memory-only",
        "allowed_write_roots": [str(r.resolve()) for r in allowed_roots],
        "allowed_memory_writes": allowed_memory_writes or [],
        "blocked_code_writes": blocked_code_writes or [],
        "violations": violations or [],
        "enforced": True,
        "generated_at": now,
    }
