"""Local workspace UI instance registry.

This module stores derived runtime state for locally launched OpenDream web UI
instances. It never becomes canonical workspace state; workspace-local
``.opendream/`` remains authoritative.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import workspace_catalog
from .storage import MemoryStore
from .util import read_json, to_iso, utc_now, write_json

REGISTRY_VERSION = 1
LOCAL_ACTION_HEADER = "X-OpenDream-Local-Action"
LOCAL_ACTION_VALUE = "1"


def registry_path(home: Path | None = None) -> Path:
    return workspace_catalog.catalog_home(home) / "web-instances.json"


def _empty_registry() -> dict[str, Any]:
    return {"version": REGISTRY_VERSION, "instances": []}


def load_registry(home: Path | None = None) -> dict[str, Any]:
    data = read_json(registry_path(home), _empty_registry())
    if not isinstance(data, dict) or "instances" not in data:
        return _empty_registry()
    data.setdefault("version", REGISTRY_VERSION)
    if not isinstance(data.get("instances"), list):
        data["instances"] = []
    return data


def save_registry(registry: dict[str, Any], home: Path | None = None) -> None:
    path = registry_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, registry)


def normalize_workspace_path(workspace: Path | str) -> str:
    return str(Path(workspace).expanduser().resolve())


def _find_raw_instance(registry: dict[str, Any], workspace_path: str) -> dict[str, Any] | None:
    for item in registry.get("instances", []):
        if isinstance(item, dict) and item.get("workspace_path") == workspace_path:
            return item
    return None


def _process_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _port_open(host: str, port: int, *, timeout: float = 0.15) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def allocate_port(host: str = "127.0.0.1", preferred: int | None = None) -> int:
    """Return an available localhost port.

    If ``preferred`` is supplied, it must be free. Otherwise the OS chooses an
    ephemeral port. The caller should bind/launch promptly because this is a
    lease candidate, not a kernel-held reservation.
    """
    port = int(preferred or 0)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        return int(sock.getsockname()[1])


def instance_state(workspace: Path | str, *, home: Path | None = None) -> dict[str, Any]:
    workspace_path = normalize_workspace_path(workspace)
    registry = load_registry(home)
    raw = _find_raw_instance(registry, workspace_path)
    if raw is None:
        return {
            "state": "stopped",
            "workspace_path": workspace_path,
            "owned": False,
        }

    host = str(raw.get("host") or "127.0.0.1")
    port = int(raw.get("port") or 0)
    pid = int(raw.get("pid") or 0)
    owned = bool(raw.get("owned"))
    alive = _process_alive(pid)
    listening = bool(port and _port_open(host, port))
    if alive and listening:
        state = "running"
    elif alive:
        state = "starting"
    else:
        state = "stale"
    out = dict(raw)
    out.update({
        "workspace_path": workspace_path,
        "state": state,
        "owned": owned,
        "pid_alive": alive,
        "listening": listening,
        "url": raw.get("url") or (f"http://{host}:{port}" if port else None),
    })
    return out


def enrich_entry(entry: dict[str, Any], *, home: Path | None = None) -> dict[str, Any]:
    workspace_path = entry.get("workspace_path") or entry.get("path") or entry.get("workspace")
    enriched = dict(entry)
    if isinstance(workspace_path, str) and workspace_path:
        enriched["instance"] = instance_state(workspace_path, home=home)
    return enriched


def find_initialized_workspace(start: Path | str) -> Path | None:
    current = Path(start).expanduser().resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        probe = workspace_catalog.probe_workspace(candidate)
        if probe.status_kind == "ok":
            return candidate
    return None


def resolve_current_context(cwd: Path | str | None = None, *, home: Path | None = None) -> dict[str, Any]:
    current = Path(cwd or Path.cwd()).expanduser().resolve()
    initialized = find_initialized_workspace(current)
    if initialized is not None:
        return {
            "status": "workspace",
            "current_path": str(current),
            "workspace_path": str(initialized),
            "source": "current" if initialized == current else "ancestor",
            "not_initialized": False,
        }
    entry = workspace_catalog.inspect_entry(current, home=home)
    if entry is not None:
        return {
            "status": "cataloged",
            "current_path": str(current),
            "workspace_path": str(current),
            "source": "catalog",
            "entry": entry,
            "not_initialized": False,
        }
    return {
        "status": "not_initialized",
        "current_path": str(current),
        "workspace_path": None,
        "source": "cwd",
        "not_initialized": True,
        "actions": ["initialize_here", "add_root", "scan_roots"],
    }


def dashboard_payload(
    entries: list[dict[str, Any]],
    *,
    current_path: Path | str | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    enriched = [enrich_entry(entry, home=home) for entry in entries]
    states = [
        (entry.get("instance") or {}).get("state")
        for entry in enriched
        if isinstance(entry.get("instance"), dict)
    ]
    return {
        "entries": enriched,
        "instance_summary": {
            "running": sum(1 for state in states if state == "running"),
            "starting": sum(1 for state in states if state == "starting"),
            "stale": sum(1 for state in states if state == "stale"),
            "stopped": sum(1 for state in states if state == "stopped"),
        },
        "current_context": resolve_current_context(current_path, home=home) if current_path else None,
    }


def _upsert_raw_instance(instance: dict[str, Any], *, home: Path | None = None) -> None:
    registry = load_registry(home)
    workspace_path = str(instance["workspace_path"])
    kept = [
        item for item in registry.get("instances", [])
        if not (isinstance(item, dict) and item.get("workspace_path") == workspace_path)
    ]
    kept.append(instance)
    registry["instances"] = kept
    save_registry(registry, home)


def _remove_raw_instance(workspace_path: str, *, home: Path | None = None) -> None:
    registry = load_registry(home)
    registry["instances"] = [
        item for item in registry.get("instances", [])
        if not (isinstance(item, dict) and item.get("workspace_path") == workspace_path)
    ]
    save_registry(registry, home)


def launch_workspace(
    workspace: Path | str,
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
    home: Path | None = None,
    wait_seconds: float = 5.0,
) -> dict[str, Any]:
    workspace_path = normalize_workspace_path(workspace)
    entry = workspace_catalog.inspect_entry(workspace_path, home=home)
    if entry is None:
        raise ValueError(f"workspace is not cataloged: {workspace_path}")
    existing = instance_state(workspace_path, home=home)
    if existing.get("state") == "running":
        return {"status": "running", "instance": existing}

    actual_port = allocate_port(host, port)
    command = [
        sys.executable,
        "-m",
        "opendream.cli",
        "observe",
        "serve",
        "--workspace",
        workspace_path,
        "--host",
        host,
        "--port",
        str(actual_port),
    ]
    process = subprocess.Popen(  # noqa: S603 - local CLI command with fixed argv
        command,
        cwd=workspace_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    now = to_iso(utc_now())
    raw = {
        "workspace_path": workspace_path,
        "host": host,
        "port": actual_port,
        "url": f"http://{host}:{actual_port}",
        "pid": int(process.pid),
        "owned": True,
        "command": command,
        "started_at": now,
        "updated_at": now,
    }
    _upsert_raw_instance(raw, home=home)

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        state = instance_state(workspace_path, home=home)
        if state.get("state") == "running":
            return {"status": "running", "instance": state}
        if not _process_alive(process.pid):
            break
        time.sleep(0.1)
    return {"status": "starting", "instance": instance_state(workspace_path, home=home)}


def stop_workspace(workspace: Path | str, *, home: Path | None = None) -> dict[str, Any]:
    workspace_path = normalize_workspace_path(workspace)
    state = instance_state(workspace_path, home=home)
    if not state.get("owned"):
        raise ValueError("refusing to stop unmanaged workspace instance")
    pid = int(state.get("pid") or 0)
    if pid and _process_alive(pid):
        os.kill(pid, signal.SIGTERM)
    _remove_raw_instance(workspace_path, home=home)
    return {
        "status": "stopped",
        "workspace_path": workspace_path,
        "instance": instance_state(workspace_path, home=home),
    }


def restart_workspace(
    workspace: Path | str,
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    state = instance_state(workspace, home=home)
    if state.get("owned") and state.get("state") in {"running", "starting", "stale"}:
        stop_workspace(workspace, home=home)
    elif state.get("state") in {"running", "starting"}:
        raise ValueError("refusing to restart unmanaged workspace instance")
    result = launch_workspace(workspace, host=host, port=port, home=home)
    result["status"] = "restarted" if result.get("status") == "running" else result.get("status", "starting")
    return result


def initialize_workspace(
    workspace: Path | str,
    *,
    home: Path | None = None,
    memory_dir: str | None = None,
    compat_mode: str | None = None,
) -> dict[str, Any]:
    workspace_path = normalize_workspace_path(workspace)
    store = MemoryStore(Path(workspace_path), memory_dir=memory_dir, compat_mode=compat_mode)
    metadata = store.initialize(store_kind="project", compat_mode=compat_mode)
    catalog_update = workspace_catalog.safe_update(
        workspace_path,
        discovered_by="init",
        home=home,
    )
    return {
        "status": "initialized",
        "workspace_path": workspace_path,
        "metadata": metadata,
        "catalog_update": catalog_update,
        "current_context": resolve_current_context(workspace_path, home=home),
    }
