from __future__ import annotations

import json
import shlex
import subprocess
from typing import Any

from .planner import SUPPORTED_OPS, _adapter_command
from .storage import MemoryStore
from .util import stable_id
from .validation import SchemaValidationError, validate_document


def verify_plan(
    store: MemoryStore,
    *,
    run_id: str,
    now: str,
    plan: dict[str, Any],
    existing_records: list[dict[str, Any]],
) -> dict[str, Any]:
    adapter_command = _adapter_command(store, "verifier", "OPENDREAM_VERIFIER_COMMAND")
    warnings: list[str] = []
    if adapter_command:
        adapter_payload = {
            "run_id": run_id,
            "generated_at": now,
            "plan": plan,
            "existing_records": existing_records,
        }
        adapted = _run_adapter(
            adapter_command,
            timeout_seconds=int(store.config["verifier"]["timeout_seconds"]),
            payload=adapter_payload,
        )
        if adapted is not None:
            adapted.setdefault("verifier_mode", "adapter")
            adapted.setdefault("warnings", [])
            return adapted
        warnings.append("verifier adapter failed; fell back to builtin verifier")

    report = _builtin_report(run_id=run_id, now=now, plan=plan, existing_records=existing_records)
    if warnings:
        report["warnings"] = warnings
    return report


def _builtin_report(
    *,
    run_id: str,
    now: str,
    plan: dict[str, Any],
    existing_records: list[dict[str, Any]],
) -> dict[str, Any]:
    records_by_id = {record["memory_id"]: record for record in existing_records}
    findings: list[dict[str, Any]] = []
    blocked_action_ids: list[str] = []
    review_action_ids: list[str] = []

    for action in plan.get("actions", []):
        action_id = str(action.get("action_id", ""))
        op = str(action.get("op", ""))
        target_id = action.get("target_id")
        payload = action.get("payload", {})
        candidate = payload.get("candidate") if isinstance(payload, dict) else None
        source_event_ids = action.get("source_event_ids", [])

        if op not in SUPPORTED_OPS:
            findings.append(_finding(run_id, action_id, "error", "block", f"unsupported op: {op}"))
            blocked_action_ids.append(action_id)
            continue
        if not isinstance(source_event_ids, list) or not source_event_ids:
            findings.append(_finding(run_id, action_id, "error", "block", "missing provenance for planned action"))
            blocked_action_ids.append(action_id)
            continue
        if op in {"update", "supersede", "quarantine_memory"} and (
            not target_id or str(target_id) not in records_by_id
        ):
            findings.append(_finding(run_id, action_id, "error", "block", "target durable memory is missing"))
            blocked_action_ids.append(action_id)
            continue
        if op in {"create", "update", "supersede", "mark_contested"} and not isinstance(candidate, dict):
            findings.append(
                _finding(run_id, action_id, "error", "block", "candidate payload missing from planned action")
            )
            blocked_action_ids.append(action_id)
            continue

        confidence = float(candidate.get("confidence", 1.0)) if isinstance(candidate, dict) else 1.0
        if op in {"create", "update", "supersede"} and confidence < 0.5:
            findings.append(
                _finding(run_id, action_id, "error", "block", "durable write confidence below verifier floor")
            )
            blocked_action_ids.append(action_id)
            continue
        if op == "mark_contested":
            findings.append(
                _finding(
                    run_id,
                    action_id,
                    "warning",
                    "review",
                    "contested memory should remain visible for human review",
                )
            )
            review_action_ids.append(action_id)
            continue

        findings.append(_finding(run_id, action_id, "info", "allow", f"{op} passed builtin verifier checks"))

    if blocked_action_ids:
        commit_verdict = "block"
    elif review_action_ids:
        commit_verdict = "allow"
    else:
        commit_verdict = "allow"

    report = {
        "report_id": stable_id("verify", run_id, now, len(findings)),
        "run_id": run_id,
        "generated_at": now,
        "verifier_mode": "builtin",
        "commit_verdict": commit_verdict,
        "blocked_action_ids": blocked_action_ids,
        "review_action_ids": review_action_ids,
        "findings": findings,
        "warnings": [],
    }
    validate_document("verifier-report.schema.json", report)
    return report


def _finding(run_id: str, action_id: str, severity: str, verdict: str, message: str) -> dict[str, Any]:
    return {
        "finding_id": stable_id("finding", run_id, action_id, severity, verdict, message),
        "action_id": action_id,
        "severity": severity,
        "verdict": verdict,
        "message": message,
    }


def _run_adapter(command: str, *, timeout_seconds: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        completed = subprocess.run(
            shlex.split(command),
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    try:
        adapted = json.loads(completed.stdout)
        validate_document("verifier-report.schema.json", adapted)
    except (json.JSONDecodeError, SchemaValidationError):
        return None
    return adapted if isinstance(adapted, dict) else None
