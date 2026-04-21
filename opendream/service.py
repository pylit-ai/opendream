from __future__ import annotations

import json
import os
import shlex
import signal
import stat
import subprocess
import sys
import time
from contextlib import suppress
from html import escape
from pathlib import Path
from string import Template
from typing import Any

from .activation import SUPPORTED_TARGETS
from .storage import MemoryStore
from .util import (
    atomic_write_text,
    ensure_relative_to,
    parse_timestamp,
    prune_recent_failures,
    sha256_path,
    stable_id,
    to_iso,
    utc_now,
)
from .validation import validate_document

TEMPLATE_ROOT = Path(__file__).with_name("templates")
AUTOWIRE_ROOT = ".opendream/hooks"
CLAUDE_SETTINGS_PATH = Path(".claude/settings.json")
OPENCLAW_CONFIG_PATH = Path(".openclaw/config.json")
CODEX_AGENTS_PATH = Path("AGENTS.md")
CODEX_BLOCK_START = "<!-- OPENDREAM:CODEX START -->"
CODEX_BLOCK_END = "<!-- OPENDREAM:CODEX END -->"
RECENT_FAILURE_LIMIT = 5
DEFAULT_STUCK_SECONDS = 180
CRASH_LOOP_THRESHOLD = 3
CLAUDE_PRE_TASK_COMMAND = (
    'env OPENDREAM_WORKSPACE="$CLAUDE_PROJECT_DIR" '
    'sh "$CLAUDE_PROJECT_DIR"/.opendream/hooks/claude-pre-task.sh'
)
CLAUDE_POST_TASK_COMMAND = (
    'env OPENDREAM_WORKSPACE="$CLAUDE_PROJECT_DIR" '
    'sh "$CLAUDE_PROJECT_DIR"/.opendream/hooks/claude-post-task.sh'
)
_MANAGED_PROCESS_HANDLES: dict[str, subprocess.Popen[bytes]] = {}


def detect_supervisor() -> str:
    if sys.platform == "darwin":
        return "launchd"
    if sys.platform.startswith("linux"):
        return "systemd"
    raise ValueError(f"unsupported platform for service lifecycle: {sys.platform}")


def service_label(store: MemoryStore) -> str:
    return f"ai.opendream.worker.{store.store_id[-12:]}"


def service_filename(supervisor_kind: str, label: str) -> str:
    suffix = ".plist" if supervisor_kind == "launchd" else ".service"
    return f"{label}{suffix}"


def default_install_root(supervisor_kind: str, service_mode: str) -> Path:
    if supervisor_kind == "launchd":
        if service_mode == "system":
            return Path("/Library/LaunchDaemons")
        return Path.home() / "Library" / "LaunchAgents"
    if service_mode == "system":
        return Path("/etc/systemd/system")
    return Path.home() / ".config" / "systemd" / "user"


def _managed_install_root(store: MemoryStore) -> Path:
    return store.state_dir / "service" / "managed"


def _default_management_mode(store: MemoryStore) -> str:
    return "managed" if store.store_kind == "project" else "disabled"


def _service_policy_payload(store: MemoryStore, runtime: dict[str, Any]) -> dict[str, Any]:
    default_mode = _default_management_mode(store)
    configured = str(runtime.get("management_mode") or default_mode)
    management_mode = configured if configured in {"managed", "disabled"} else default_mode
    return {
        "management_mode": management_mode,
        "auto_ensure": management_mode == "managed",
        "source": "workspace-state" if "management_mode" in runtime else "default",
    }


def set_service_management_mode(store: MemoryStore, management_mode: str) -> dict[str, Any]:
    if management_mode not in {"managed", "disabled"}:
        raise ValueError("management_mode must be `managed` or `disabled`")
    runtime = store.load_service_runtime()
    runtime["management_mode"] = management_mode
    store.save_service_runtime(runtime)
    return _service_policy_payload(store, runtime)


def worker_command(store: MemoryStore, *, interval_seconds: float) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "opendream.cli",
        "dream",
        "daemon",
        "--workspace",
        str(store.workspace),
        "--interval-seconds",
        _format_interval(interval_seconds),
        "--max-polls",
        "0",
        "--mode",
        "auto",
        "--memory-dir",
        store.memory_dir_name,
    ]
    if store.compat_mode != "canonical":
        command.extend(["--compat-mode", store.compat_mode])
    return command


def render_manifest(
    supervisor_kind: str,
    service_mode: str,
    *,
    label: str,
    command: list[str],
    working_directory: Path,
    log_path: Path,
) -> str:
    template_name = f"{supervisor_kind}.{service_mode}.{'plist' if supervisor_kind == 'launchd' else 'service'}.tmpl"
    template = Template((TEMPLATE_ROOT / template_name).read_text(encoding="utf-8"))
    payload = {
        "label": label,
        "working_directory": str(working_directory),
        "log_path": str(log_path),
        "program_arguments": _launchd_arguments(command),
        "exec_start": shlex.join(command),
    }
    return template.substitute(payload).strip() + "\n"


def install_service(
    store: MemoryStore,
    *,
    interval_seconds: float,
    backend_mode: str,
    service_mode: str,
    install_root: Path | None,
    start: bool,
) -> dict[str, Any]:
    store.ensure_layout()
    _validate_service_paths(store)
    supervisor_kind = detect_supervisor()
    label = service_label(store)
    install_base = (
        install_root.expanduser()
        if install_root
        else (
            _managed_install_root(store)
            if backend_mode == "managed"
            else default_install_root(supervisor_kind, service_mode)
        )
    )
    command = worker_command(store, interval_seconds=interval_seconds)
    log_path = store.audit_service_dir / f"{label}.log"
    rendered_dir = store.state_dir / "service"
    rendered_dir.mkdir(parents=True, exist_ok=True)
    rendered_path = rendered_dir / service_filename(supervisor_kind, label)
    install_path = install_base / rendered_path.name
    rendered = render_manifest(
        supervisor_kind,
        service_mode,
        label=label,
        command=command,
        working_directory=store.workspace,
        log_path=log_path,
    )
    previous_manifest = store.load_service_manifest()
    previous_install_path = str(previous_manifest.get("install_path", ""))
    previous_checksum = previous_manifest.get("manifest_sha256")

    atomic_write_text(rendered_path, rendered)
    install_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(install_path, rendered)

    manifest = {
        "version": 1,
        "service_name": label,
        "supervisor_kind": supervisor_kind,
        "service_mode": service_mode,
        "backend_mode": backend_mode,
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "rendered_path": str(rendered_path),
        "install_path": str(install_path),
        "command": command,
        "interval_seconds": interval_seconds,
        "log_path": str(log_path),
        "enabled": True,
        "installed_at": to_iso(utc_now()),
        "template_name": rendered_path.name,
        "manifest_sha256": sha256_path(rendered_path),
    }
    validate_document("supervisor-manifest.schema.json", manifest)
    store.save_service_manifest(manifest)

    runtime = store.load_service_runtime()
    runtime.setdefault("start_count", 0)
    runtime.setdefault("restart_count", 0)
    runtime.setdefault("management_mode", _default_management_mode(store))
    runtime["service_name"] = label
    runtime["backend_mode"] = backend_mode
    runtime["enabled"] = True
    runtime["install_path"] = str(install_path)
    store.save_service_runtime(runtime)

    warnings: list[str] = []
    native_action = None
    if backend_mode == "native":
        native_action = _native_install(supervisor_kind, service_mode, install_path, label)
        warnings.extend(native_action["warnings"])

    start_result: dict[str, Any] | None = None
    if start:
        start_result = start_service(store)
        warnings.extend(start_result.get("warnings", []))

    changed = previous_install_path != str(install_path) or previous_checksum != manifest["manifest_sha256"]
    report = {
        "report_id": stable_id("service-install", label, manifest["installed_at"], "install"),
        "action": "install",
        "generated_at": manifest["installed_at"],
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "service_name": label,
        "supervisor_kind": supervisor_kind,
        "service_mode": service_mode,
        "backend_mode": backend_mode,
        "rendered_path": str(rendered_path),
        "install_path": str(install_path),
        "installed": True,
        "enabled": True,
        "started": bool(start_result and start_result.get("running")),
        "changed": changed,
        "warnings": warnings,
    }
    validate_document("service-install-report.schema.json", report)
    report_path = store.write_service_report(report)
    return {
        "status": "installed",
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "manifest": manifest,
        "report_path": str(report_path),
        "native_action": native_action,
        "start_result": start_result,
        "warnings": warnings,
    }


def update_service(
    store: MemoryStore,
    *,
    interval_seconds: float,
    backend_mode: str | None,
    service_mode: str | None,
    install_root: Path | None,
    restart: bool,
) -> dict[str, Any]:
    existing = store.load_service_manifest()
    if not existing:
        raise ValueError("service is not installed; run `opendream install-service` first")
    previous_checksum = str(existing.get("manifest_sha256", ""))
    result = install_service(
        store,
        interval_seconds=interval_seconds,
        backend_mode=backend_mode or str(existing.get("backend_mode", "managed")),
        service_mode=service_mode or str(existing.get("service_mode", "user")),
        install_root=install_root,
        start=False,
    )
    manifest = result["manifest"]
    changed = previous_checksum != manifest["manifest_sha256"]
    restart_result: dict[str, Any] | None = None
    warnings = list(result.get("warnings", []))
    if restart:
        restart_result = restart_service(store)
        warnings.extend(restart_result.get("warnings", []))
    report = {
        "report_id": stable_id("service-install", manifest["service_name"], to_iso(utc_now()), "update"),
        "action": "update",
        "generated_at": to_iso(utc_now()),
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "service_name": manifest["service_name"],
        "supervisor_kind": manifest["supervisor_kind"],
        "service_mode": manifest["service_mode"],
        "backend_mode": manifest["backend_mode"],
        "rendered_path": manifest["rendered_path"],
        "install_path": manifest["install_path"],
        "installed": True,
        "enabled": True,
        "started": bool(restart_result and restart_result.get("running")),
        "changed": changed,
        "warnings": warnings,
    }
    validate_document("service-install-report.schema.json", report)
    report_path = store.write_service_report(report)
    result.update(
        {
            "status": "updated",
            "changed": changed,
            "restart_result": restart_result,
            "report_path": str(report_path),
            "warnings": warnings,
        }
    )
    return result


def uninstall_service(store: MemoryStore, *, purge: bool) -> dict[str, Any]:
    manifest = store.load_service_manifest()
    runtime = store.load_service_runtime()
    management_mode = str(runtime.get("management_mode") or _default_management_mode(store))
    warnings: list[str] = []
    stop_result: dict[str, Any] | None = None
    if runtime.get("pid") or runtime.get("running"):
        stop_result = stop_service(store)
        warnings.extend(stop_result.get("warnings", []))

    removed_paths: list[str] = []
    if manifest:
        install_path = Path(str(manifest.get("install_path", ""))).expanduser()
        if install_path.exists():
            install_path.unlink()
            removed_paths.append(str(install_path))
        rendered_path = Path(str(manifest.get("rendered_path", ""))).expanduser()
        if rendered_path.exists():
            rendered_path.unlink()
            removed_paths.append(str(rendered_path))
        if manifest.get("backend_mode") == "native":
            warnings.extend(
                _native_uninstall(
                    str(manifest.get("supervisor_kind")),
                    str(manifest.get("service_mode")),
                    install_path,
                )
            )

    if purge:
        for path in [store.service_manifest_path, store.service_runtime_path, store.worker_health_path]:
            if path.exists():
                path.unlink()
                removed_paths.append(str(path))
    else:
        store.save_service_manifest({})
        store.save_service_runtime({"enabled": False, "management_mode": management_mode})

    report = {
        "report_id": stable_id("service-install", service_label(store), to_iso(utc_now()), "uninstall"),
        "action": "uninstall",
        "generated_at": to_iso(utc_now()),
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "service_name": str(manifest.get("service_name", service_label(store))),
        "supervisor_kind": str(manifest.get("supervisor_kind", detect_supervisor())),
        "service_mode": str(manifest.get("service_mode", "user")),
        "backend_mode": str(manifest.get("backend_mode", "managed")),
        "rendered_path": str(manifest.get("rendered_path", "")),
        "install_path": str(manifest.get("install_path", "")),
        "installed": False,
        "enabled": False,
        "started": False,
        "changed": bool(removed_paths),
        "warnings": warnings,
    }
    validate_document("service-install-report.schema.json", report)
    report_path = store.write_service_report(report)
    return {
        "status": "uninstalled",
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "removed_paths": removed_paths,
        "report_path": str(report_path),
        "stop_result": stop_result,
        "warnings": warnings,
    }


def start_service(store: MemoryStore) -> dict[str, Any]:
    manifest = store.load_service_manifest()
    if not manifest:
        raise ValueError("service is not installed; run `opendream install-service` first")
    if str(manifest.get("backend_mode", "managed")) == "native":
        native = _native_start(manifest)
        runtime = store.load_service_runtime()
        runtime.setdefault("management_mode", _default_management_mode(store))
        runtime["enabled"] = True
        runtime["running"] = bool(native.get("ok"))
        runtime["last_start_at"] = to_iso(utc_now())
        runtime["last_error"] = None if native.get("ok") else "native-start-failed"
        store.save_service_runtime(runtime)
        return {
            "status": "started" if native.get("ok") else "failed",
            "running": bool(native.get("ok")),
            "warnings": native["warnings"],
        }

    runtime = store.load_service_runtime()
    runtime.setdefault("management_mode", _default_management_mode(store))
    current_pid = _coerce_pid(runtime.get("pid"))
    if current_pid and _pid_running(current_pid):
        return {"status": "already-running", "running": True, "pid": current_pid, "warnings": []}

    command = [str(item) for item in manifest["command"]]
    log_path = Path(str(manifest["log_path"]))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as handle:
        process = subprocess.Popen(
            command,
            cwd=str(store.workspace),
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    _MANAGED_PROCESS_HANDLES[str(store.workspace.resolve())] = process
    runtime["pid"] = process.pid
    runtime["running"] = True
    runtime["enabled"] = True
    runtime["last_start_at"] = to_iso(utc_now())
    runtime["start_count"] = int(runtime.get("start_count", 0)) + 1
    runtime["backend_mode"] = "managed"
    runtime["service_name"] = manifest["service_name"]
    store.save_service_runtime(runtime)
    return {"status": "started", "running": True, "pid": process.pid, "warnings": []}


def stop_service(store: MemoryStore, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    manifest = store.load_service_manifest()
    runtime = store.load_service_runtime()
    handle = _MANAGED_PROCESS_HANDLES.get(str(store.workspace.resolve()))
    runtime.setdefault("management_mode", _default_management_mode(store))
    warnings: list[str] = []
    if manifest and str(manifest.get("backend_mode", "managed")) == "native":
        native = _native_stop(manifest)
        runtime["running"] = False
        runtime["pid"] = None
        runtime["last_stop_at"] = to_iso(utc_now())
        runtime["last_error"] = None if native.get("ok") else "native-stop-failed"
        store.save_service_runtime(runtime)
        _mark_worker_stopped(store)
        return {"status": "stopped" if native.get("ok") else "failed", "running": False, "warnings": native["warnings"]}

    pid = _coerce_pid(runtime.get("pid"))
    if not pid or not _pid_running(pid):
        runtime["running"] = False
        runtime["pid"] = None
        runtime["last_stop_at"] = to_iso(utc_now())
        store.save_service_runtime(runtime)
        _mark_worker_stopped(store)
        if handle is not None:
            with suppress(Exception):
                handle.wait(timeout=0.1)
            _MANAGED_PROCESS_HANDLES.pop(str(store.workspace.resolve()), None)
        return {"status": "already-stopped", "running": False, "warnings": []}

    _terminate_pid(pid, timeout_seconds=timeout_seconds)
    runtime["running"] = False
    runtime["pid"] = None
    runtime["last_stop_at"] = to_iso(utc_now())
    runtime["last_error"] = None
    store.save_service_runtime(runtime)
    _mark_worker_stopped(store)
    if handle is not None:
        with suppress(Exception):
            handle.wait(timeout=0.2)
        _MANAGED_PROCESS_HANDLES.pop(str(store.workspace.resolve()), None)
    return {"status": "stopped", "running": False, "warnings": warnings}


def restart_service(store: MemoryStore) -> dict[str, Any]:
    runtime = store.load_service_runtime()
    runtime.setdefault("management_mode", _default_management_mode(store))
    runtime["restart_count"] = int(runtime.get("restart_count", 0)) + 1
    store.save_service_runtime(runtime)
    stop_result = stop_service(store)
    start_result = start_service(store)
    warnings = [*stop_result.get("warnings", []), *start_result.get("warnings", [])]
    return {
        "status": "restarted" if start_result.get("running") else "failed",
        "running": bool(start_result.get("running")),
        "stop_result": stop_result,
        "start_result": start_result,
        "warnings": warnings,
    }


def service_status(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    from .semantic_dreamer import semantic_runtime_diagnosis

    timestamp = now or to_iso(utc_now())
    manifest = store.load_service_manifest()
    runtime = store.load_service_runtime()
    runtime.setdefault("management_mode", _default_management_mode(store))
    worker_health = store.load_worker_health()
    recent_failures = prune_recent_failures(
        worker_health.get("recent_failures", []),
        now=timestamp,
        last_success_at=worker_health.get("last_success_at"),
        recent_limit=RECENT_FAILURE_LIMIT,
    )
    worker_health = {**worker_health, "recent_failures": recent_failures}
    queue = store.load_dream_queue()
    queue_backlog = len([job for job in queue if job.get("status") == "queued"])
    install_path = Path(str(manifest.get("install_path", ""))).expanduser() if manifest else None
    installed = bool(manifest) and bool(install_path and install_path.exists())
    enabled = installed and bool(manifest.get("enabled", True))
    pid = _coerce_pid(runtime.get("pid"))
    running = bool(pid and _pid_running(pid))
    runtime_changed = runtime.get("running") != running or runtime.get("pid") != pid
    runtime["running"] = running
    runtime["pid"] = pid
    if runtime_changed:
        store.save_service_runtime(runtime)
    if not running:
        _MANAGED_PROCESS_HANDLES.pop(str(store.workspace.resolve()), None)
    policy = _service_policy_payload(store, runtime)

    heartbeat_age = _heartbeat_age_seconds(worker_health, timestamp)
    health = _health_state(
        installed=installed,
        enabled=enabled,
        running=running,
        worker_health=worker_health,
        queue_backlog=queue_backlog,
        heartbeat_age_seconds=heartbeat_age,
        restart_count=int(runtime.get("restart_count", 0)),
    )
    semantic_runtime = semantic_runtime_diagnosis(store, now=timestamp, requested_mode="auto")
    return {
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "service_name": manifest.get("service_name"),
        "supervisor_kind": manifest.get("supervisor_kind"),
        "service_mode": manifest.get("service_mode"),
        "backend_mode": manifest.get("backend_mode"),
        "installed": installed,
        "enabled": enabled,
        "running": running,
        "install_path": str(install_path) if install_path else None,
        "rendered_path": manifest.get("rendered_path"),
        "health": health,
        "heartbeat_age_seconds": heartbeat_age,
        "backlog": queue_backlog,
        "last_success_at": worker_health.get("last_success_at"),
        "last_loop_at": worker_health.get("last_loop_at"),
        "active_job_id": worker_health.get("active_job_id"),
        "active_phase": worker_health.get("active_phase"),
        "pid": pid,
        "restart_count": int(runtime.get("restart_count", 0)),
        "start_count": int(runtime.get("start_count", 0)),
        "recent_failures": recent_failures,
        "policy": policy,
        "semantic_runtime": semantic_runtime,
        "runtime": runtime,
        "worker_health": worker_health,
    }


def service_doctor(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    status = service_status(store, now=now)
    issues: list[str] = []
    remediation: list[str] = []

    if not status["installed"]:
        issues.append("service is not installed")
        remediation.append("run `opendream install-service --workspace <path>`")
    if status["installed"] and not status["enabled"]:
        issues.append("service manifest exists but is disabled")
        remediation.append("run `opendream update-service --workspace <path>` to re-enable the manifest")
    if status["installed"] and not status["running"]:
        issues.append("service is installed but not running")
        remediation.append("run `opendream service start --workspace <path>` and re-check status")
    if status["heartbeat_age_seconds"] is not None and status["heartbeat_age_seconds"] > DEFAULT_STUCK_SECONDS:
        issues.append("worker heartbeat is stale")
        remediation.append("restart the service and inspect the service log for stuck dream runs")
    if status["health"] == "crash_loop":
        issues.append("worker appears to be crash-looping")
        remediation.append("inspect recent failures and reduce restart churn before re-enabling background work")
    if int(status["backlog"]) > 0 and not status["running"]:
        issues.append("queue backlog is present while the worker is stopped")
        remediation.append(
            "start the service or run `opendream dream worker --workspace <path> --once` to drain manually"
        )
    if not issues:
        remediation.append("no action required")

    return {
        **status,
        "issues": issues,
        "recommended_remediation": remediation,
    }


def format_service_status(payload: dict[str, Any]) -> str:
    semantic_runtime = payload.get("semantic_runtime") or {}
    parts = [
        f"service={payload.get('service_name') or 'unknown'}",
        f"policy={payload.get('policy', {}).get('management_mode', 'unknown')}",
        f"installed={payload['installed']}",
        f"enabled={payload['enabled']}",
        f"running={payload['running']}",
        f"health={payload['health']}",
        f"backlog={payload['backlog']}",
    ]
    if semantic_runtime:
        parts.append(f"semantic_state={semantic_runtime.get('state', 'unknown')}")
        parts.append(f"semantic_mode={semantic_runtime.get('work_mode', 'unknown')}")
    if payload.get("heartbeat_age_seconds") is not None:
        parts.append(f"heartbeat_age_seconds={payload['heartbeat_age_seconds']}")
    if payload.get("last_success_at"):
        parts.append(f"last_success_at={payload['last_success_at']}")
    return " ".join(parts)


def format_service_doctor(payload: dict[str, Any]) -> str:
    lines = [format_service_status(payload)]
    issues = payload.get("issues", [])
    remediation = payload.get("recommended_remediation", [])
    lines.append("issues: " + (", ".join(issues) if issues else "none"))
    lines.append("remediation: " + (", ".join(remediation) if remediation else "none"))
    return "\n".join(lines)


def autowire_adapters(
    store: MemoryStore,
    *,
    target: str,
    force: bool,
    uninstall: bool,
) -> dict[str, Any]:
    from .activation import autowire_adapters_compat

    return autowire_adapters_compat(store, target=target, force=force, uninstall=uninstall)


def ensure_background_runtime(
    store: MemoryStore,
    *,
    interval_seconds: float = 30.0,
    backend_mode: str = "managed",
    service_mode: str = "user",
    install_root: Path | None = None,
) -> dict[str, Any]:
    policy = _service_policy_payload(store, store.load_service_runtime())
    if policy["management_mode"] == "disabled":
        return {
            "status": "disabled",
            "policy": policy,
            "service": service_status(store),
            "steps": [],
        }

    steps: list[str] = []
    install_result: dict[str, Any] | None = None
    start_result: dict[str, Any] | None = None
    status = service_status(store)

    if status["installed"] and _service_manifest_requires_refresh(
        store,
        interval_seconds=interval_seconds,
        backend_mode=backend_mode,
        service_mode=service_mode,
        install_root=install_root,
    ):
        update_result = update_service(
            store,
            interval_seconds=interval_seconds,
            backend_mode=backend_mode,
            service_mode=service_mode,
            install_root=install_root,
            restart=status["running"],
        )
        steps.append("updated")
        restart_result = update_result.get("restart_result")
        if isinstance(restart_result, dict) and restart_result.get("running"):
            steps.append("restarted")
        status = service_status(store)

    if not status["installed"]:
        install_result = install_service(
            store,
            interval_seconds=interval_seconds,
            backend_mode=backend_mode,
            service_mode=service_mode,
            install_root=install_root,
            start=False,
        )
        steps.append("installed")
        status = service_status(store)

    if not status["running"]:
        start_result = start_service(store)
        steps.append("started" if start_result.get("running") else "failed")

    final_status = service_status(store)
    if not steps and final_status["running"]:
        status_label = "already-running"
    elif "failed" in steps or not final_status["running"]:
        status_label = "failed"
    elif steps == ["started"]:
        status_label = "started"
    else:
        status_label = "ensured"

    return {
        "status": status_label,
        "policy": final_status["policy"],
        "service": final_status,
        "steps": steps,
        "install_result": install_result,
        "start_result": start_result,
    }


def enable_background_runtime(
    store: MemoryStore,
    *,
    interval_seconds: float = 30.0,
    backend_mode: str = "managed",
    service_mode: str = "user",
    install_root: Path | None = None,
) -> dict[str, Any]:
    policy = set_service_management_mode(store, "managed")
    ensured = ensure_background_runtime(
        store,
        interval_seconds=interval_seconds,
        backend_mode=backend_mode,
        service_mode=service_mode,
        install_root=install_root,
    )
    return {
        "status": "enabled",
        "policy": policy,
        "ensure_status": ensured["status"],
        "service": ensured["service"],
        "steps": ensured.get("steps", []),
        "install_result": ensured.get("install_result"),
        "start_result": ensured.get("start_result"),
    }


def disable_background_runtime(store: MemoryStore) -> dict[str, Any]:
    policy = set_service_management_mode(store, "disabled")
    stop_result: dict[str, Any] | None = None
    status = service_status(store)
    if status["running"]:
        stop_result = stop_service(store)
        status = service_status(store)
    return {
        "status": "disabled",
        "policy": policy,
        "service": status,
        "stop_result": stop_result,
    }


def _service_manifest_requires_refresh(
    store: MemoryStore,
    *,
    interval_seconds: float,
    backend_mode: str,
    service_mode: str,
    install_root: Path | None,
) -> bool:
    manifest = store.load_service_manifest()
    if not manifest:
        return False
    desired_backend = backend_mode or str(manifest.get("backend_mode", "managed"))
    desired_service_mode = service_mode or str(manifest.get("service_mode", "user"))
    desired_root = (
        install_root.expanduser()
        if install_root
        else (
            _managed_install_root(store)
            if desired_backend == "managed"
            else default_install_root(detect_supervisor(), desired_service_mode)
        )
    )
    desired_install_path = desired_root / service_filename(detect_supervisor(), service_label(store))
    desired_command = worker_command(store, interval_seconds=interval_seconds)
    current_command = [str(item) for item in manifest.get("command", [])]
    current_interval = float(manifest.get("interval_seconds", interval_seconds) or interval_seconds)
    return (
        current_command != desired_command
        or current_interval != float(interval_seconds)
        or str(manifest.get("backend_mode", "managed")) != desired_backend
        or str(manifest.get("service_mode", "user")) != desired_service_mode
        or str(manifest.get("install_path", "")) != str(desired_install_path)
    )


def _autowire_claude(workspace: Path, *, force: bool, uninstall: bool) -> dict[str, Any]:
    hooks_root = workspace / AUTOWIRE_ROOT
    pre_path = hooks_root / "claude-pre-task.sh"
    post_path = hooks_root / "claude-post-task.sh"
    settings_path = workspace / CLAUDE_SETTINGS_PATH
    changed_files: list[str] = []
    warnings: list[str] = []
    payload = _load_json_file(settings_path)
    hooks = payload.setdefault("hooks", {})

    pre_command = CLAUDE_PRE_TASK_COMMAND
    post_command = CLAUDE_POST_TASK_COMMAND

    if uninstall:
        # Remove from UserPromptSubmit event
        if "UserPromptSubmit" in hooks:
            user_prompt_submit = hooks["UserPromptSubmit"]
            for matcher in user_prompt_submit:
                if isinstance(matcher, dict) and "hooks" in matcher:
                    matcher["hooks"] = [
                        h for h in matcher["hooks"]
                        if not (isinstance(h, dict) and h.get("command") == pre_command)
                    ]
        # Remove from Stop event
        if "Stop" in hooks:
            stop = hooks["Stop"]
            for matcher in stop:
                if isinstance(matcher, dict) and "hooks" in matcher:
                    matcher["hooks"] = [
                        h for h in matcher["hooks"]
                        if not (isinstance(h, dict) and h.get("command") == post_command)
                    ]
        if settings_path.exists():
            atomic_write_text(settings_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
            changed_files.append(str(settings_path))
        for path in [pre_path, post_path]:
            if path.exists():
                path.unlink()
                changed_files.append(str(path))
        return {"target": "claude-code", "changed_files": changed_files, "warnings": warnings}

    _ensure_script(pre_path, _hook_script("claude", "pre"))
    _ensure_script(post_path, _hook_script("claude", "post"))
    changed_files.extend([str(pre_path), str(post_path)])

    # Clean up old deprecated keys
    hooks.pop("preTask", None)
    hooks.pop("postTask", None)

    # Add to UserPromptSubmit event
    user_prompt_submit = hooks.setdefault("UserPromptSubmit", [])
    if not user_prompt_submit:
        user_prompt_submit.append({
            "hooks": [
                {"type": "command", "command": pre_command}
            ]
        })
    else:
        found = False
        for matcher in user_prompt_submit:
            if isinstance(matcher, dict) and "hooks" in matcher:
                hooks_list = matcher["hooks"]
                if not any(h.get("command") == pre_command for h in hooks_list if isinstance(h, dict)):
                    hooks_list.append({"type": "command", "command": pre_command})
                found = True
                break
        if not found:
            user_prompt_submit.append({
                "hooks": [
                    {"type": "command", "command": pre_command}
                ]
            })

    # Add to Stop event
    stop = hooks.setdefault("Stop", [])
    if not stop:
        stop.append({
            "hooks": [
                {"type": "command", "command": post_command}
            ]
        })
    else:
        found = False
        for matcher in stop:
            if isinstance(matcher, dict) and "hooks" in matcher:
                hooks_list = matcher["hooks"]
                if not any(h.get("command") == post_command for h in hooks_list if isinstance(h, dict)):
                    hooks_list.append({"type": "command", "command": post_command})
                found = True
                break
        if not found:
            stop.append({
                "hooks": [
                    {"type": "command", "command": post_command}
                ]
            })

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(settings_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    changed_files.append(str(settings_path))
    if not force:
        # Check for other hooks we might be preserving
        has_other_pre = False
        has_other_post = False
        for event in hooks:
            if event == "UserPromptSubmit":
                for matcher in hooks.get("UserPromptSubmit", []):
                    if isinstance(matcher, dict) and "hooks" in matcher:
                        for h in matcher["hooks"]:
                            if isinstance(h, dict) and h.get("command") != pre_command:
                                has_other_pre = True
            if event == "Stop":
                for matcher in hooks.get("Stop", []):
                    if isinstance(matcher, dict) and "hooks" in matcher:
                        for h in matcher["hooks"]:
                            if isinstance(h, dict) and h.get("command") != post_command:
                                has_other_post = True
        if has_other_pre:
            warnings.append("preserved existing Claude hooks in UserPromptSubmit")
        if has_other_post:
            warnings.append("preserved existing Claude hooks in Stop")
    return {"target": "claude-code", "changed_files": changed_files, "warnings": warnings}


def _autowire_codex(workspace: Path, *, force: bool, uninstall: bool) -> dict[str, Any]:
    hooks_root = workspace / AUTOWIRE_ROOT
    pre_path = hooks_root / "codex-pre-task.sh"
    post_path = hooks_root / "codex-post-task.sh"
    agents_path = workspace / CODEX_AGENTS_PATH
    changed_files: list[str] = []
    warnings: list[str] = []
    if uninstall:
        if agents_path.exists():
            text = agents_path.read_text(encoding="utf-8")
            updated = _remove_block(text, CODEX_BLOCK_START, CODEX_BLOCK_END)
            atomic_write_text(agents_path, updated)
            changed_files.append(str(agents_path))
        for path in [pre_path, post_path]:
            if path.exists():
                path.unlink()
                changed_files.append(str(path))
        return {"target": "codex", "changed_files": changed_files, "warnings": warnings}

    _ensure_script(pre_path, _hook_script("codex", "pre"))
    _ensure_script(post_path, _hook_script("codex", "post"))
    changed_files.extend([str(pre_path), str(post_path)])
    block = "\n".join(
        [
            CODEX_BLOCK_START,
            "",
            "## OpenDream hooks",
            "",
            "Before planning:",
            '`sh .opendream/hooks/codex-pre-task.sh "$CODEX_TASK"`',
            "",
            "After task completion:",
            '`sh .opendream/hooks/codex-post-task.sh "$CODEX_SUMMARY"`',
            "",
            CODEX_BLOCK_END,
            "",
        ]
    )
    existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else "# AGENTS.md\n\n"
    if CODEX_BLOCK_START in existing and CODEX_BLOCK_END in existing:
        updated = _replace_block(existing, CODEX_BLOCK_START, CODEX_BLOCK_END, block)
    else:
        updated = existing.rstrip() + "\n\n" + block
    if not force and agents_path.exists() and CODEX_BLOCK_START not in existing:
        warnings.append("appended a managed OpenDream block to the existing AGENTS.md")
    atomic_write_text(agents_path, updated)
    changed_files.append(str(agents_path))
    return {"target": "codex", "changed_files": changed_files, "warnings": warnings}


def _autowire_openclaw(workspace: Path, *, force: bool, uninstall: bool) -> dict[str, Any]:
    hooks_root = workspace / AUTOWIRE_ROOT
    hook_path = hooks_root / "openclaw-hooks.sh"
    map_path = workspace / ".openclaw" / "opendream-event-map.md"
    config_path = workspace / OPENCLAW_CONFIG_PATH
    changed_files: list[str] = []
    warnings: list[str] = []
    config = _load_json_file(config_path)
    hooks = config.setdefault("hooks", {})
    pre_task = hooks.setdefault("prePlan", [])
    post_task = hooks.setdefault("postTask", [])
    pre_cmd = 'sh .opendream/hooks/openclaw-hooks.sh pre-plan "$OPENCLAW_TASK"'
    post_cmd = 'sh .opendream/hooks/openclaw-hooks.sh post-task "$OPENCLAW_SUMMARY"'

    if uninstall:
        pre_task[:] = [item for item in pre_task if item != pre_cmd]
        post_task[:] = [item for item in post_task if item != post_cmd]
        if config_path.exists():
            atomic_write_text(config_path, json.dumps(config, indent=2, sort_keys=True) + "\n")
            changed_files.append(str(config_path))
        for path in [hook_path, map_path]:
            if path.exists():
                path.unlink()
                changed_files.append(str(path))
        return {"target": "openclaw", "changed_files": changed_files, "warnings": warnings}

    _ensure_script(hook_path, _openclaw_hook_script())
    changed_files.append(str(hook_path))
    map_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        map_path,
        "\n".join(
            [
                "# OpenDream OpenClaw event map",
                "",
                '- `planner.pre_plan` -> `sh .opendream/hooks/openclaw-hooks.sh pre-plan "$OPENCLAW_TASK"`',
                '- `worker.post_task` -> `sh .opendream/hooks/openclaw-hooks.sh post-task "$OPENCLAW_SUMMARY"`',
                "",
            ]
        )
        + "\n",
    )
    changed_files.append(str(map_path))
    if config_path.exists() or force:
        if pre_cmd not in pre_task:
            pre_task.append(pre_cmd)
        if post_cmd not in post_task:
            post_task.append(post_cmd)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(config_path, json.dumps(config, indent=2, sort_keys=True) + "\n")
        changed_files.append(str(config_path))
    else:
        warnings.append("created OpenClaw hook artifacts but did not create a config file without --force")
    return {"target": "openclaw", "changed_files": changed_files, "warnings": warnings}


def _resolve_autowire_targets(workspace: Path, target: str) -> list[str]:
    if target == "all":
        return list(SUPPORTED_TARGETS)
    if target != "auto":
        return [target]
    targets: list[str] = []
    if (workspace / ".claude").exists():
        targets.append("claude-code")
    if (workspace / "AGENTS.md").exists():
        targets.append("codex")
    if (workspace / ".openclaw").exists():
        targets.append("openclaw")
    return targets or ["codex"]


def _hook_script(adapter: str, phase: str) -> str:
    if adapter == "codex":
        agent_lines = [
            'AGENT_LABEL="${OPENDREAM_AGENT_LABEL:-${CODEX_INTERNAL_ORIGINATOR_OVERRIDE:-Codex}}"',
            'AGENT_MODEL_ID="${OPENDREAM_AGENT_MODEL_ID:-${OPENAI_MODEL:-${MODEL:-unknown}}}"',
            'AGENT_MODEL_VERSION="${OPENDREAM_AGENT_MODEL_VERSION:-${OPENAI_MODEL_VERSION:-${MODEL_VERSION:-unknown}}}"',
        ]
        agent_args = " ".join(
            [
                '--agent-id "${OPENDREAM_AGENT_ID:-codex}"',
                '--agent-label "$AGENT_LABEL"',
                '--agent-runtime "${OPENDREAM_AGENT_RUNTIME:-codex-cli}"',
                '--agent-adapter-id "${OPENDREAM_AGENT_ADAPTER_ID:-codex-account}"',
                '--agent-model-id "$AGENT_MODEL_ID"',
                '--agent-model-version "$AGENT_MODEL_VERSION"',
            ]
        )
    else:
        agent_lines = []
        agent_args = ""
    if phase == "pre":
        task_var = "current task"
        return "\n".join(
            [
                "#!/bin/sh",
                "set -eu",
                "",
                'WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"',
                f'QUERY="${{1:-${{OPENDREAM_QUERY:-{task_var}}}}}"',
                'GLOBAL="${OPENDREAM_GLOBAL_WORKSPACE:-}"',
                "",
                *agent_lines,
                "",
                'if [ -n "$GLOBAL" ]; then',
                "  opendream prepare-context --workspace "
                f'"$WORKSPACE" --query "$QUERY" --include-global --global-workspace "$GLOBAL" {agent_args}'.rstrip(),
                "else",
                f'  opendream prepare-context --workspace "$WORKSPACE" --query "$QUERY" {agent_args}'.rstrip(),
                "fi",
                "",
            ]
        )
    ref = "claude-post-task" if adapter == "claude" else "codex-post-task"
    return "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            "",
            'WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"',
            'SUMMARY="${1:-${OPENDREAM_SUMMARY:-Task completed.}}"',
            f'MESSAGE_REF="${{OPENDREAM_REF:-{ref}}}"',
            "",
            *agent_lines,
            "",
            "opendream emit-event --workspace "
            f'"$WORKSPACE" --kind task_outcome --content "$SUMMARY" --message-ref "$MESSAGE_REF" {agent_args}'.rstrip(),
            'opendream maintain --workspace "$WORKSPACE"',
            'opendream dream worker --workspace "$WORKSPACE" --once',
            "",
        ]
    )


def _openclaw_hook_script() -> str:
    return "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            "",
            'MODE="${1:-pre-plan}"',
            'PAYLOAD="${2:-current task}"',
            'WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"',
            'GLOBAL="${OPENDREAM_GLOBAL_WORKSPACE:-}"',
            "",
            'if [ "$MODE" = "pre-plan" ]; then',
            '  if [ -n "$GLOBAL" ]; then',
            "    opendream prepare-context --workspace "
            '"$WORKSPACE" --query "$PAYLOAD" --include-global --global-workspace "$GLOBAL"',
            "  else",
            '    opendream prepare-context --workspace "$WORKSPACE" --query "$PAYLOAD"',
            "  fi",
            "  exit 0",
            "fi",
            "",
            "opendream emit-event --workspace "
            '"$WORKSPACE" --kind task_outcome --content "$PAYLOAD" '
            '--message-ref "${OPENCLAW_REF:-openclaw-post-task}"',
            'opendream maintain --workspace "$WORKSPACE"',
            'opendream dream worker --workspace "$WORKSPACE" --once',
            "",
        ]
    )


def _ensure_script(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _replace_block(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    return text[:start] + replacement + text[end:]


def _remove_block(text: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in text or end_marker not in text:
        return text
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    trimmed = (text[:start] + text[end:]).replace("\n\n\n", "\n\n")
    return trimmed.lstrip("\n")


def _validate_service_paths(store: MemoryStore) -> None:
    ensure_relative_to(store.memory_root, store.workspace)
    if not store.workspace.exists():
        store.workspace.mkdir(parents=True, exist_ok=True)
    if not Path(sys.executable).exists():
        raise ValueError(f"python executable does not exist: {sys.executable}")


def _launchd_arguments(command: list[str]) -> str:
    return "\n".join(f"    <string>{escape(item)}</string>" for item in command)


def _format_interval(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _heartbeat_age_seconds(worker_health: dict[str, Any], now: str) -> int | None:
    last_loop_at = worker_health.get("last_loop_at")
    if not last_loop_at:
        return None
    return max(0, round((parse_timestamp(now) - parse_timestamp(str(last_loop_at))).total_seconds()))


def _health_state(
    *,
    installed: bool,
    enabled: bool,
    running: bool,
    worker_health: dict[str, Any],
    queue_backlog: int,
    heartbeat_age_seconds: int | None,
    restart_count: int,
) -> str:
    if not installed:
        return "unknown"
    if not enabled:
        return "stopped"
    if restart_count >= CRASH_LOOP_THRESHOLD and not running:
        return "crash_loop"
    if not running:
        return "stopped"
    if heartbeat_age_seconds is not None and heartbeat_age_seconds > DEFAULT_STUCK_SECONDS:
        if worker_health.get("active_job_id"):
            return "stuck"
        return "degraded"
    if queue_backlog > 0:
        return "draining"
    if worker_health.get("state") == "idle":
        return "idle"
    return "healthy"


def _coerce_pid(value: Any) -> int | None:
    if value in (None, "", 0):
        return None
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal_process_tree(pid: int, sig: int) -> None:
    """Signal a managed worker process; prefer the session group, fall back to single PID."""
    if os.name != "posix":
        with suppress(ProcessLookupError):
            os.kill(pid, sig)
        return
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        return
    except PermissionError:
        # macOS can raise EPERM for killpg even when kill(pid) works (pg/session edge cases).
        with suppress(ProcessLookupError):
            os.kill(pid, sig)


def _terminate_pid(pid: int, *, timeout_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    _signal_process_tree(pid, signal.SIGTERM)
    while time.time() < deadline:
        if not _pid_running(pid):
            return
        time.sleep(0.1)
    _signal_process_tree(pid, signal.SIGKILL)


def _mark_worker_stopped(store: MemoryStore) -> None:
    worker_health = store.load_worker_health()
    queue_backlog = len([job for job in store.load_dream_queue() if job.get("status") == "queued"])
    worker_health.update(
        {
            "state": "stopped",
            "active_job_id": None,
            "active_phase": None,
            "pid": None,
            "started_at": worker_health.get("started_at"),
            "last_loop_at": worker_health.get("last_loop_at") or to_iso(utc_now()),
            "last_success_at": worker_health.get("last_success_at"),
            "queue_backlog": max(0, int(worker_health.get("queue_backlog", queue_backlog))),
            "restart_count": int(worker_health.get("restart_count", 0)),
            "recent_failures": list(worker_health.get("recent_failures", [])),
        }
    )
    if worker_health:
        validate_document("worker-health.schema.json", worker_health)
        store.save_worker_health(worker_health)


def _native_install(supervisor_kind: str, service_mode: str, install_path: Path, label: str) -> dict[str, Any]:
    warnings: list[str] = []
    if supervisor_kind == "launchd":
        if service_mode == "system":
            warnings.append(
                "native launchd system services require elevated privileges and were not started automatically"
            )
            return {"ok": False, "warnings": warnings}
        _run_native(["launchctl", "bootout", f"gui/{os.getuid()}", str(install_path)], warnings)
        ok = _run_native(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(install_path)], warnings)
        if ok:
            _run_native(["launchctl", "enable", f"gui/{os.getuid()}/{label}"], warnings)
        return {"ok": ok, "warnings": warnings}
    if service_mode == "system":
        warnings.append("native system systemd services require elevated privileges and were not enabled automatically")
        return {"ok": False, "warnings": warnings}
    _run_native(["systemctl", "--user", "daemon-reload"], warnings)
    ok = _run_native(["systemctl", "--user", "enable", "--now", install_path.name], warnings)
    return {"ok": ok, "warnings": warnings}


def _native_uninstall(supervisor_kind: str, service_mode: str, install_path: Path) -> list[str]:
    warnings: list[str] = []
    if supervisor_kind == "launchd" and service_mode == "user":
        _run_native(["launchctl", "bootout", f"gui/{os.getuid()}", str(install_path)], warnings)
    if supervisor_kind == "systemd" and service_mode == "user":
        _run_native(["systemctl", "--user", "disable", "--now", install_path.name], warnings)
        _run_native(["systemctl", "--user", "daemon-reload"], warnings)
    return warnings


def _native_start(manifest: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    install_path = Path(str(manifest["install_path"]))
    label = str(manifest["service_name"])
    supervisor_kind = str(manifest["supervisor_kind"])
    service_mode = str(manifest["service_mode"])
    if supervisor_kind == "launchd":
        ok = _run_native(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"], warnings)
        return {"ok": ok, "warnings": warnings}
    ok = _run_native(["systemctl", "--user", "start", install_path.name], warnings)
    if service_mode == "system":
        warnings.append("system mode start is not supported without explicit elevated privileges")
    return {"ok": ok, "warnings": warnings}


def _native_stop(manifest: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    install_path = Path(str(manifest["install_path"]))
    label = str(manifest["service_name"])
    supervisor_kind = str(manifest["supervisor_kind"])
    if supervisor_kind == "launchd":
        ok = _run_native(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], warnings)
        return {"ok": ok, "warnings": warnings}
    ok = _run_native(["systemctl", "--user", "stop", install_path.name], warnings)
    return {"ok": ok, "warnings": warnings}


def _run_native(command: list[str], warnings: list[str]) -> bool:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode == 0:
        return True
    stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown native supervisor failure"
    warnings.append(f"{shlex.join(command)} failed: {stderr}")
    return False
