from __future__ import annotations

import hashlib
import json
import shlex
import stat
import subprocess
from pathlib import Path
from typing import Any, cast

from .storage import MemoryStore
from .util import atomic_write_text, read_json, stable_id, to_iso, utc_now, write_json
from .validation import validate_document

SUPPORTED_TARGETS = ("claude-code", "codex", "openclaw")
REGISTRY_PATH = Path(".opendream/agents.json")
TARGET_REGISTRY_PATH = Path(".opendream/targets.json")
ACTIVATION_STATE_PATH = Path(".opendream/activation-state.json")
REPORTS_DIR = Path(".opendream/reports")
HOOKS_DIR = Path(".opendream/hooks")
BIN_DIR = Path(".opendream/bin")
CONTEXT_DIR = Path(".opendream/context")

CLAUDE_SETTINGS_PATH = Path(".claude/settings.json")
OPENCLAW_CONFIG_PATH = Path(".openclaw/config.json")
OPENCLAW_EVENT_MAP_PATH = Path(".openclaw/opendream-event-map.md")
CODEX_AGENTS_PATH = Path("AGENTS.md")
CODEX_CONFIG_PATH = Path(".codex/config.toml")

LEGACY_CODEX_BLOCK_START = "<!-- OPENDREAM:CODEX START -->"
LEGACY_CODEX_BLOCK_END = "<!-- OPENDREAM:CODEX END -->"


def activate_agents(store: MemoryStore, *, targets: str, repair: bool = False) -> dict[str, Any]:
    store.ensure_layout()
    workspace = store.workspace
    registry_before = load_agent_registry(workspace)
    registry_before_map = _records_by_target(registry_before)
    detections = detect_agents(workspace)
    selected = _select_targets(detections, targets)
    warnings: list[str] = []
    changed_files: list[str] = []
    repairs: list[str] = []
    records: list[dict[str, Any]] = []
    generated_at = to_iso(utc_now())

    for target in selected:
        install_result = _install_target(store, target)
        verify_result = inspect_target(store, target)
        record = _build_agent_record(
            target,
            verify_result,
            activated_at=generated_at,
        )
        records.append(record)
        changed_files.extend(install_result["changed_files"])
        warnings.extend(install_result["warnings"])
        warnings.extend(verify_result["warnings"])
        if repair:
            repairs.extend(
                f"{target}: restored {Path(path).name}"
                for path in install_result["changed_files"]
                if install_result["changed_files"]
            )

    if not selected:
        warnings.append("no configured supported agent surfaces were detected")

    service_state = _service_requirement(store, records)
    if service_state["warnings"]:
        warnings.extend(service_state["warnings"])
    registry_records = _collect_registry_records(
        store,
        registry_before_map,
        activated_targets=set(selected),
        generated_at=generated_at,
    )
    registry = {
        "version": 2,
        "generated_at": generated_at,
        "workspace": str(workspace),
        "targets": registry_records,
        "service": service_state,
    }
    _write_registry(workspace, registry)
    activation_state = _activation_state_payload(workspace, generated_at, registry_records, service_state)
    _write_activation_state(workspace, activation_state)

    change_detected = bool(changed_files)
    report_status = "noop"
    if change_detected and registry_before.get("targets"):
        report_status = "updated"
    elif change_detected:
        report_status = "applied"

    activation_report = {
        "generated_at": generated_at,
        "workspace": str(workspace),
        "status": report_status,
        "targets": records,
        "warnings": sorted(dict.fromkeys(warnings)),
        "changed_files": sorted(dict.fromkeys(changed_files)),
        "service": service_state,
    }
    validate_document("activation-report.schema.json", activation_report)
    activation_report_path = _write_report(workspace, "activation", activation_report)
    activation_report["registry_path"] = str((workspace / TARGET_REGISTRY_PATH).relative_to(workspace))
    activation_report["legacy_registry_path"] = str((workspace / REGISTRY_PATH).relative_to(workspace))
    activation_report["activation_state_path"] = str((workspace / ACTIVATION_STATE_PATH).relative_to(workspace))
    activation_report["report_path"] = str(activation_report_path.relative_to(workspace))

    if not repair:
        return activation_report

    repair_status = "noop"
    if repairs:
        repair_status = "repaired"
    repair_report = {
        "generated_at": generated_at,
        "workspace": str(workspace),
        "status": repair_status,
        "repairs": repairs,
        "warnings": sorted(dict.fromkeys(warnings)),
        "activation_report_path": str(activation_report_path.relative_to(workspace)),
    }
    validate_document("repair-report.schema.json", repair_report)
    repair_report_path = _write_report(workspace, "repair", repair_report)
    repair_report["report_path"] = str(repair_report_path.relative_to(workspace))
    return repair_report


def deactivate_agents(store: MemoryStore, *, targets: str) -> dict[str, Any]:
    store.ensure_layout()
    workspace = store.workspace
    registry_before = load_agent_registry(workspace)
    registry_before_map = _records_by_target(registry_before)
    detections = detect_agents(workspace)
    selected = _select_targets_for_deactivation(detections, registry_before_map, targets)
    warnings: list[str] = []
    changed_files: list[str] = []
    results: list[dict[str, Any]] = []
    generated_at = to_iso(utc_now())

    for target in selected:
        removal = _remove_target(store, target)
        changed_files.extend(removal["changed_files"])
        warnings.extend(removal["warnings"])
        results.append(
            _build_agent_record(
                target,
                _normalize_registry_target(
                    target,
                    inspect_target(store, target),
                    registry_before_map.get(target, {}),
                    activated_targets=set(),
                    deactivated_targets=set(selected),
                ),
            )
        )

    registry_records = _collect_registry_records(
        store,
        registry_before_map,
        activated_targets=set(),
        deactivated_targets=set(selected),
        generated_at=generated_at,
    )
    service_state = _service_requirement(store, registry_records)
    registry = {
        "version": 2,
        "generated_at": generated_at,
        "workspace": str(workspace),
        "targets": registry_records,
        "service": service_state,
    }
    _write_registry(workspace, registry)
    activation_state = _activation_state_payload(workspace, generated_at, registry_records, service_state)
    _write_activation_state(workspace, activation_state)

    status = "noop"
    if changed_files:
        status = "deactivated"
    payload = {
        "generated_at": generated_at,
        "workspace": str(workspace),
        "status": status,
        "targets": results,
        "deactivated_targets": selected,
        "warnings": sorted(dict.fromkeys(warnings)),
        "changed_files": sorted(dict.fromkeys(changed_files)),
        "registry_path": str((workspace / TARGET_REGISTRY_PATH).relative_to(workspace)),
        "legacy_registry_path": str((workspace / REGISTRY_PATH).relative_to(workspace)),
        "activation_state_path": str((workspace / ACTIVATION_STATE_PATH).relative_to(workspace)),
    }
    payload["report_path"] = str(_write_report(workspace, "deactivate", payload).relative_to(workspace))
    return payload


def compressed_status(
    store: MemoryStore,
    *,
    now: str | None = None,
    min_new_events: int | None = None,
    min_interval_seconds: int | None = None,
) -> dict[str, Any]:
    from .service import service_status

    snapshot = store.status_snapshot(
        now=now,
        min_new_events=min_new_events,
        min_interval_seconds=min_interval_seconds,
    )
    generated_at = now or to_iso(utc_now())
    registry = load_agent_registry(store.workspace)
    registry_map = _records_by_target(registry)
    records = _collect_registry_records(store, registry_map, activated_targets=set(), generated_at=generated_at)
    service_state = _service_requirement(store, records)
    if store.is_initialized():
        service_runtime = service_status(store, now=generated_at)
    else:
        service_runtime = {
            "installed": False,
            "running": False,
            "health": "not-installed",
            "backlog": 0,
        }
    activation_state = _activation_state_payload(store.workspace, generated_at, records, service_state)
    overall_state = _compressed_overall_state(snapshot, activation_state, records, service_runtime)
    targets = [_compressed_target_record(record) for record in records]
    runtime = {
        "memory_state": snapshot["state"],
        "pending_events": snapshot["pending_events"],
        "pending_candidates": snapshot["pending_candidates"],
        "lock": snapshot["lock"],
        "dream": {
            "state": snapshot["dream"]["state"],
            "queue_depth": snapshot["dream"]["queue_depth"],
            "last_ran_at": snapshot["dream"]["last_ran_at"],
            "worker": snapshot["dream"]["worker"],
        },
        "service": {
            "installed": service_runtime["installed"],
            "running": service_runtime["running"],
            "health": service_runtime["health"],
            "backlog": service_runtime["backlog"],
        },
        "next_eligible_reason": snapshot["next_eligible_reason"],
        "next_eligible_at": snapshot["next_eligible_at"],
    }
    payload = {
        **snapshot,
        "workspace": str(store.workspace),
        "overall_state": overall_state,
        "targets": targets,
        "runtime": runtime,
        "next_action": _next_action(store.workspace, overall_state, targets, runtime),
        "activation_state": activation_state,
        "service": service_state,
    }
    validate_document("compressed-status.schema.json", payload)
    return payload


def format_compressed_status(payload: dict[str, Any]) -> str:
    lines = [
        f"workspace={payload['workspace']}",
        f"overall_state={payload['overall_state']}",
        f"next_action={payload['next_action']}",
    ]
    target_summary = payload.get("targets", [])
    if target_summary:
        lines.append(
            "targets="
            + ", ".join(
                f"{item['target_kind']}:{item['state']}"
                for item in target_summary
            )
        )
    runtime = payload.get("runtime", {})
    lines.append(
        "runtime="
        + ",".join(
            [
                f"memory={runtime.get('memory_state')}",
                f"pending_events={runtime.get('pending_events')}",
                f"pending_candidates={runtime.get('pending_candidates')}",
                f"dream={runtime.get('dream', {}).get('state')}",
                f"service={runtime.get('service', {}).get('health')}",
            ]
        )
    )
    return "\n".join(lines)


def doctor_agents(store: MemoryStore) -> dict[str, Any]:
    store.ensure_layout()
    workspace = store.workspace
    detections = detect_agents(workspace)
    configured_targets = [item["target_kind"] for item in detections if item["configured"]]
    detected_targets = [item["target_kind"] for item in detections if item["detected"]]
    registry = _records_by_target(load_agent_registry(workspace))
    records = _collect_registry_records(store, registry, activated_targets=set(), generated_at=to_iso(utc_now()))
    activated_targets = [record["target_kind"] for record in records if record["activated"]]
    drifted_targets = [
        record["target_kind"]
        for record in records
        if record["drift_state"] in {"drifted", "missing"}
    ]
    broken_targets = [record["target_kind"] for record in records if record["health_state"] == "broken"]
    service_state = _service_requirement(store, records)
    status = "healthy"
    if drifted_targets or service_state["status"] == "missing":
        status = "needs-repair"
    elif broken_targets:
        status = "broken"
    return {
        "generated_at": to_iso(utc_now()),
        "workspace": str(workspace),
        "surface": "agents",
        "status": status,
        "detected_targets": detected_targets,
        "configured_targets": configured_targets,
        "activated_targets": activated_targets,
        "drifted_targets": drifted_targets,
        "broken_targets": broken_targets,
        "missing_service_targets": service_state["missing_targets"],
        "results": [_build_agent_record(record["target_kind"], record) for record in records],
        "service": service_state,
    }


def autowire_adapters_compat(
    store: MemoryStore,
    *,
    target: str,
    force: bool,
    uninstall: bool,
) -> dict[str, Any]:
    del force
    if uninstall:
        targets = _select_targets_for_autowire(store.workspace, target)
        changed_files: list[str] = []
        warnings: list[str] = []
        results = []
        for item in targets:
            removal = _remove_target(store, item)
            changed_files.extend(removal["changed_files"])
            warnings.extend(removal["warnings"])
            results.append(
                {
                    "target": item,
                    "changed_files": removal["changed_files"],
                    "warnings": removal["warnings"],
                }
            )
        payload = {
            "generated_at": to_iso(utc_now()),
            "workspace": str(store.workspace),
            "target": target,
            "status": "removed",
            "changed_files": sorted(dict.fromkeys(changed_files)),
            "warnings": sorted(dict.fromkeys(warnings)),
            "results": results,
        }
        validate_document("autowire-report.schema.json", payload)
        payload["report_path"] = str(_write_report(store.workspace, "autowire", payload).relative_to(store.workspace))
        return payload

    if target == "all":
        targets = list(SUPPORTED_TARGETS)
        all_changed_files: list[str] = []
        all_warnings: list[str] = []
        all_results: list[dict[str, Any]] = []
        for item in targets:
            install = _install_target(store, item)
            verify = inspect_target(store, item)
            all_changed_files.extend(install["changed_files"])
            all_warnings.extend(install["warnings"])
            all_warnings.extend(verify["warnings"])
            all_results.append(
                {
                    "target": item,
                    "changed_files": verify["managed_paths"],
                    "warnings": verify["warnings"],
                }
            )
        payload = {
            "generated_at": to_iso(utc_now()),
            "workspace": str(store.workspace),
            "target": target,
            "status": "configured",
            "changed_files": sorted(dict.fromkeys(all_changed_files)),
            "warnings": sorted(dict.fromkeys(all_warnings)),
            "results": all_results,
        }
        validate_document("autowire-report.schema.json", payload)
        payload["report_path"] = str(_write_report(store.workspace, "autowire", payload).relative_to(store.workspace))
        return payload

    selector = "configured" if target == "auto" else target
    report = activate_agents(store, targets=selector, repair=False)
    compatibility_results = []
    for item in report["targets"]:
        compatibility_results.append(
            {
                "target": item["target_kind"],
                "changed_files": item.get("managed_paths", []),
                "warnings": item.get("warnings", []),
            }
        )
    payload = {
        "generated_at": report["generated_at"],
        "workspace": report["workspace"],
        "target": target,
        "status": "configured",
        "changed_files": report.get("changed_files", []),
        "warnings": report.get("warnings", []),
        "results": compatibility_results,
        "report_path": report["report_path"],
    }
    validate_document("autowire-report.schema.json", payload)
    return payload


def detect_agents(workspace: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for target in SUPPORTED_TARGETS:
        detected, configured = _detect_target(workspace, target)
        results.append(
            {
                "target_kind": target,
                "detected": detected,
                "configured": configured,
                "activation_mode": _activation_mode(target),
            }
        )
    return results


def inspect_target(store: MemoryStore, target: str) -> dict[str, Any]:
    workspace = store.workspace
    detected, configured = _detect_target(workspace, target)
    expected = _expected_target_state(store, target)
    surfaces: list[dict[str, Any]] = []
    warnings: list[str] = []
    smoke_checks: list[dict[str, Any]] = []
    drift_state = "clean"
    activated = True

    for surface in expected["surfaces"]:
        assessment = _assess_surface(workspace, surface)
        surfaces.append(assessment)
        if assessment["smoke"]["status"] != "passed":
            warnings.append(assessment["smoke"]["detail"])
        smoke_checks.append(assessment["smoke"])
        if assessment["state"] == "missing":
            drift_state = "missing"
            activated = False
        elif assessment["state"] == "drifted" and drift_state != "missing":
            drift_state = "drifted"
            activated = False

    if not detected and not configured and all(surface["state"] == "missing" for surface in surfaces):
        return {
            "target_kind": target,
            "detected": False,
            "configured": False,
            "activation_mode": _activation_mode(target),
            "managed_paths": [],
            "drift_state": "unknown",
            "health_state": "unknown",
            "activated": False,
            "managed_surfaces": [],
            "warnings": [],
            "smoke": [],
        }

    health_state = "healthy"
    if drift_state == "missing":
        health_state = "broken"
    elif drift_state == "drifted" or not smoke_checks or any(item["status"] != "passed" for item in smoke_checks):
        health_state = "degraded"

    managed_paths = sorted({surface["path"] for surface in surfaces})
    return {
        "target_kind": target,
        "detected": detected or bool(managed_paths),
        "configured": configured or bool(managed_paths),
        "activation_mode": _activation_mode(target),
        "managed_paths": managed_paths,
        "drift_state": drift_state,
        "health_state": health_state,
        "activated": activated and bool(managed_paths),
        "managed_surfaces": surfaces,
        "warnings": warnings,
        "smoke": smoke_checks,
    }


def load_agent_registry(workspace: Path) -> dict[str, Any]:
    if (workspace / TARGET_REGISTRY_PATH).exists():
        return cast(dict[str, Any], read_json(workspace / TARGET_REGISTRY_PATH, {}))
    return cast(dict[str, Any], read_json(workspace / REGISTRY_PATH, {}))


def load_activation_state(workspace: Path) -> dict[str, Any]:
    return cast(dict[str, Any], read_json(workspace / ACTIVATION_STATE_PATH, {}))


def _write_registry(workspace: Path, payload: dict[str, Any]) -> None:
    validate_document("target-registry.schema.json", payload)
    write_json(workspace / TARGET_REGISTRY_PATH, payload)
    write_json(workspace / REGISTRY_PATH, payload)


def _write_activation_state(workspace: Path, payload: dict[str, Any]) -> None:
    validate_document("activation-state.schema.json", payload)
    write_json(workspace / ACTIVATION_STATE_PATH, payload)


def _write_report(workspace: Path, prefix: str, payload: dict[str, Any]) -> Path:
    report_id = stable_id(prefix, payload["workspace"], payload["generated_at"], payload["status"])
    path = workspace / REPORTS_DIR / f"{prefix}-{report_id}.json"
    write_json(path, payload)
    latest = workspace / REPORTS_DIR / f"{prefix}-latest.json"
    write_json(latest, payload)
    return path


def _select_targets(detections: list[dict[str, Any]], selector: str) -> list[str]:
    if selector == "configured":
        return [item["target_kind"] for item in detections if item["configured"]]
    if selector == "all-detected":
        return [item["target_kind"] for item in detections if item["detected"]]
    if selector not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported activation target selector: {selector}")
    return [selector]


def _select_targets_for_autowire(workspace: Path, selector: str) -> list[str]:
    detections = detect_agents(workspace)
    if selector == "auto":
        selected = _select_targets(detections, "configured")
        return selected or ["codex"]
    if selector == "all":
        return list(SUPPORTED_TARGETS)
    return [selector]


def _select_targets_for_deactivation(
    detections: list[dict[str, Any]],
    registry: dict[str, dict[str, Any]],
    selector: str,
) -> list[str]:
    registry_targets = {
        target
        for target, record in registry.items()
        if record.get("activated") or record.get("managed_paths")
    }
    if selector == "configured":
        selected = [
            item["target_kind"]
            for item in detections
            if item["configured"] or item["target_kind"] in registry_targets
        ]
        return selected
    if selector == "all-detected":
        selected = [
            item["target_kind"]
            for item in detections
            if item["detected"] or item["target_kind"] in registry_targets
        ]
        return selected
    if selector not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported activation target selector: {selector}")
    return [selector]


def _activation_mode(target: str) -> str:
    if target == "codex":
        return "managed_wrapper"
    return "native_hooks"


def _detect_target(workspace: Path, target: str) -> tuple[bool, bool]:
    if target == "claude-code":
        detected = (workspace / ".claude").exists() or (workspace / "CLAUDE.md").exists()
        configured = (workspace / ".claude").exists() or (workspace / CLAUDE_SETTINGS_PATH).exists()
        return detected, configured
    if target == "codex":
        detected = (workspace / ".codex").exists() or (workspace / CODEX_AGENTS_PATH).exists()
        configured = detected
        return detected, configured
    if target == "openclaw":
        detected = (workspace / ".openclaw").exists()
        configured = detected or (workspace / OPENCLAW_CONFIG_PATH).exists()
        return detected, configured
    raise ValueError(f"unsupported target: {target}")


def _install_target(store: MemoryStore, target: str) -> dict[str, Any]:
    if target == "claude-code":
        return _install_claude(store)
    if target == "codex":
        return _install_codex(store)
    if target == "openclaw":
        return _install_openclaw(store)
    raise ValueError(f"unsupported target: {target}")


def _remove_target(store: MemoryStore, target: str) -> dict[str, Any]:
    if target == "claude-code":
        return _remove_claude(store.workspace)
    if target == "codex":
        return _remove_codex(store.workspace)
    if target == "openclaw":
        return _remove_openclaw(store.workspace)
    raise ValueError(f"unsupported target: {target}")


def _install_claude(store: MemoryStore) -> dict[str, Any]:
    workspace = store.workspace
    pre_path = workspace / HOOKS_DIR / "claude-pre-task.sh"
    post_path = workspace / HOOKS_DIR / "claude-post-task.sh"
    changed_files = _write_managed_script(pre_path, _pre_task_script(store, "claude"))
    changed_files.extend(_write_managed_script(post_path, _post_task_script(store, "claude")))

    settings_path = workspace / CLAUDE_SETTINGS_PATH
    payload = _load_json_object(settings_path)
    hooks = payload.setdefault("hooks", {})
    pre_task = hooks.setdefault("preTask", [])
    post_task = hooks.setdefault("postTask", [])
    pre_cmd = 'sh .opendream/hooks/claude-pre-task.sh "$CLAUDE_TASK"'
    post_cmd = 'sh .opendream/hooks/claude-post-task.sh "$CLAUDE_SUMMARY"'
    if pre_cmd not in pre_task:
        pre_task.append(pre_cmd)
    if post_cmd not in post_task:
        post_task.append(post_cmd)
    changed_files.extend(_write_if_changed(settings_path, json.dumps(payload, indent=2, sort_keys=True) + "\n"))
    return {"changed_files": changed_files, "warnings": []}


def _install_codex(store: MemoryStore) -> dict[str, Any]:
    workspace = store.workspace
    pre_path = workspace / HOOKS_DIR / "codex-pre-task.sh"
    post_path = workspace / HOOKS_DIR / "codex-post-task.sh"
    wrapper_path = workspace / BIN_DIR / "codex-task-wrapper.sh"
    changed_files = _write_managed_script(pre_path, _pre_task_script(store, "codex"))
    changed_files.extend(_write_managed_script(post_path, _post_task_script(store, "codex")))
    changed_files.extend(_write_managed_script(wrapper_path, _codex_wrapper_script(store)))
    agents_path = workspace / CODEX_AGENTS_PATH
    existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else "# AGENTS.md\n\n"
    block = _codex_block(store)
    updated = _replace_or_append_block(existing, _block_start("codex"), _block_end("codex"), block)
    changed_files.extend(_write_if_changed(agents_path, updated))
    return {"changed_files": changed_files, "warnings": []}


def _install_openclaw(store: MemoryStore) -> dict[str, Any]:
    workspace = store.workspace
    hook_path = workspace / HOOKS_DIR / "openclaw-hooks.sh"
    map_path = workspace / OPENCLAW_EVENT_MAP_PATH
    changed_files = _write_managed_script(hook_path, _openclaw_hook_script(store))
    changed_files.extend(_write_if_changed(map_path, _openclaw_event_map()))

    config_path = workspace / OPENCLAW_CONFIG_PATH
    payload = _load_json_object(config_path)
    hooks = payload.setdefault("hooks", {})
    pre_plan = hooks.setdefault("prePlan", [])
    post_task = hooks.setdefault("postTask", [])
    pre_cmd = 'sh .opendream/hooks/openclaw-hooks.sh pre-plan "$OPENCLAW_TASK"'
    post_cmd = 'sh .opendream/hooks/openclaw-hooks.sh post-task "$OPENCLAW_SUMMARY"'
    if pre_cmd not in pre_plan:
        pre_plan.append(pre_cmd)
    if post_cmd not in post_task:
        post_task.append(post_cmd)
    changed_files.extend(_write_if_changed(config_path, json.dumps(payload, indent=2, sort_keys=True) + "\n"))
    return {"changed_files": changed_files, "warnings": []}


def _remove_claude(workspace: Path) -> dict[str, Any]:
    settings_path = workspace / CLAUDE_SETTINGS_PATH
    payload = _load_json_object(settings_path)
    hooks = payload.setdefault("hooks", {})
    pre_cmd = 'sh .opendream/hooks/claude-pre-task.sh "$CLAUDE_TASK"'
    post_cmd = 'sh .opendream/hooks/claude-post-task.sh "$CLAUDE_SUMMARY"'
    hooks["preTask"] = [item for item in hooks.get("preTask", []) if item != pre_cmd]
    hooks["postTask"] = [
        item for item in hooks.get("postTask", []) if item != post_cmd
    ]
    changed_files = (
        _write_if_changed(settings_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        if settings_path.exists()
        else []
    )
    for path in [workspace / HOOKS_DIR / "claude-pre-task.sh", workspace / HOOKS_DIR / "claude-post-task.sh"]:
        if path.exists():
            path.unlink()
            changed_files.append(str(path))
    return {"changed_files": changed_files, "warnings": []}


def _remove_codex(workspace: Path) -> dict[str, Any]:
    changed_files: list[str] = []
    agents_path = workspace / CODEX_AGENTS_PATH
    if agents_path.exists():
        text = agents_path.read_text(encoding="utf-8")
        updated = _remove_block(text, _block_start("codex"), _block_end("codex"))
        updated = _remove_block(updated, LEGACY_CODEX_BLOCK_START, LEGACY_CODEX_BLOCK_END)
        changed_files.extend(_write_if_changed(agents_path, updated))
    for path in [
        workspace / HOOKS_DIR / "codex-pre-task.sh",
        workspace / HOOKS_DIR / "codex-post-task.sh",
        workspace / BIN_DIR / "codex-task-wrapper.sh",
    ]:
        if path.exists():
            path.unlink()
            changed_files.append(str(path))
    return {"changed_files": changed_files, "warnings": []}


def _remove_openclaw(workspace: Path) -> dict[str, Any]:
    config_path = workspace / OPENCLAW_CONFIG_PATH
    payload = _load_json_object(config_path)
    hooks = payload.setdefault("hooks", {})
    hooks["prePlan"] = [
        item
        for item in hooks.get("prePlan", [])
        if item != 'sh .opendream/hooks/openclaw-hooks.sh pre-plan "$OPENCLAW_TASK"'
    ]
    hooks["postTask"] = [
        item
        for item in hooks.get("postTask", [])
        if item != 'sh .opendream/hooks/openclaw-hooks.sh post-task "$OPENCLAW_SUMMARY"'
    ]
    changed_files = (
        _write_if_changed(config_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        if config_path.exists()
        else []
    )
    for path in [workspace / HOOKS_DIR / "openclaw-hooks.sh", workspace / OPENCLAW_EVENT_MAP_PATH]:
        if path.exists():
            path.unlink()
            changed_files.append(str(path))
    return {"changed_files": changed_files, "warnings": []}


def _service_requirement(store: MemoryStore, records: list[dict[str, Any]]) -> dict[str, Any]:
    from .service import service_status

    missing_targets: list[str] = []
    warnings: list[str] = []
    service_required_targets: list[str] = []
    if service_required_targets:
        status = service_status(store)
        if not status["installed"]:
            missing_targets.extend(service_required_targets)
            warnings.append("background service is required for at least one activated target but is not installed")
    return {
        "status": "missing" if missing_targets else "not-required",
        "required_targets": service_required_targets,
        "missing_targets": missing_targets,
        "warnings": warnings,
    }


def _build_agent_record(target: str, payload: dict[str, Any], *, activated_at: str | None = None) -> dict[str, Any]:
    record = {
        "target_kind": target,
        "detected": bool(payload.get("detected")),
        "configured": bool(payload.get("configured")),
        "activation_mode": str(payload.get("activation_mode", _activation_mode(target))),
        "managed_paths": list(payload.get("managed_paths", [])),
        "drift_state": str(payload.get("drift_state", "unknown")),
        "health_state": str(payload.get("health_state", "unknown")),
        "activated": bool(payload.get("activated", False)),
        "warnings": list(payload.get("warnings", [])),
        "smoke": list(payload.get("smoke", [])),
        "managed_surfaces": list(payload.get("managed_surfaces", [])),
    }
    if activated_at:
        record["last_activated_at"] = activated_at
    record["last_verified_at"] = to_iso(utc_now())
    validate_document("agent-target.schema.json", record)
    for surface in cast(list[dict[str, Any]], record["managed_surfaces"]):
        validate_document("managed-surface.schema.json", surface)
    return record


def _records_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for item in cast(list[dict[str, Any]], payload.get("targets", [])):
        target = item.get("target_kind")
        if isinstance(target, str):
            records[target] = item
    return records


def _collect_registry_records(
    store: MemoryStore,
    previous_registry: dict[str, dict[str, Any]],
    *,
    activated_targets: set[str],
    deactivated_targets: set[str] | None = None,
    generated_at: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    deactivated = deactivated_targets or set()
    for target in SUPPORTED_TARGETS:
        inspected = inspect_target(store, target)
        previous = previous_registry.get(target, {})
        should_include = (
            inspected["detected"]
            or inspected["configured"]
            or bool(inspected["managed_paths"])
            or bool(previous)
        )
        if not should_include:
            continue
        normalized = _normalize_registry_target(
            target,
            inspected,
            previous,
            activated_targets=activated_targets,
            deactivated_targets=deactivated,
        )
        activated_at = None
        if target in activated_targets and normalized["activated"]:
            activated_at = generated_at
        elif normalized["activated"]:
            previous_activated_at = previous.get("last_activated_at")
            if isinstance(previous_activated_at, str):
                activated_at = previous_activated_at
        records.append(_build_agent_record(target, normalized, activated_at=activated_at))
    return records


def _normalize_registry_target(
    target: str,
    inspected: dict[str, Any],
    previous: dict[str, Any],
    *,
    activated_targets: set[str],
    deactivated_targets: set[str] | None = None,
) -> dict[str, Any]:
    deactivated = deactivated_targets or set()
    if target in deactivated and _all_expected_surfaces_absent(inspected):
        return {
            "target_kind": target,
            "detected": inspected["detected"],
            "configured": inspected["configured"],
            "activation_mode": inspected["activation_mode"],
            "managed_paths": [],
            "drift_state": "clean",
            "health_state": "healthy",
            "activated": False,
            "managed_surfaces": [],
            "warnings": [],
            "smoke": [],
        }
    expects_managed_surfaces = bool(
        target in activated_targets or previous.get("activated") or previous.get("managed_paths")
    )
    if expects_managed_surfaces or not _all_expected_surfaces_absent(inspected):
        return inspected
    return {
        "target_kind": target,
        "detected": inspected["detected"],
        "configured": inspected["configured"],
        "activation_mode": inspected["activation_mode"],
        "managed_paths": [],
        "drift_state": "clean",
        "health_state": "healthy",
        "activated": False,
        "managed_surfaces": [],
        "warnings": [],
        "smoke": [],
    }


def _all_expected_surfaces_absent(inspected: dict[str, Any]) -> bool:
    surfaces = cast(list[dict[str, Any]], inspected.get("managed_surfaces", []))
    if not surfaces:
        return False
    return all(surface.get("state") in {"missing", "drifted"} for surface in surfaces)


def _activation_state_payload(
    workspace: Path,
    generated_at: str,
    records: list[dict[str, Any]],
    service_state: dict[str, Any],
) -> dict[str, Any]:
    status = "inactive"
    if service_state["status"] == "missing" or any(record["health_state"] == "broken" for record in records):
        status = "broken"
    elif any(record["activated"] for record in records):
        if all(record["activated"] and record["health_state"] == "healthy" for record in records):
            status = "active"
        else:
            status = "partial"
    payload = {
        "workspace": str(workspace),
        "generated_at": generated_at,
        "status": status,
        "targets": [_compressed_target_record(record) for record in records],
    }
    validate_document("activation-state.schema.json", payload)
    return payload


def _compressed_target_record(record: dict[str, Any]) -> dict[str, Any]:
    state = "inactive"
    if record.get("activated"):
        state = "active"
    elif record.get("configured") or record.get("detected"):
        state = "configured"
    if record.get("drift_state") in {"drifted", "missing"}:
        state = "drifted"
    return {
        "target_kind": record["target_kind"],
        "state": state,
        "configured": record["configured"],
        "activated": record["activated"],
        "drift_state": record["drift_state"],
        "health_state": record["health_state"],
        "managed_paths": record.get("managed_paths", []),
    }


def _compressed_overall_state(
    snapshot: dict[str, Any],
    activation_state: dict[str, Any],
    records: list[dict[str, Any]],
    service_runtime: dict[str, Any],
) -> str:
    if activation_state["status"] == "inactive" and not records:
        return "inactive"
    if activation_state["status"] == "broken":
        return "broken"
    if activation_state["status"] == "partial":
        return "degraded"
    if any(record["drift_state"] in {"drifted", "missing"} for record in records):
        return "degraded"
    if any(record["health_state"] != "healthy" for record in records if record["activated"]):
        return "degraded"
    if service_runtime["installed"] and service_runtime["health"] not in {"healthy", "idle"}:
        return "degraded"
    if snapshot["state"] == "uninitialized" and not any(record["activated"] for record in records):
        return "inactive"
    if activation_state["status"] in {"inactive", "partial"} and not any(record["activated"] for record in records):
        return "inactive"
    return "healthy"


def _next_action(
    workspace: Path,
    overall_state: str,
    targets: list[dict[str, Any]],
    runtime: dict[str, Any],
) -> str:
    configured_targets = [item["target_kind"] for item in targets if item["configured"]]
    drifted_targets = [item["target_kind"] for item in targets if item["state"] == "drifted"]
    if drifted_targets or overall_state in {"broken", "degraded"}:
        return f"run `opendream activate --workspace {workspace} --repair`"
    if configured_targets and not any(item["activated"] for item in targets):
        return f"run `opendream activate --workspace {workspace}`"
    if not targets:
        return (
            "configure Claude Code, Codex, or OpenClaw, then run "
            "`opendream init --workspace <path> --activate-configured`"
        )
    if runtime.get("memory_state") == "pending":
        return f"run `opendream maintain --workspace {workspace}` or let your configured hooks drain naturally"
    if runtime.get("service", {}).get("installed") and not runtime.get("service", {}).get("running"):
        return f"run `opendream service start --workspace {workspace}` if you want background polling"
    return "no action required"


def _expected_target_state(store: MemoryStore, target: str) -> dict[str, Any]:
    if target == "claude-code":
        pre_cmd = 'sh .opendream/hooks/claude-pre-task.sh "$CLAUDE_TASK"'
        post_cmd = 'sh .opendream/hooks/claude-post-task.sh "$CLAUDE_SUMMARY"'
        return {
            "surfaces": [
                _file_surface(
                    target,
                    HOOKS_DIR / "claude-pre-task.sh",
                    "hook-script",
                    _pre_task_script(store, "claude"),
                ),
                _file_surface(
                    target,
                    HOOKS_DIR / "claude-post-task.sh",
                    "hook-script",
                    _post_task_script(store, "claude"),
                ),
                _json_surface(
                    target,
                    CLAUDE_SETTINGS_PATH,
                    "native-hooks",
                    {"hooks": {"preTask": [pre_cmd], "postTask": [post_cmd]}},
                ),
            ]
        }
    if target == "codex":
        return {
            "surfaces": [
                _file_surface(
                    target,
                    HOOKS_DIR / "codex-pre-task.sh",
                    "hook-script",
                    _pre_task_script(store, "codex"),
                ),
                _file_surface(
                    target,
                    HOOKS_DIR / "codex-post-task.sh",
                    "hook-script",
                    _post_task_script(store, "codex"),
                ),
                _file_surface(
                    target,
                    BIN_DIR / "codex-task-wrapper.sh",
                    "managed-wrapper",
                    _codex_wrapper_script(store),
                ),
                _block_surface(target, CODEX_AGENTS_PATH, "repo-instructions", _codex_block(store)),
            ]
        }
    if target == "openclaw":
        pre_cmd = 'sh .opendream/hooks/openclaw-hooks.sh pre-plan "$OPENCLAW_TASK"'
        post_cmd = 'sh .opendream/hooks/openclaw-hooks.sh post-task "$OPENCLAW_SUMMARY"'
        return {
            "surfaces": [
                _file_surface(
                    target,
                    HOOKS_DIR / "openclaw-hooks.sh",
                    "hook-script",
                    _openclaw_hook_script(store),
                ),
                _file_surface(target, OPENCLAW_EVENT_MAP_PATH, "event-map", _openclaw_event_map()),
                _json_surface(
                    target,
                    OPENCLAW_CONFIG_PATH,
                    "native-hooks",
                    {"hooks": {"prePlan": [pre_cmd], "postTask": [post_cmd]}},
                ),
            ]
        }
    raise ValueError(f"unsupported target: {target}")


def _assess_surface(workspace: Path, surface: dict[str, Any]) -> dict[str, Any]:
    path = workspace / surface["path"]
    state = "clean"
    detail = "surface is live"
    if surface["mode"] == "file":
        if not path.exists():
            state = "missing"
            detail = f"missing managed file {surface['path']}"
        else:
            content = path.read_text(encoding="utf-8")
            if content != surface["expected"]:
                state = "drifted"
                detail = f"managed file drift detected at {surface['path']}"
    elif surface["mode"] == "json":
        if not path.exists():
            state = "missing"
            detail = f"missing config file {surface['path']}"
        else:
            payload = _load_json_object(path)
            if not _json_contains_expected(payload, surface["expected"]):
                state = "drifted"
                detail = f"managed hook entries drifted at {surface['path']}"
    elif surface["mode"] == "block":
        if not path.exists():
            state = "missing"
            detail = f"missing block carrier {surface['path']}"
        else:
            text = path.read_text(encoding="utf-8")
            block = _extract_block(text, _block_start(surface["target"]), _block_end(surface["target"]))
            if block != surface["expected"]:
                state = "drifted"
                detail = f"managed block drift detected at {surface['path']}"
    smoke = {"status": "passed", "detail": detail}
    if state == "clean" and surface["kind"] in {"hook-script", "managed-wrapper"}:
        check = subprocess.run(
            ["/bin/sh", "-n", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if check.returncode != 0:
            state = "drifted"
            smoke = {"status": "failed", "detail": f"shell syntax check failed for {surface['path']}"}
    elif state != "clean":
        smoke = {"status": "failed", "detail": detail}
    return {
        "target_kind": surface["target_kind"],
        "path": surface["path"],
        "kind": surface["kind"],
        "hash": surface["hash"],
        "managed": True,
        "state": state,
        "smoke": smoke,
    }


def _file_surface(target: str, relative_path: Path, kind: str, expected: str) -> dict[str, Any]:
    return {
        "target_kind": target,
        "path": str(relative_path),
        "kind": kind,
        "hash": _sha256_text(expected),
        "mode": "file",
        "expected": expected,
    }


def _json_surface(target: str, relative_path: Path, kind: str, expected: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_kind": target,
        "path": str(relative_path),
        "kind": kind,
        "hash": _sha256_text(json.dumps(expected, sort_keys=True)),
        "mode": "json",
        "expected": expected,
    }


def _block_surface(target: str, relative_path: Path, kind: str, expected: str) -> dict[str, Any]:
    return {
        "target_kind": target,
        "path": str(relative_path),
        "kind": kind,
        "hash": _sha256_text(expected),
        "mode": "block",
        "expected": expected,
        "target": target,
    }


def _pre_task_script(store: MemoryStore, target: str) -> str:
    command = _opendream_command(store, "prepare-context")
    output_name = f"{target}-pre-task.json"
    return "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            "",
            'WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"',
            'QUERY="${1:-${OPENDREAM_QUERY:-current task}}"',
            'GLOBAL="${OPENDREAM_GLOBAL_WORKSPACE:-}"',
            f'OUTPUT="$WORKSPACE/{CONTEXT_DIR}/{output_name}"',
            'mkdir -p "$(dirname "$OUTPUT")"',
            'if [ -n "$GLOBAL" ]; then',
            f'  {command} --query "$QUERY" --include-global --global-workspace "$GLOBAL" > "$OUTPUT"',
            "else",
            f'  {command} --query "$QUERY" > "$OUTPUT"',
            "fi",
            'cat "$OUTPUT"',
            "",
        ]
    )


def _post_task_script(store: MemoryStore, target: str) -> str:
    emit_command = _opendream_command(store, "emit-event")
    maintain_command = _opendream_command(store, "maintain")
    worker_command = _opendream_command(store, "dream worker")
    ref = f"{target}-post-task"
    return "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            "",
            'WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"',
            'SUMMARY="${1:-${OPENDREAM_SUMMARY:-Task completed.}}"',
            f'MESSAGE_REF="${{OPENDREAM_REF:-{ref}}}"',
            f'{emit_command} --kind task_outcome --content "$SUMMARY" --message-ref "$MESSAGE_REF"',
            f"{maintain_command}",
            f"{worker_command} --once",
            "",
        ]
    )


def _openclaw_hook_script(store: MemoryStore) -> str:
    prepare_command = _opendream_command(store, "prepare-context")
    emit_command = _opendream_command(store, "emit-event")
    maintain_command = _opendream_command(store, "maintain")
    worker_command = _opendream_command(store, "dream worker")
    return "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            "",
            'MODE="${1:-pre-plan}"',
            'PAYLOAD="${2:-${OPENCLAW_TASK:-current task}}"',
            'WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"',
            'GLOBAL="${OPENDREAM_GLOBAL_WORKSPACE:-}"',
            f'OUTPUT="$WORKSPACE/{CONTEXT_DIR}/openclaw-pre-task.json"',
            'mkdir -p "$(dirname "$OUTPUT")"',
            'if [ "$MODE" = "pre-plan" ]; then',
            '  if [ -n "$GLOBAL" ]; then',
            f'    {prepare_command} --query "$PAYLOAD" --include-global --global-workspace "$GLOBAL" > "$OUTPUT"',
            "  else",
            f'    {prepare_command} --query "$PAYLOAD" > "$OUTPUT"',
            "  fi",
            '  cat "$OUTPUT"',
            "  exit 0",
            "fi",
            (
                f'{emit_command} --kind task_outcome --content "$PAYLOAD" '
                '--message-ref "${OPENCLAW_REF:-openclaw-post-task}"'
            ),
            f"{maintain_command}",
            f"{worker_command} --once",
            "",
        ]
    )


def _codex_wrapper_script(store: MemoryStore) -> str:
    del store
    return "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            "",
            'SUMMARY="${OPENDREAM_SUMMARY:-Codex task completed.}"',
            'QUERY="${OPENDREAM_QUERY:-$SUMMARY}"',
            'if [ "${1:-}" = "--summary" ]; then',
            '  SUMMARY="$2"',
            "  shift 2",
            "fi",
            'if [ "${1:-}" = "--query" ]; then',
            '  QUERY="$2"',
            "  shift 2",
            "fi",
            'if [ "${1:-}" = "--" ]; then',
            "  shift",
            "fi",
            'sh .opendream/hooks/codex-pre-task.sh "$QUERY"',
            "status=0",
            'if [ "$#" -gt 0 ]; then',
            '  "$@" || status=$?',
            "fi",
            'post_status=0',
            'sh .opendream/hooks/codex-post-task.sh "$SUMMARY" || post_status=$?',
            'if [ "$status" -eq 0 ] && [ "$post_status" -ne 0 ]; then',
            '  status="$post_status"',
            "fi",
            'exit "$status"',
            "",
        ]
    )


def _codex_block(store: MemoryStore) -> str:
    del store
    return "\n".join(
        [
            _block_start("codex"),
            "",
            "## OpenDream Activation",
            "",
            "Before substantial work, run:",
            '`sh .opendream/hooks/codex-pre-task.sh "${OPENDREAM_QUERY:-current task}"`',
            "",
            "Before the final response, run:",
            '`sh .opendream/hooks/codex-post-task.sh "${OPENDREAM_SUMMARY:-Task completed.}"`',
            "",
            "For scripted Codex entrypoints, prefer:",
            (
                '`sh .opendream/bin/codex-task-wrapper.sh '
                '--summary "${OPENDREAM_SUMMARY:-Task completed.}" -- <agent command>`'
            ),
            "",
            _block_end("codex"),
            "",
        ]
    )


def _openclaw_event_map() -> str:
    return "\n".join(
        [
            "# OpenDream OpenClaw event map",
            "",
            '- `planner.pre_plan` -> `sh .opendream/hooks/openclaw-hooks.sh pre-plan "$OPENCLAW_TASK"`',
            '- `worker.post_task` -> `sh .opendream/hooks/openclaw-hooks.sh post-task "$OPENCLAW_SUMMARY"`',
            "",
        ]
    )


def _opendream_command(store: MemoryStore, command: str) -> str:
    flags = ["opendream", *command.split(), "--workspace", '"$WORKSPACE"']
    if store.memory_dir_name != "memory":
        flags.extend(["--memory-dir", shlex.quote(store.memory_dir_name)])
    if store.compat_mode != "canonical":
        flags.extend(["--compat-mode", shlex.quote(store.compat_mode)])
    return " ".join(flags)


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _json_contains_expected(payload: dict[str, Any], expected: dict[str, Any]) -> bool:
    for key, value in expected.items():
        current = payload.get(key)
        if isinstance(value, dict):
            if not isinstance(current, dict) or not _json_contains_expected(current, value):
                return False
        elif isinstance(value, list):
            if not isinstance(current, list):
                return False
            for item in value:
                if item not in current:
                    return False
        else:
            if current != value:
                return False
    return True


def _write_managed_script(path: Path, content: str) -> list[str]:
    changed = _write_if_changed(path, content)
    if changed:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return changed


def _write_if_changed(path: Path, content: str) -> list[str]:
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == content:
        return []
    atomic_write_text(path, content)
    return [str(path)]


def _replace_or_append_block(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    updated = _remove_block(text, LEGACY_CODEX_BLOCK_START, LEGACY_CODEX_BLOCK_END)
    if start_marker in updated and end_marker in updated:
        start = updated.index(start_marker)
        end = updated.index(end_marker, start) + len(end_marker)
        if updated[end : end + 1] == "\n":
            end += 1
        tail = updated[end:]
        return updated[:start] + replacement + tail
    return updated.rstrip() + "\n\n" + replacement


def _remove_block(text: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in text or end_marker not in text:
        return text
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    return ((text[:start] + text[end:]).replace("\n\n\n", "\n\n")).lstrip("\n")


def _extract_block(text: str, start_marker: str, end_marker: str) -> str | None:
    if start_marker not in text or end_marker not in text:
        return None
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    tail = text[end:]
    if tail.startswith("\n"):
        end += 1
    return text[start:end]


def _block_start(target: str) -> str:
    return f"<!-- BEGIN OPENDREAM MANAGED BLOCK: {target} -->"


def _block_end(target: str) -> str:
    return f"<!-- END OPENDREAM MANAGED BLOCK: {target} -->"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
