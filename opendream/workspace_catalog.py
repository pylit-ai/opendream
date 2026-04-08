"""Machine-local workspace catalog.

The catalog is a derived convenience index of OpenDream workspaces known on
this machine. It is NEVER canonical: per-workspace ``.opendream/`` state
remains the source of truth. Catalog entries can be safely rebuilt from
workspace-local state.

See ``openspec/changes/441-workspace-catalog-dashboard-bundle`` for the
proposal and ``docs/adr/ADR-017-machine-local-workspace-catalog.md``.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .util import read_json, to_iso, utc_now, write_json
from .validation import validate_document

CATALOG_VERSION = 1
ROOTS_VERSION = 1

DISCOVERED_BY = Literal["init", "activate", "scan", "install-service", "manual-add", "status"]
STATUS_KIND = Literal["ok", "stale", "missing", "broken"]

CATALOG_SCHEMA = "workspace-catalog.schema.json"
ROOTS_SCHEMA = "workspace-roots.schema.json"
SCAN_REPORT_SCHEMA = "workspace-scan-report.schema.json"


def catalog_home(override: Path | None = None) -> Path:
    """Return the machine-local catalog home directory.

    Honors (in order): explicit ``override`` argument, ``OPENDREAM_CATALOG_HOME``
    environment variable, ``~/.opendream``.
    """
    if override is not None:
        return Path(override).expanduser().resolve()
    env = os.environ.get("OPENDREAM_CATALOG_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / ".opendream").resolve()


def catalog_path(home: Path | None = None) -> Path:
    return catalog_home(home) / "catalog.json"


def roots_path(home: Path | None = None) -> Path:
    return catalog_home(home) / "roots.json"


def _empty_catalog() -> dict[str, Any]:
    return {"version": CATALOG_VERSION, "entries": []}


def _empty_roots() -> dict[str, Any]:
    return {"version": ROOTS_VERSION, "roots": []}


def load_catalog(home: Path | None = None) -> dict[str, Any]:
    data = read_json(catalog_path(home), _empty_catalog())
    if not isinstance(data, dict) or "entries" not in data:
        return _empty_catalog()
    # Defensive normalization: ensure version and list types.
    data.setdefault("version", CATALOG_VERSION)
    if not isinstance(data.get("entries"), list):
        data["entries"] = []
    return data


def save_catalog(catalog: dict[str, Any], home: Path | None = None) -> None:
    validate_document(CATALOG_SCHEMA, catalog)
    path = catalog_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, catalog)


def load_roots(home: Path | None = None) -> dict[str, Any]:
    data = read_json(roots_path(home), _empty_roots())
    if not isinstance(data, dict) or "roots" not in data:
        return _empty_roots()
    data.setdefault("version", ROOTS_VERSION)
    if not isinstance(data.get("roots"), list):
        data["roots"] = []
    return data


def save_roots(roots: dict[str, Any], home: Path | None = None) -> None:
    validate_document(ROOTS_SCHEMA, roots)
    path = roots_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, roots)


def _normalize_workspace_path(workspace: Path | str) -> str:
    return str(Path(workspace).expanduser().resolve())


def _find_entry(catalog: dict[str, Any], workspace_path: str) -> dict[str, Any] | None:
    for entry in catalog["entries"]:
        if not isinstance(entry, dict):
            continue
        if entry.get("workspace_path") == workspace_path:
            return entry
    return None


@dataclass
class ProbeResult:
    """Result of probing a workspace for health."""

    status_kind: STATUS_KIND
    memory_dir: str | None = None
    activation_summary: str | None = None
    service_summary: str | None = None
    semantic_summary: str | None = None
    notes: list[str] = field(default_factory=list)


def probe_workspace(workspace: Path | str) -> ProbeResult:
    """Lazy, read-only probe of a workspace's health.

    Does not mutate workspace state. Returns a status kind plus summary strings
    suitable for display in the catalog/dashboard.
    """
    ws = Path(workspace).expanduser()
    notes: list[str] = []

    if not ws.exists():
        return ProbeResult(status_kind="missing", notes=["workspace path does not exist"])

    opendream_dir = ws / ".opendream"
    legacy_dir = ws / "memory"

    memory_root: Path | None = None
    memory_dir: str | None = None
    if (opendream_dir / "memory").exists():
        memory_root = opendream_dir / "memory"
        memory_dir = ".opendream/memory"
    elif (legacy_dir / "state" / "store.json").exists():
        memory_root = legacy_dir
        memory_dir = "memory"
    else:
        return ProbeResult(
            status_kind="broken",
            notes=["no .opendream/memory or legacy memory/ layout found"],
        )

    state_dir = memory_root / "state"
    # activation-state.json is workspace-relative at .opendream/activation-state.json,
    # not under memory/state/. See opendream.activation.ACTIVATION_STATE_PATH.
    activation_state = ws / ".opendream" / "activation-state.json"
    service_manifest = state_dir / "service_manifest.json"
    service_runtime = state_dir / "service_runtime.json"
    semantic_config = state_dir / "semantic_config.json"
    store_json = state_dir / "store.json"

    if not store_json.exists():
        return ProbeResult(
            status_kind="broken",
            memory_dir=memory_dir,
            notes=["store.json missing"],
        )

    activation_summary: str | None
    if activation_state.exists():
        payload = read_json(activation_state, {})
        targets = payload.get("targets") if isinstance(payload, dict) else None
        if isinstance(targets, list) and targets:
            active = sum(1 for t in targets if isinstance(t, dict) and t.get("activated"))
            activation_summary = f"activated:{active}/{len(targets)} targets"
        elif isinstance(payload, dict) and payload:
            activation_summary = "activated"
        else:
            activation_summary = "not activated"
    else:
        activation_summary = "not activated"

    service_summary: str | None
    if service_manifest.exists():
        payload = read_json(service_manifest, {})
        if isinstance(payload, dict) and payload:
            mode = payload.get("backend_mode")
            service_summary = f"installed ({mode})" if mode else "installed"
            if service_runtime.exists():
                runtime = read_json(service_runtime, {})
                status = runtime.get("status") if isinstance(runtime, dict) else None
                if status:
                    service_summary = f"{service_summary}:{status}"
        else:
            service_summary = None
    else:
        service_summary = None

    semantic_summary: str | None
    if semantic_config.exists():
        payload = read_json(semantic_config, {})
        mode = payload.get("mode") if isinstance(payload, dict) else None
        semantic_summary = f"semantic:{mode}" if mode else "semantic:on"
    else:
        semantic_summary = None

    # Simple staleness heuristic: if workspace subtree mtime has not been touched
    # in a very long time, callers may mark it stale from the CLI layer; we don't
    # enforce that here to keep probes cheap and deterministic.

    return ProbeResult(
        status_kind="ok",
        memory_dir=memory_dir,
        activation_summary=activation_summary,
        service_summary=service_summary,
        semantic_summary=semantic_summary,
        notes=notes,
    )


def upsert_entry(
    workspace: Path | str,
    *,
    discovered_by: DISCOVERED_BY,
    home: Path | None = None,
    probe: ProbeResult | None = None,
) -> dict[str, Any]:
    """Add or update a catalog entry for ``workspace``.

    Returns the updated entry. Probes the workspace if no ``probe`` is supplied.
    """
    workspace_path = _normalize_workspace_path(workspace)
    now = to_iso(utc_now())
    catalog = load_catalog(home)
    entry = _find_entry(catalog, workspace_path)
    probe = probe or probe_workspace(workspace_path)
    ws = Path(workspace_path)
    if entry is None:
        entry = {
            "workspace_path": workspace_path,
            "workspace_name": ws.name or workspace_path,
            "repo_root_name": ws.parent.name or None,
            "first_seen_at": now,
            "last_seen_at": now,
            "discovered_by": discovered_by,
            "memory_dir": probe.memory_dir,
            "activation_state_summary": probe.activation_summary,
            "service_state_summary": probe.service_summary,
            "semantic_state_summary": probe.semantic_summary,
            "last_probe_at": now,
            "status_kind": probe.status_kind,
            "notes": list(probe.notes),
        }
        catalog["entries"].append(entry)
    else:
        entry["last_seen_at"] = now
        entry["discovered_by"] = discovered_by
        entry["memory_dir"] = probe.memory_dir
        entry["activation_state_summary"] = probe.activation_summary
        entry["service_state_summary"] = probe.service_summary
        entry["semantic_state_summary"] = probe.semantic_summary
        entry["last_probe_at"] = now
        entry["status_kind"] = probe.status_kind
        entry["notes"] = list(probe.notes)
    save_catalog(catalog, home)
    return entry


def refresh_entry(workspace: Path | str, *, home: Path | None = None) -> dict[str, Any] | None:
    """Re-probe an existing entry without changing ``discovered_by``."""
    workspace_path = _normalize_workspace_path(workspace)
    catalog = load_catalog(home)
    entry = _find_entry(catalog, workspace_path)
    if entry is None:
        return None
    probe = probe_workspace(workspace_path)
    entry["memory_dir"] = probe.memory_dir
    entry["activation_state_summary"] = probe.activation_summary
    entry["service_state_summary"] = probe.service_summary
    entry["semantic_state_summary"] = probe.semantic_summary
    entry["last_probe_at"] = to_iso(utc_now())
    entry["status_kind"] = probe.status_kind
    entry["notes"] = list(probe.notes)
    save_catalog(catalog, home)
    return entry


def forget_workspace(workspace: Path | str, *, home: Path | None = None) -> bool:
    """Remove only the catalog entry for ``workspace``.

    Does NOT touch the workspace-local ``.opendream/`` state.
    Returns True if an entry was removed.
    """
    workspace_path = _normalize_workspace_path(workspace)
    catalog = load_catalog(home)
    before = len(catalog["entries"])
    catalog["entries"] = [e for e in catalog["entries"] if e.get("workspace_path") != workspace_path]
    if len(catalog["entries"]) == before:
        return False
    save_catalog(catalog, home)
    return True


def list_entries(home: Path | None = None) -> list[dict[str, Any]]:
    catalog = load_catalog(home)
    return list(catalog["entries"])


def inspect_entry(workspace: Path | str, *, home: Path | None = None) -> dict[str, Any] | None:
    workspace_path = _normalize_workspace_path(workspace)
    catalog = load_catalog(home)
    return _find_entry(catalog, workspace_path)


def add_root(root: Path | str, *, home: Path | None = None) -> bool:
    root_path = str(Path(root).expanduser().resolve())
    roots = load_roots(home)
    if root_path in roots["roots"]:
        return False
    roots["roots"].append(root_path)
    save_roots(roots, home)
    return True


def remove_root(root: Path | str, *, home: Path | None = None) -> bool:
    root_path = str(Path(root).expanduser().resolve())
    roots = load_roots(home)
    if root_path not in roots["roots"]:
        return False
    roots["roots"] = [r for r in roots["roots"] if r != root_path]
    save_roots(roots, home)
    return True


def list_roots(home: Path | None = None) -> list[str]:
    return list(load_roots(home)["roots"])


# Maximum directory depth to walk when scanning a root. Chosen to find
# workspaces within a few levels of a developer's src/ tree without doing a
# whole-disk crawl.
_SCAN_MAX_DEPTH = 6
# Directory basenames that are never interesting to walk into.
_SCAN_PRUNE = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".tox",
    }
)


def _walk_for_workspaces(root: Path, *, max_depth: int = _SCAN_MAX_DEPTH) -> list[Path]:
    """Yield workspaces (directories that contain a ``.opendream/`` dir).

    Prunes common noisy directories and bounds recursion depth so the scan is
    cheap and explicit.
    """
    root = root.resolve()
    discovered: list[Path] = []
    if not root.exists() or not root.is_dir():
        return discovered
    # BFS with depth tracking.
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        if (current / ".opendream").is_dir() or (current / "memory" / "state" / "store.json").exists():
            discovered.append(current)
            # Do not descend further — the workspace itself is the leaf we care about.
            continue
        if depth >= max_depth:
            continue
        try:
            children = list(current.iterdir())
        except (PermissionError, OSError):
            continue
        for child in children:
            if not child.is_dir() or child.is_symlink():
                continue
            if child.name in _SCAN_PRUNE or child.name.startswith("."):
                # Still allow .opendream detection above, but skip hidden descent.
                continue
            stack.append((child, depth + 1))
    return discovered


def scan_root(root: Path | str, *, home: Path | None = None) -> dict[str, Any]:
    """Scan a single root path for workspaces and update the catalog.

    Returns a scan report conforming to ``workspace-scan-report.schema.json``.
    """
    return scan_roots([root], home=home)


def scan_roots(
    roots: list[Path | str] | None = None,
    *,
    home: Path | None = None,
    all_roots: bool = False,
) -> dict[str, Any]:
    """Scan the given roots (or configured roots when ``all_roots=True``).

    Returns a scan report conforming to ``workspace-scan-report.schema.json``.
    Never silently scans arbitrary locations: callers must pass explicit roots,
    or ``all_roots=True`` to use persisted configured roots.
    """
    if all_roots and not roots:
        roots = [Path(r) for r in list_roots(home)]
    if not roots:
        report = {
            "roots_scanned": [],
            "discovered": [],
            "updated": [],
            "skipped": [],
            "errors": ["no roots supplied and no configured roots available"],
        }
        validate_document(SCAN_REPORT_SCHEMA, report)
        return report

    roots_scanned: list[str] = []
    discovered: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for raw in roots:
        root = Path(raw).expanduser().resolve()
        roots_scanned.append(str(root))
        if not root.exists():
            errors.append(f"root does not exist: {root}")
            continue
        try:
            workspaces = _walk_for_workspaces(root)
        except OSError as exc:
            errors.append(f"scan failed for {root}: {exc}")
            continue
        for ws in workspaces:
            ws_str = str(ws)
            catalog_before = load_catalog(home)
            existed = _find_entry(catalog_before, ws_str) is not None
            try:
                upsert_entry(ws, discovered_by="scan", home=home)
            except Exception as exc:  # noqa: BLE001 - surface all failures explicitly
                errors.append(f"{ws_str}: {exc}")
                skipped.append(ws_str)
                continue
            if existed:
                updated.append(ws_str)
            else:
                discovered.append(ws_str)

    report = {
        "roots_scanned": roots_scanned,
        "discovered": discovered,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }
    validate_document(SCAN_REPORT_SCHEMA, report)
    return report


def doctor(
    workspace: Path | str | None = None,
    *,
    home: Path | None = None,
    all_workspaces: bool = False,
) -> dict[str, Any]:
    """Diagnose workspace catalog entries.

    If ``workspace`` is provided, only that entry is doctored (or inserted).
    If ``all_workspaces`` is True, every known entry is re-probed.
    """
    catalog = load_catalog(home)
    results: list[dict[str, Any]] = []
    if workspace is not None:
        ws = _normalize_workspace_path(workspace)
        probe = probe_workspace(ws)
        entry = refresh_entry(ws, home=home)
        if entry is None:
            entry = upsert_entry(ws, discovered_by="manual-add", home=home, probe=probe)
        results.append(entry)
    elif all_workspaces:
        for existing in list(catalog["entries"]):
            refreshed = refresh_entry(existing["workspace_path"], home=home)
            if refreshed is not None:
                results.append(refreshed)
    else:
        raise ValueError("doctor requires either a workspace or all_workspaces=True")

    return {
        "doctored": len(results),
        "entries": results,
    }


def _tempdir_prefixes() -> tuple[str, ...]:
    prefixes: set[str] = set()
    with contextlib.suppress(OSError):
        prefixes.add(str(Path(tempfile.gettempdir()).resolve()))
    # macOS resolves /var -> /private/var; capture both so resolved workspace
    # paths under /private/var/folders/... are recognized as temp.
    prefixes.add("/tmp")
    prefixes.add("/private/tmp")
    prefixes.add("/private/var/folders")
    prefixes.add("/var/folders")
    return tuple(prefixes)


def _workspace_is_under_tempdir(workspace: Path | str) -> bool:
    try:
        resolved = str(Path(workspace).expanduser().resolve())
    except OSError:
        return False
    return any(resolved == p or resolved.startswith(p + os.sep) for p in _tempdir_prefixes())


def _is_test_runner_active() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    if "_pytest" in sys.modules or "pytest" in sys.modules:
        return True
    argv0 = (sys.argv[0] if sys.argv else "") or ""
    return "unittest" in argv0 or "pytest" in argv0


def _is_sandboxed_environment() -> bool:
    """Return True when the current process should not touch the real home catalog.

    Prevents event-driven hooks from silently polluting the operator's real
    ``~/.opendream/catalog.json`` during test runs that do not isolate
    ``OPENDREAM_CATALOG_HOME`` themselves. Honors an explicit
    ``OPENDREAM_CATALOG_HOME`` override and an ``OPENDREAM_CATALOG_DISABLE``
    kill switch.
    """
    if os.environ.get("OPENDREAM_CATALOG_DISABLE"):
        return True
    if os.environ.get("OPENDREAM_CATALOG_HOME"):
        return False
    return _is_test_runner_active()


def safe_update(
    workspace: Path | str,
    *,
    discovered_by: DISCOVERED_BY,
    home: Path | None = None,
) -> dict[str, Any]:
    """Update the catalog but never raise: returns a structured status.

    Used from event-driven hooks (init/activate/install-service) so a catalog
    failure does not corrupt the primary command's return value. Failures are
    surfaced explicitly via the ``catalog_update`` block in the command result.
    """
    if home is None and _is_sandboxed_environment():
        return {
            "status": "skipped",
            "reason": "sandboxed-environment",
            "workspace": _normalize_workspace_path(workspace),
        }
    if (
        home is None
        and not os.environ.get("OPENDREAM_CATALOG_HOME")
        and _workspace_is_under_tempdir(workspace)
    ):
        # Refuse to write the real home catalog for transient tempdir
        # workspaces. Tests, scripted fixtures, and one-off scratch runs should
        # never accumulate entries in the operator's real catalog. Callers that
        # genuinely want to track a tempdir workspace can pass an explicit
        # ``home`` or set ``OPENDREAM_CATALOG_HOME``.
        return {
            "status": "skipped",
            "reason": "tempdir-workspace",
            "workspace": _normalize_workspace_path(workspace),
        }
    try:
        entry = upsert_entry(workspace, discovered_by=discovered_by, home=home)
    except Exception as exc:  # noqa: BLE001 - event hooks must never crash the caller
        return {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "workspace": _normalize_workspace_path(workspace),
        }
    return {
        "status": "ok",
        "workspace": entry["workspace_path"],
        "status_kind": entry["status_kind"],
    }
