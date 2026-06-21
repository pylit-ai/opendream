from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .storage import MemoryStore

FULL_INDEX_KEY = "observability_index"
COMPACT_INDEX_KEY = "observability_compact_index"
GENERATED_CACHE_KEYS = (FULL_INDEX_KEY, COMPACT_INDEX_KEY)


@dataclass(frozen=True)
class CacheArtifact:
    key: str
    path_attr: str
    role: str
    max_bytes_config_key: str
    prunable_by_default: bool


CACHE_ARTIFACTS: tuple[CacheArtifact, ...] = (
    CacheArtifact(
        key=FULL_INDEX_KEY,
        path_attr="observability_index_path",
        role="derived full observability read model",
        max_bytes_config_key="observability_index_max_bytes",
        prunable_by_default=True,
    ),
    CacheArtifact(
        key=COMPACT_INDEX_KEY,
        path_attr="observability_compact_index_path",
        role="derived compact observability read model",
        max_bytes_config_key="observability_compact_index_max_bytes",
        prunable_by_default=False,
    ),
)


def _artifact_path(store: MemoryStore, artifact: CacheArtifact) -> Path:
    value = getattr(store, artifact.path_attr)
    return value if isinstance(value, Path) else Path(str(value))


def _path_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _relative_to_workspace(store: MemoryStore, path: Path) -> str:
    try:
        return str(path.relative_to(store.workspace))
    except ValueError:
        return str(path)


def _git_path_state(store: MemoryStore, path: Path) -> dict[str, Any]:
    workspace = store.workspace
    try:
        root = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return {"available": False, "tracked": False, "ignored": None}
    if not root:
        return {"available": False, "tracked": False, "ignored": None}
    repo_root = Path(root)
    try:
        rel = str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return {"available": True, "tracked": False, "ignored": None}
    tracked = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", rel],
        capture_output=True,
        text=True,
        check=False,
    ).returncode == 0
    ignored = subprocess.run(
        ["git", "-C", str(repo_root), "check-ignore", "-q", rel],
        capture_output=True,
        text=True,
        check=False,
    ).returncode == 0
    return {
        "available": True,
        "repo_root": str(repo_root),
        "relative_path": rel,
        "tracked": tracked,
        "ignored": ignored,
    }


def cache_config(store: MemoryStore) -> dict[str, Any]:
    config = store.load_cache_config()
    return {
        "persist_full_observability_index": bool(config.get("persist_full_observability_index", True)),
        "observability_index_max_bytes": int(config.get("observability_index_max_bytes", 0) or 0),
        "observability_compact_index_max_bytes": int(
            config.get("observability_compact_index_max_bytes", 0) or 0
        ),
    }


def configure_cache(
    store: MemoryStore,
    *,
    persist_full_observability_index: bool | None = None,
    observability_index_max_bytes: int | None = None,
    observability_compact_index_max_bytes: int | None = None,
) -> dict[str, Any]:
    update: dict[str, Any] = {}
    if persist_full_observability_index is not None:
        update["persist_full_observability_index"] = persist_full_observability_index
    if observability_index_max_bytes is not None:
        if observability_index_max_bytes < 0:
            raise ValueError("--max-full-index-bytes must be >= 0")
        update["observability_index_max_bytes"] = observability_index_max_bytes
    if observability_compact_index_max_bytes is not None:
        if observability_compact_index_max_bytes < 0:
            raise ValueError("--max-compact-index-bytes must be >= 0")
        update["observability_compact_index_max_bytes"] = observability_compact_index_max_bytes
    if update:
        store.save_cache_config(update)
    return cache_info(store)


def cache_info(store: MemoryStore) -> dict[str, Any]:
    store.ensure_layout()
    config = cache_config(store)
    artifacts: list[dict[str, Any]] = []
    total_bytes = 0
    for artifact in CACHE_ARTIFACTS:
        path = _artifact_path(store, artifact)
        exists = path.exists()
        size = _path_size(path) if exists else 0
        total_bytes += size
        max_bytes = int(config.get(artifact.max_bytes_config_key, 0) or 0)
        artifacts.append(
            {
                "key": artifact.key,
                "role": artifact.role,
                "path": str(path),
                "relative_path": _relative_to_workspace(store, path),
                "exists": exists,
                "bytes": size,
                "max_bytes": max_bytes,
                "over_limit": bool(exists and max_bytes > 0 and size > max_bytes),
                "rebuildable": True,
                "prunable_by_default": artifact.prunable_by_default,
                "git": _git_path_state(store, path),
            }
        )
    return {
        "status": "ok",
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "config_path": str(store.cache_config_path),
        "policy": config,
        "total_bytes": total_bytes,
        "artifacts": artifacts,
    }


def verify_cache(store: MemoryStore) -> dict[str, Any]:
    info = cache_info(store)
    problems: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    persist_full = bool(info["policy"].get("persist_full_observability_index", True))
    for artifact in info["artifacts"]:
        if artifact["over_limit"]:
            problems.append(
                {
                    "code": "cache_artifact_over_limit",
                    "artifact": artifact["key"],
                    "path": artifact["path"],
                    "bytes": artifact["bytes"],
                    "max_bytes": artifact["max_bytes"],
                }
            )
        if artifact["git"].get("tracked"):
            problems.append(
                {
                    "code": "generated_cache_tracked_by_git",
                    "artifact": artifact["key"],
                    "path": artifact["git"].get("relative_path") or artifact["relative_path"],
                }
            )
        if artifact["key"] == FULL_INDEX_KEY and artifact["exists"] and not persist_full:
            problems.append(
                {
                    "code": "full_index_persistence_disabled_but_file_exists",
                    "artifact": artifact["key"],
                    "path": artifact["path"],
                }
            )
        if artifact["key"] == COMPACT_INDEX_KEY and not artifact["exists"]:
            warnings.append(
                {
                    "code": "compact_index_missing",
                    "artifact": artifact["key"],
                    "message": "The compact index is rebuilt automatically on the next observe/list request.",
                }
            )
    status = "passed" if not problems else "failed"
    return {
        **info,
        "status": status,
        "problems": problems,
        "warnings": warnings,
    }


def prune_cache(
    store: MemoryStore,
    *,
    dry_run: bool = True,
    full_index: bool = False,
    compact_index: bool = False,
    all_generated: bool = False,
) -> dict[str, Any]:
    info = cache_info(store)
    selected_keys: set[str] = set()
    if all_generated:
        selected_keys.update(GENERATED_CACHE_KEYS)
    if full_index:
        selected_keys.add(FULL_INDEX_KEY)
    if compact_index:
        selected_keys.add(COMPACT_INDEX_KEY)
    if not selected_keys:
        for artifact in info["artifacts"]:
            if artifact["prunable_by_default"] and artifact["over_limit"]:
                selected_keys.add(str(artifact["key"]))

    removed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for artifact in info["artifacts"]:
        if artifact["key"] not in selected_keys:
            skipped.append({"artifact": artifact["key"], "reason": "not-selected"})
            continue
        path = Path(str(artifact["path"]))
        if not path.exists():
            skipped.append({"artifact": artifact["key"], "reason": "missing", "path": str(path)})
            continue
        item = {"artifact": artifact["key"], "path": str(path), "bytes": artifact["bytes"]}
        if not dry_run:
            path.unlink(missing_ok=True)
        removed.append(item)
    return {
        "status": "previewed" if dry_run else "pruned",
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "dry_run": dry_run,
        "removed": removed,
        "skipped": skipped,
        "bytes_reclaimable": sum(int(item["bytes"]) for item in removed),
        "bytes_reclaimed": 0 if dry_run else sum(int(item["bytes"]) for item in removed),
    }
