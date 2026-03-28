from __future__ import annotations

import json
import os
import shlex
import subprocess
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from .storage import MemoryStore
from .util import parse_timestamp, stable_id
from .validation import SchemaValidationError, validate_document

SUPERSEDE_TYPES = {"project_decision", "environment_requirement", "user_preference"}
SUPPORTED_OPS = {
    "create",
    "update",
    "supersede",
    "mark_contested",
    "quarantine_candidate",
    "quarantine_memory",
    "ignore",
}


def build_plan(
    store: MemoryStore,
    *,
    run_id: str,
    now: str,
    pending_candidates: list[dict[str, Any]],
    existing_records: list[dict[str, Any]],
) -> dict[str, Any]:
    adapter_command = _adapter_command(store, "planner", "OPENDREAM_PLANNER_COMMAND")
    warnings: list[str] = []
    if adapter_command:
        adapter_payload = {
            "run_id": run_id,
            "generated_at": now,
            "pending_candidates": pending_candidates,
            "existing_records": existing_records,
        }
        adapted = _run_adapter(
            adapter_command,
            timeout_seconds=int(store.config["planner"]["timeout_seconds"]),
            schema_name="dream-plan.schema.json",
            payload=adapter_payload,
        )
        if adapted is not None:
            adapted.setdefault("planner_mode", "adapter")
            adapted.setdefault("warnings", [])
            return adapted
        warnings.append("planner adapter failed; fell back to builtin planner")

    plan = _build_builtin_plan(
        store,
        run_id=run_id,
        now=now,
        pending_candidates=pending_candidates,
        existing_records=existing_records,
    )
    if warnings:
        plan["warnings"] = warnings
    return plan


def _build_builtin_plan(
    store: MemoryStore,
    *,
    run_id: str,
    now: str,
    pending_candidates: list[dict[str, Any]],
    existing_records: list[dict[str, Any]],
) -> dict[str, Any]:
    existing_lookup = {
        (item["scope"], item["type"], item["title"]): item for item in existing_records if item["status"] == "active"
    }
    workflow_evidence: Counter[tuple[str, str]] = Counter()
    workflow_events: dict[tuple[str, str], set[str]] = defaultdict(set)
    threshold = int(store.config["promotion"]["workflow_min_successful_recalls"])
    candidate_ttl_days = int(store.config["retention"]["candidate_ttl_days"])
    now_dt = parse_timestamp(now)

    for record in existing_records:
        if record["type"] == "procedural_workflow":
            workflow_key = (record["scope"], record["title"])
            workflow_evidence[workflow_key] += len(set(record["source_event_ids"]))
            workflow_events[workflow_key].update(record["source_event_ids"])

    for candidate in pending_candidates:
        if candidate["type"] == "procedural_workflow":
            workflow_key = (candidate["scope"], candidate["title"])
            workflow_evidence[workflow_key] += len(set(candidate["derived_from_event_ids"]))
            workflow_events[workflow_key].update(candidate["derived_from_event_ids"])

    actions: list[dict[str, Any]] = []
    for candidate in pending_candidates:
        action = _plan_candidate(
            candidate,
            existing_lookup=existing_lookup,
            workflow_evidence=workflow_evidence,
            workflow_events=workflow_events,
            workflow_threshold=threshold,
            candidate_ttl_days=candidate_ttl_days,
            now=now,
            now_dt=now_dt,
            run_id=run_id,
        )
        actions.append(action)

    pending_decay_days = int(store.config["retention"]["pending_item_decay_days"])
    weak_decay_days = int(store.config["retention"]["weak_memory_quarantine_days"])
    for record in existing_records:
        if record["status"] != "active":
            continue
        age_days = (now_dt - parse_timestamp(record["updated_at"])).days
        if record["type"] == "pending_item" and age_days > pending_decay_days:
            actions.append(
                _action(
                    run_id,
                    op="quarantine_memory",
                    target_id=record["memory_id"],
                    reason="stale pending item removed from startup index",
                    source_event_ids=record["source_event_ids"],
                    payload={"record": record},
                )
            )
        elif record["type"] == "semantic_fact" and record["confidence"] < 0.5 and age_days > weak_decay_days:
            actions.append(
                _action(
                    run_id,
                    op="quarantine_memory",
                    target_id=record["memory_id"],
                    reason="stale low-confidence fact quarantined",
                    source_event_ids=record["source_event_ids"],
                    payload={"record": record},
                )
            )

    plan = {
        "plan_id": stable_id("plan", run_id, now, len(actions)),
        "run_id": run_id,
        "generated_at": now,
        "planner_mode": "builtin",
        "actions": actions,
        "warnings": [],
        "stats": {
            "candidate_count": len(pending_candidates),
            "planned_action_count": len(actions),
            "existing_record_count": len(existing_records),
        },
    }
    validate_document("dream-plan.schema.json", plan)
    return plan


def _plan_candidate(
    candidate: dict[str, Any],
    *,
    existing_lookup: dict[tuple[str, str, str], dict[str, Any]],
    workflow_evidence: Counter[tuple[str, str]],
    workflow_events: dict[tuple[str, str], set[str]],
    workflow_threshold: int,
    candidate_ttl_days: int,
    now: str,
    now_dt: Any,
    run_id: str,
) -> dict[str, Any]:
    candidate_age = now_dt - parse_timestamp(candidate["created_at"])
    if candidate_age > timedelta(days=candidate_ttl_days):
        return _action(
            run_id,
            op="quarantine_candidate",
            target_id=candidate["candidate_id"],
            reason="candidate expired before consolidation",
            source_event_ids=candidate["derived_from_event_ids"],
            payload={"candidate": candidate},
        )
    if candidate["confidence"] < 0.45:
        return _action(
            run_id,
            op="quarantine_candidate",
            target_id=candidate["candidate_id"],
            reason="candidate confidence below promotion threshold",
            source_event_ids=candidate["derived_from_event_ids"],
            payload={"candidate": candidate},
        )

    lookup_key = (candidate["scope"], candidate["type"], candidate["title"])
    existing = existing_lookup.get(lookup_key)

    if candidate["type"] == "procedural_workflow":
        workflow_key = (candidate["scope"], candidate["title"])
        if workflow_evidence[workflow_key] < workflow_threshold:
            return _action(
                run_id,
                op="quarantine_candidate",
                target_id=candidate["candidate_id"],
                reason="workflow requires repeated successful evidence before promotion",
                source_event_ids=candidate["derived_from_event_ids"],
                payload={"candidate": candidate},
            )
        candidate = dict(candidate)
        candidate["derived_from_event_ids"] = sorted(workflow_events[workflow_key])

    if candidate["type"] == "contested_fact":
        if existing:
            reason = "updated contested memory with new evidence"
        else:
            reason = "created contested memory from contradiction signal"
        return _action(
            run_id,
            op="mark_contested",
            target_id=existing["memory_id"] if existing else None,
            reason=reason,
            source_event_ids=candidate["derived_from_event_ids"],
            payload={"candidate": candidate, "existing": existing},
        )

    if existing and _same_body(existing, candidate):
        return _action(
            run_id,
            op="update",
            target_id=existing["memory_id"],
            reason="merged duplicate durable evidence",
            source_event_ids=candidate["derived_from_event_ids"],
            payload={"candidate": candidate, "existing": existing},
        )

    if existing and candidate["type"] in SUPERSEDE_TYPES:
        return _action(
            run_id,
            op="supersede",
            target_id=existing["memory_id"],
            reason="superseded by stronger or newer explicit durable memory",
            source_event_ids=candidate["derived_from_event_ids"],
            payload={"candidate": candidate, "existing": existing},
        )

    if existing:
        return _action(
            run_id,
            op="mark_contested",
            target_id=existing["memory_id"],
            reason="conflicting evidence kept as contested memory",
            source_event_ids=candidate["derived_from_event_ids"],
            payload={"candidate": candidate, "existing": existing},
        )

    return _action(
        run_id,
        op="create",
        target_id=None,
        reason="created new durable memory",
        source_event_ids=candidate["derived_from_event_ids"],
        payload={"candidate": candidate},
    )


def _same_body(existing: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return str(existing["body"]).strip() == str(candidate["body"]).strip()


def _action(
    run_id: str,
    *,
    op: str,
    target_id: str | None,
    reason: str,
    source_event_ids: list[str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    candidate_id = ""
    if isinstance(payload.get("candidate"), dict):
        candidate_id = str(payload["candidate"].get("candidate_id", ""))
    return {
        "action_id": stable_id("plan-action", run_id, op, target_id or candidate_id),
        "op": op,
        "target_id": target_id,
        "reason": reason,
        "source_event_ids": source_event_ids,
        "payload": payload,
    }


def _adapter_command(store: MemoryStore, config_key: str, env_key: str) -> str | None:
    configured = store.config.get(config_key, {}).get("command")
    if isinstance(configured, str) and configured.strip():
        return configured
    env_value = os.environ.get(env_key, "").strip()
    return env_value or None


def _run_adapter(
    command: str,
    *,
    timeout_seconds: int,
    schema_name: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
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
        validate_document(schema_name, adapted)
    except (json.JSONDecodeError, SchemaValidationError):
        return None
    return adapted if isinstance(adapted, dict) else None
