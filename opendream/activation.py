from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from . import activation_primitives as P
from .adapter_loader import (
    adapter_ids_for_workspace,
    builtin_adapter_ids,
    load_merged_adapters,
)
from .adapter_profiles import (
    detect_from_manifest,
    expected_surfaces,
    install_adapter,
    remove_adapter,
)
from .memory_quality import analyze_memory_quality
from .semantic_readiness import empty_context_pruning
from .storage import MemoryStore
from .util import CLI_JSON_VERSION, read_json, stable_id, to_iso, utc_now, write_json
from .validation import validate_document

SUPPORTED_TARGETS = builtin_adapter_ids()
REGISTRY_PATH = Path(".opendream/agents.json")
TARGET_REGISTRY_PATH = Path(".opendream/targets.json")
ACTIVATION_STATE_PATH = Path(".opendream/activation-state.json")
REPORTS_DIR = Path(".opendream/reports")


def activate_agents(store: MemoryStore, *, targets: str, repair: bool = False) -> dict[str, Any]:
    store.ensure_layout()
    workspace = store.workspace
    registry_before = load_agent_registry(workspace)
    registry_before_map = _records_by_target(registry_before)
    detections = detect_agents(workspace)
    selected = _select_targets(workspace, detections, targets)
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


def plan_agent_activation(store: MemoryStore, *, targets: str) -> dict[str, Any]:
    """Dry-run: report which managed surfaces would be created, updated, or left unchanged."""
    store.ensure_layout()
    workspace = store.workspace
    detections = detect_agents(workspace)
    selected = _select_targets(workspace, detections, targets)
    generated_at = to_iso(utc_now())
    target_plans: list[dict[str, Any]] = []
    remediation_cmds: list[str] = []
    for target in selected:
        expected = _expected_target_state(store, target)
        surface_plans: list[dict[str, Any]] = []
        for surface in expected["surfaces"]:
            assessment = P.assess_surface(workspace, surface)
            state = assessment["state"]
            if state == "clean":
                action = "noop"
            elif state == "missing":
                action = "create"
            else:
                action = "update"
            surface_plans.append(
                {
                    "path": surface["path"],
                    "kind": surface["kind"],
                    "action": action,
                    "detail": assessment["smoke"]["detail"],
                }
            )
        if any(item["action"] != "noop" for item in surface_plans):
            remediation_cmds.append(
                f"opendream activate --workspace {workspace} --targets {target}"
            )
        target_plans.append({"target_kind": target, "surfaces": surface_plans})
    if not selected:
        remediation = (
            "No targets matched this selector. Try `opendream doctor --workspace <path> --surface agents`, "
            "or install surfaces explicitly, e.g. "
            f"`opendream activate --workspace {workspace} --targets cursor`."
        )
    elif remediation_cmds:
        remediation = "Run: " + " ; ".join(dict.fromkeys(remediation_cmds))
    else:
        remediation = "No changes required for selected targets."
    payload = {
        "generated_at": generated_at,
        "workspace": str(workspace),
        "selector": targets,
        "selected_targets": selected,
        "targets": target_plans,
        "remediation": remediation,
    }
    validate_document("activation-plan.schema.json", payload)
    return payload


def deactivate_agents(store: MemoryStore, *, targets: str) -> dict[str, Any]:
    store.ensure_layout()
    workspace = store.workspace
    registry_before = load_agent_registry(workspace)
    registry_before_map = _records_by_target(registry_before)
    detections = detect_agents(workspace)
    selected = _select_targets_for_deactivation(workspace, detections, registry_before_map, targets)
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
        "automation": snapshot["automation"],
        "next_eligible_reason": snapshot["next_eligible_reason"],
        "next_eligible_at": snapshot["next_eligible_at"],
    }
    semantic_surface = _semantic_quality_surface(store, now=generated_at)
    operational_next_action = _next_action(store.workspace, overall_state, targets, runtime)
    payload = {
        **snapshot,
        "workspace": str(store.workspace),
        "overall_state": overall_state,
        "targets": targets,
        "runtime": runtime,
        "activation_state": activation_state,
        "service": service_state,
        "memory_layout": store.memory_layout_advisory(),
        **semantic_surface,
        "next_action": (
            semantic_surface["next_action"]
            if semantic_surface["semantic_capability_state"] in {"setup_required", "degraded"}
            else operational_next_action
        ),
        "context_pruning": empty_context_pruning(),
        "cli_output_version": CLI_JSON_VERSION,
    }
    validate_document("compressed-status.schema.json", payload)
    return payload


def format_compressed_status(payload: dict[str, Any]) -> str:
    lines = [
        f"workspace={payload['workspace']}",
        f"overall_state={payload['overall_state']}",
        f"next_action={payload['next_action']}",
    ]
    memory_layout = payload.get("memory_layout") or {}
    if memory_layout.get("active_memory_root"):
        lines.append(f"memory_root={memory_layout['active_memory_root']}")
    for warning in memory_layout.get("warnings") or []:
        lines.append(f"memory_warning={warning}")
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
                f"automation_due={len(runtime.get('automation', {}).get('due_job_ids', []))}",
            ]
        )
    )
    return "\n".join(lines)


def doctor_memory(store: MemoryStore) -> dict[str, Any]:
    ml = store.memory_layout_advisory()
    hints: list[str] = []
    if ml.get("shadow_memory_paths"):
        hints.append(
            "Shadow memory paths detected; only active_memory_root is authoritative for this invocation."
        )
    if not store.is_initialized():
        return {
            "generated_at": to_iso(utc_now()),
            "workspace": str(store.workspace),
            "surface": "memory",
            "status": "uninitialized",
            "memory_layout": ml,
            "durable_record_count": 0,
            "pending_events": 0,
            "pending_candidates": 0,
            **_semantic_quality_surface(store),
            "context_pruning": empty_context_pruning(),
            "hints": [*hints, "Run `opendream init --workspace <path>`."],
            "cli_output_version": CLI_JSON_VERSION,
        }
    store.ensure_layout()
    semantic_surface = _semantic_quality_surface(store)
    warnings = semantic_surface["memory_quality"].get("warnings") or []
    if warnings:
        hints.extend(str(item.get("remediation", "")).strip() for item in warnings if item.get("remediation"))
    return {
        "generated_at": to_iso(utc_now()),
        "workspace": str(store.workspace),
        "surface": "memory",
        "status": "warning" if warnings else "healthy",
        "memory_layout": ml,
        "durable_record_count": len(store.load_durable_records()),
        "pending_events": store.pending_event_count(),
        "pending_candidates": len(store.load_pending_candidates()),
        **semantic_surface,
        "context_pruning": empty_context_pruning(),
        "hints": list(dict.fromkeys(hints)),
        "cli_output_version": CLI_JSON_VERSION,
    }


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
    memory_layout = store.memory_layout_advisory()
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
        "memory_layout": memory_layout,
        "cli_output_version": CLI_JSON_VERSION,
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
        targets = sorted(load_merged_adapters(store.workspace).keys())
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
    merged = load_merged_adapters(workspace)
    results: list[dict[str, Any]] = []
    for adapter_id in sorted(merged.keys()):
        manifest = merged[adapter_id]
        detected, configured = detect_from_manifest(workspace, manifest)
        results.append(
            {
                "target_kind": adapter_id,
                "detected": detected,
                "configured": configured,
                "activation_mode": str(manifest["activation_mode"]),
            }
        )
    return results


def inspect_target(store: MemoryStore, target: str) -> dict[str, Any]:
    workspace = store.workspace
    merged = load_merged_adapters(workspace)
    manifest = merged.get(target)
    if not manifest:
        return {
            "target_kind": target,
            "detected": False,
            "configured": False,
            "activation_mode": "unsupported",
            "managed_paths": [],
            "drift_state": "unknown",
            "health_state": "unknown",
            "activated": False,
            "managed_surfaces": [],
            "warnings": [],
            "smoke": [],
        }

    detected, configured = detect_from_manifest(workspace, manifest)
    activation_mode = str(manifest["activation_mode"])
    expected = _expected_target_state(store, target)
    surfaces: list[dict[str, Any]] = []
    warnings: list[str] = []
    smoke_checks: list[dict[str, Any]] = []
    drift_state = "clean"
    activated = True

    for surface in expected["surfaces"]:
        assessment = P.assess_surface(workspace, surface)
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
            "activation_mode": activation_mode,
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
        "activation_mode": activation_mode,
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


def _select_targets(workspace: Path, detections: list[dict[str, Any]], selector: str) -> list[str]:
    merged = load_merged_adapters(workspace)
    merged_ids = set(merged.keys())
    if selector == "configured":
        return [item["target_kind"] for item in detections if item["configured"]]
    if selector == "all-detected":
        return [item["target_kind"] for item in detections if item["detected"]]
    if selector == "all-supported":
        return sorted(merged_ids)
    if selector in merged_ids:
        return [selector]
    raise ValueError(f"unsupported activation target selector: {selector}")


def _select_targets_for_autowire(workspace: Path, selector: str) -> list[str]:
    detections = detect_agents(workspace)
    if selector == "auto":
        selected = _select_targets(workspace, detections, "configured")
        return selected or ["codex"]
    if selector == "all":
        return sorted(load_merged_adapters(workspace).keys())
    return [selector]


def _select_targets_for_deactivation(
    workspace: Path,
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
    if selector == "all-supported":
        return sorted(load_merged_adapters(workspace).keys())
    merged = load_merged_adapters(workspace)
    if selector in merged:
        return [selector]
    raise ValueError(f"unsupported activation target selector: {selector}")


def _expected_target_state(store: MemoryStore, target: str) -> dict[str, Any]:
    merged = load_merged_adapters(store.workspace)
    manifest = merged.get(target)
    if not manifest:
        return {"surfaces": []}
    return {"surfaces": expected_surfaces(store, manifest)}


def _install_target(store: MemoryStore, target: str) -> dict[str, Any]:
    merged = load_merged_adapters(store.workspace)
    manifest = merged.get(target)
    if not manifest:
        raise ValueError(f"unknown adapter id: {target}")
    return install_adapter(store, manifest)


def _remove_target(store: MemoryStore, target: str) -> dict[str, Any]:
    merged = load_merged_adapters(store.workspace)
    manifest = merged.get(target)
    if not manifest:
        return {"changed_files": [], "warnings": []}
    return remove_adapter(store.workspace, manifest)


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
        "activation_mode": str(payload.get("activation_mode", "unsupported")),
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
    for target in adapter_ids_for_workspace(store.workspace, frozenset(previous_registry.keys())):
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
    if runtime.get("automation", {}).get("due_job_ids"):
        return f"run `opendream tick --workspace {workspace}` to process due automation jobs"
    if not targets:
        return (
            "configure an agent surface (Claude Code, Codex, OpenClaw, Cursor, Gemini CLI, Copilot, …), "
            "then run `opendream init --workspace <path> --activate-configured` "
            "or `opendream activate --workspace <path> --targets <name>`"
        )
    if runtime.get("memory_state") == "pending":
        return f"run `opendream maintain --workspace {workspace}` or let your configured hooks drain naturally"
    if runtime.get("service", {}).get("installed") and not runtime.get("service", {}).get("running"):
        return f"run `opendream service start --workspace {workspace}` if you want background polling"
    return "no action required"


def _semantic_quality_surface(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    report = analyze_memory_quality(store, now=now)
    posture_map = {
        "semantic_first": "semantic-first",
        "deterministic_only": "deterministic-by-choice",
    }
    return {
        "product_posture": posture_map.get(report["product_posture"], str(report["product_posture"])),
        "semantic_capability_state": report["semantic_capability_state"],
        "semantic_unavailability_reason": report["semantic_unavailability_reason"],
        "memory_quality": report["memory_quality"],
        "next_action": report["next_action"],
    }
