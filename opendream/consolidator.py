from __future__ import annotations

import time
from typing import Any

from .claim_verification import classify_claim, verify_claim
from .extractor import build_title, classify_event, parse_workflow_steps
from .memory_types import canonical_memory_type, is_workflow_memory_type
from .models import ConsolidationOperation, MemoryRecord, RelationEdge, StartupIndexEntry
from .planner import build_plan
from .relation_graph import create_relation_store
from .storage import LockError, MemoryStore
from .util import CLI_JSON_VERSION, semantic_tokens, stable_id, summarize, to_iso, utc_now
from .verifier import verify_plan

SUPERSEDE_TYPES = {"project_decision", "environment_requirement", "user_preference"}
INDEX_TYPE_BOOSTS = {
    "project_decision": 5.0,
    "environment_requirement": 4.5,
    "workflow": 4.0,
    "procedural_workflow": 4.0,
    "anti_pattern": 3.5,
    "user_preference": 3.0,
    "pending_item": 2.5,
    "semantic_fact": 1.5,
}


def _candidate_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_tokens = semantic_tokens(" ".join([left["title"], left["summary"], left["body"]]))
    right_tokens = semantic_tokens(" ".join([right["title"], right["summary"], right["body"]]))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _merge_candidate_cluster(cluster: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(cluster, key=lambda item: (item["created_at"], item["candidate_id"]))
    primary = dict(ordered[0])
    primary["derived_from_event_ids"] = sorted(
        {event_id for item in ordered for event_id in item["derived_from_event_ids"]}
    )
    primary["memory_refs"] = sorted({memory_id for item in ordered for memory_id in item.get("memory_refs", [])})
    primary["conflicts_with"] = sorted(
        {memory_id for item in ordered for memory_id in item.get("conflicts_with", [])}
    )
    primary["confidence"] = round(max(item["confidence"] for item in ordered), 2)
    primary["salience"] = round(max(item["salience"] for item in ordered), 2)
    primary["summary"] = summarize(" ".join(item["summary"] for item in ordered), 140)
    primary["body"] = max((item["body"] for item in ordered), key=len)
    primary["status"] = "merged" if len(ordered) > 1 else primary["status"]
    return primary


def _cluster_candidates(candidates: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    clustered: list[list[dict[str, Any]]] = []
    for candidate in candidates:
        placed = False
        for cluster in clustered:
            exemplar = cluster[0]
            if (
                exemplar["scope"] == candidate["scope"]
                and canonical_memory_type(exemplar["type"]) == canonical_memory_type(candidate["type"])
                and _candidate_similarity(exemplar, candidate) >= threshold
            ):
                cluster.append(candidate)
                placed = True
                break
        if not placed:
            clustered.append([candidate])
    return [_merge_candidate_cluster(cluster) for cluster in clustered]


def _record_from_candidate(
    candidate: dict[str, Any],
    *,
    now: str,
    run_id: str,
    status: str = "active",
    supersedes: list[str] | None = None,
    conflicts_with: list[str] | None = None,
) -> dict[str, Any]:
    candidate_created_at = candidate["created_at"]
    source_event_ids = list(candidate["derived_from_event_ids"])
    record: dict[str, Any] = {
        "memory_id": stable_id("mem", candidate["candidate_id"], now),
        "type": canonical_memory_type(candidate["type"]),
        "scope": candidate["scope"],
        "title": candidate["title"],
        "summary": candidate["summary"],
        "body": candidate["body"],
        "status": status,
        "confidence": candidate["confidence"],
        "salience": candidate["salience"],
        "source_event_ids": source_event_ids,
        "supersedes": supersedes or [],
        "conflicts_with": conflicts_with or list(candidate.get("conflicts_with", [])),
        "valid_from": candidate_created_at,
        "valid_to": None,
        "access_count": 0,
        "last_accessed_at": None,
        "created_at": candidate_created_at,
        "updated_at": candidate_created_at,
        "lifecycle": _initial_lifecycle(
            status=status,
            now=now,
            source_event_ids=source_event_ids,
            promotion_run_id=run_id,
        ),
    }
    workflow_steps = candidate.get("workflow_steps", [])
    if workflow_steps:
        record["workflow_steps"] = workflow_steps
    # Claim verification: classify and assign provenance tier.
    claim_class = candidate.get("claim_class") or classify_claim(candidate["body"], title=candidate["title"])
    record["provenance_tier"] = candidate.get("provenance_tier", "inferred")
    record["claim_class"] = claim_class
    # Procedural memory enrichment.
    for key in ("preconditions", "recovery_steps", "anti_patterns", "success_markers"):
        if candidate.get(key):
            record[key] = candidate[key]
    return record


def _initial_lifecycle(
    *,
    status: str,
    now: str,
    source_event_ids: list[str],
    promotion_run_id: str | None,
) -> dict[str, Any]:
    state = _lifecycle_state(status)
    return {
        "state": state,
        "created_at": now,
        "updated_at": now,
        "last_transition_at": now,
        "last_reinforced_at": now if state == "active" else None,
        "promoted_at": now if state == "active" else None,
        "promotion_run_id": promotion_run_id,
        "transition_count": 1,
        "source_event_count": len(set(source_event_ids)),
    }


def _lifecycle_state(status: object) -> str:
    value = str(status or "active")
    if value in {"active", "contested", "superseded", "quarantined", "deleted"}:
        return value
    return "active"


def _ensure_lifecycle(record: dict[str, Any], *, now: str) -> dict[str, Any]:
    lifecycle = record.get("lifecycle")
    source_event_count = len(set(record.get("source_event_ids", [])))
    state = _lifecycle_state(record.get("status"))
    if not isinstance(lifecycle, dict):
        lifecycle = {
            "state": state,
            "created_at": str(record.get("created_at") or now),
            "updated_at": str(record.get("updated_at") or now),
            "last_transition_at": str(record.get("updated_at") or now),
            "last_reinforced_at": str(record.get("updated_at") or now) if state == "active" else None,
            "promoted_at": str(record.get("valid_from") or record.get("created_at") or now) if state == "active" else None,
            "promotion_run_id": None,
            "transition_count": 0,
            "source_event_count": source_event_count,
        }
        record["lifecycle"] = lifecycle
        return lifecycle

    lifecycle.setdefault("state", state)
    lifecycle.setdefault("created_at", str(record.get("created_at") or now))
    lifecycle.setdefault("updated_at", str(record.get("updated_at") or now))
    lifecycle.setdefault("last_transition_at", str(record.get("updated_at") or now))
    lifecycle.setdefault("last_reinforced_at", None)
    lifecycle.setdefault(
        "promoted_at",
        str(record.get("valid_from") or record.get("created_at") or now) if state == "active" else None,
    )
    lifecycle.setdefault("promotion_run_id", None)
    lifecycle.setdefault("transition_count", 0)
    lifecycle["source_event_count"] = source_event_count
    return lifecycle


def _transition_lifecycle(record: dict[str, Any], *, status: str, now: str) -> None:
    lifecycle = _ensure_lifecycle(record, now=now)
    new_state = _lifecycle_state(status)
    if lifecycle.get("state") != new_state:
        lifecycle["transition_count"] = int(lifecycle.get("transition_count", 0)) + 1
        lifecycle["last_transition_at"] = now
    lifecycle["state"] = new_state
    lifecycle["updated_at"] = now
    lifecycle["source_event_count"] = len(set(record.get("source_event_ids", [])))


def _reinforce_lifecycle(record: dict[str, Any], *, now: str) -> None:
    lifecycle = _ensure_lifecycle(record, now=now)
    lifecycle["updated_at"] = now
    lifecycle["last_reinforced_at"] = now
    lifecycle["source_event_count"] = len(set(record.get("source_event_ids", [])))


def _make_operation(
    run_id: str,
    op: str,
    target_id: str,
    reason: str,
    source_event_ids: list[str],
    *,
    now: str,
    payload: dict[str, Any] | None = None,
) -> ConsolidationOperation:
    return ConsolidationOperation(
        op_id=stable_id("op", run_id, op, target_id, len(source_event_ids), reason),
        run_id=run_id,
        op=op,
        target_id=target_id,
        reason=reason,
        source_event_ids=source_event_ids,
        timestamp=now,
        payload=payload or {},
    )


def _build_startup_index(records: list[dict[str, Any]], *, memory_dir: str) -> list[StartupIndexEntry]:
    entries: list[StartupIndexEntry] = []
    for record in records:
        if record["status"] != "active":
            continue
        if record["type"] == "contested_fact":
            continue
        priority = round(
            INDEX_TYPE_BOOSTS.get(record["type"], 1.0)
            + float(record["confidence"])
            + float(record["salience"])
            + min(record["access_count"] * 0.1, 0.5),
            3,
        )
        entries.append(
            StartupIndexEntry(
                memory_id=record["memory_id"],
                title=record["title"],
                type=record["type"],
                summary=summarize(record["summary"]),
                path=f"{memory_dir}/topics/{record['memory_id']}.md",
                priority=priority,
            )
        )
    return sorted(entries, key=lambda item: (-item.priority, item.title))


def _bump(summary: dict[str, Any], key: str, amount: int = 1) -> None:
    summary[key] = int(summary.get(key, 0)) + amount


_RETYPE_ELIGIBLE_TYPES = frozenset(
    {"project_decision", "environment_requirement", "workflow", "procedural_workflow", "anti_pattern", "user_preference"}
)


def _retype_generic_records_from_source_events(
    records: list[dict[str, Any]],
    *,
    events_by_id: dict[str, dict[str, Any]],
    operations: list[ConsolidationOperation],
    summary: dict[str, Any],
    run_id: str,
    now: str,
) -> None:
    for record in records:
        if record.get("status") != "active" or record.get("type") != "semantic_fact":
            continue
        source_events = [
            events_by_id[event_id]
            for event_id in record.get("source_event_ids", [])
            if event_id in events_by_id
        ]
        if not source_events:
            continue
        inferred_types = {
            inferred
            for event in source_events
            if (inferred := classify_event(event)) in _RETYPE_ELIGIBLE_TYPES
        }
        if len(inferred_types) != 1:
            continue
        inferred_type = canonical_memory_type(next(iter(inferred_types)))
        exemplar = source_events[-1]
        record["type"] = inferred_type
        record["title"] = build_title(exemplar, inferred_type)
        record["claim_class"] = classify_claim(record["body"], title=record["title"])
        if is_workflow_memory_type(inferred_type):
            steps = parse_workflow_steps(record["body"])
            if steps:
                record["workflow_steps"] = steps
        elif "workflow_steps" in record:
            record.pop("workflow_steps", None)
        record["updated_at"] = now
        _bump(summary, "updated")
        operations.append(
            _make_operation(
                run_id,
                "update",
                record["memory_id"],
                f"retyped generic semantic_fact to {inferred_type} from source event evidence",
                list(record.get("source_event_ids", [])),
                now=now,
                payload={"retyped_from": "semantic_fact", "retyped_to": inferred_type},
            )
        )


def consolidate(
    store: MemoryStore,
    *,
    now: str | None = None,
    sleep_before_write: float = 0.0,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    run_id = stable_id("run", timestamp, "consolidate")
    try:
        with store.lock():
            if sleep_before_write:
                time.sleep(sleep_before_write)
            result = _consolidate_locked(store, run_id=run_id, now=timestamp)
    except LockError:
        return {
            "run_id": run_id,
            "status": "skipped",
            "reason": "lock-held",
            "created": 0,
            "updated": 0,
            "superseded": 0,
            "contested": 0,
            "quarantined": 0,
            "deleted": 0,
            "cli_output_version": CLI_JSON_VERSION,
        }
    result["cli_output_version"] = CLI_JSON_VERSION
    return result


def _consolidate_locked(store: MemoryStore, *, run_id: str, now: str) -> dict[str, Any]:
    before_snapshot = store.snapshot_memory_text()
    existing_records = [dict(item) for item in store.load_durable_records()]
    pending_candidates = sorted(
        store.load_pending_candidates(),
        key=lambda item: (item["created_at"], item["candidate_id"]),
    )
    pending_candidates = _cluster_candidates(
        pending_candidates,
        float(store.config["retrieval"]["semantic_merge_threshold"]),
    )

    plan = build_plan(
        store,
        run_id=run_id,
        now=now,
        pending_candidates=pending_candidates,
        existing_records=existing_records,
    )
    plan_path = store.write_plan_audit(run_id, plan)
    report = verify_plan(store, run_id=run_id, now=now, plan=plan, existing_records=existing_records)
    report_path = store.write_verifier_report(run_id, report)

    summary = {
        "run_id": run_id,
        "generated_at": now,
        "status": "completed",
        "created": 0,
        "updated": 0,
        "superseded": 0,
        "contested": 0,
        "quarantined": 0,
        "deleted": 0,
        "planner_mode": plan.get("planner_mode", "builtin"),
        "verifier_mode": report.get("verifier_mode", "builtin"),
        "planner_artifact": str(plan_path.relative_to(store.workspace)),
        "verifier_artifact": str(report_path.relative_to(store.workspace)),
        "review_action_count": len(report.get("review_action_ids", [])),
        "blocked_action_count": len(report.get("blocked_action_ids", [])),
    }

    if report.get("commit_verdict") == "block":
        summary["status"] = "blocked"
        summary["reason"] = "verifier-blocked"
        summary["startup_index_entries"] = len(store.load_startup_index().get("entries", []))
        summary["audit"] = store.write_consolidation_audit(run_id, [], summary, before_snapshot)
        return summary

    operations: list[ConsolidationOperation] = []
    processed_candidate_ids = [
        action["payload"]["candidate"]["candidate_id"]
        for action in plan.get("actions", [])
        if isinstance(action.get("payload"), dict) and isinstance(action["payload"].get("candidate"), dict)
    ]

    for action in plan.get("actions", []):
        _apply_action(
            action,
            existing_records=existing_records,
            operations=operations,
            summary=summary,
            run_id=run_id,
            now=now,
        )

    events_by_id = {str(event.get("event_id", "")): event for event in store.load_events()}
    _retype_generic_records_from_source_events(
        existing_records,
        events_by_id=events_by_id,
        operations=operations,
        summary=summary,
        run_id=run_id,
        now=now,
    )

    # Claim verification pass: verify externally checkable claims.
    verification_reports: list[dict[str, Any]] = []
    for record in existing_records:
        if record.get("provenance_tier") == "inferred" and record.get("status") == "active":
            claim_class = record.get("claim_class") or classify_claim(record["body"], title=record["title"])
            if claim_class == "externally_checkable":
                vr = verify_claim(
                    claim_id=record["memory_id"],
                    body=record["body"],
                    title=record["title"],
                    workspace=store.workspace,
                )
                verification_reports.append(vr.to_dict())
                store.write_claim_verification_audit(vr.report_id, vr.to_dict())
                if vr.result == "downgraded":
                    record["provenance_tier"] = "inferred"
                    record["confidence"] = min(record.get("confidence", 0.5), 0.45)
                elif vr.result == "quarantined":
                    record["status"] = "quarantined"
                    _transition_lifecycle(record, status="quarantined", now=now)
                elif vr.result == "verified":
                    record["provenance_tier"] = vr.provenance_tier

    # Build relation edges for supersession and conflict operations.
    relation_store = create_relation_store(store.memory_root)
    for op_obj in operations:
        if op_obj.op == "supersede" and op_obj.payload.get("replacement_id"):
            edge = RelationEdge(
                edge_id=stable_id("edge", op_obj.payload["replacement_id"], op_obj.target_id, "supersedes"),
                from_id=op_obj.payload["replacement_id"],
                to_id=op_obj.target_id,
                kind="supersedes",
                created_at=now,
                reason=op_obj.reason,
            )
            relation_store.add_edge(edge)
        if op_obj.op == "mark_contested":
            for record in existing_records:
                if record["memory_id"] == op_obj.target_id:
                    for conflict_id in record.get("conflicts_with", []):
                        edge = RelationEdge(
                            edge_id=stable_id("edge", op_obj.target_id, conflict_id, "conflicts_with"),
                            from_id=op_obj.target_id,
                            to_id=conflict_id,
                            kind="conflicts_with",
                            created_at=now,
                            reason=op_obj.reason,
                        )
                        relation_store.add_edge(edge)

    for record in existing_records:
        record["type"] = canonical_memory_type(record.get("type"))
        _ensure_lifecycle(record, now=now)

    record_models = [
        MemoryRecord(**{k: v for k, v in record.items() if k in MemoryRecord.__dataclass_fields__})
        for record in existing_records
    ]
    store.save_durable_records(record_models)
    entries = _build_startup_index(existing_records, memory_dir=store.memory_dir_name)
    store.save_startup_index(entries, generated_at=now)
    summary["startup_index_entries"] = len(entries[: int(store.config["index_policy"]["max_entries"])])
    summary["verification_reports"] = len(verification_reports)
    audit = store.write_consolidation_audit(run_id, operations, summary, before_snapshot)
    if processed_candidate_ids:
        store.mark_candidates_processed(processed_candidate_ids)
    summary["audit"] = audit
    return summary


def _apply_action(
    action: dict[str, Any],
    *,
    existing_records: list[dict[str, Any]],
    operations: list[ConsolidationOperation],
    summary: dict[str, Any],
    run_id: str,
    now: str,
) -> None:
    op = str(action["op"])
    payload = action.get("payload", {})
    candidate = payload.get("candidate") if isinstance(payload, dict) else None
    target_id = action.get("target_id")
    reason = str(action.get("reason", ""))
    source_event_ids = list(action.get("source_event_ids", []))

    if op == "ignore":
        return

    if op == "quarantine_candidate":
        _bump(summary, "quarantined")
        operations.append(_make_operation(run_id, "quarantine", str(target_id), reason, source_event_ids, now=now))
        return

    if op == "quarantine_memory":
        record = _find_record(existing_records, str(target_id))
        if record is None or record["status"] != "active":
            return
        record["status"] = "quarantined"
        record["updated_at"] = now
        _transition_lifecycle(record, status="quarantined", now=now)
        _bump(summary, "quarantined")
        operations.append(_make_operation(run_id, "quarantine", record["memory_id"], reason, source_event_ids, now=now))
        return

    if not isinstance(candidate, dict):
        return

    if op == "create":
        new_record = _record_from_candidate(candidate, now=now, run_id=run_id)
        existing_records.append(new_record)
        _bump(summary, "created")
        operations.append(_make_operation(run_id, "create", new_record["memory_id"], reason, source_event_ids, now=now))
        return

    if op == "update":
        record = _find_record(existing_records, str(target_id))
        if record is None:
            return
        record["source_event_ids"] = sorted(set(record["source_event_ids"]) | set(candidate["derived_from_event_ids"]))
        record["conflicts_with"] = sorted(set(record["conflicts_with"]) | set(candidate.get("conflicts_with", [])))
        record["confidence"] = round(max(record["confidence"], candidate["confidence"]), 2)
        record["salience"] = round(max(record["salience"], candidate["salience"]), 2)
        if is_workflow_memory_type(record.get("type")) or is_workflow_memory_type(candidate.get("type")):
            record["type"] = canonical_memory_type(record.get("type"))
            workflow_steps = candidate.get("workflow_steps", [])
            if workflow_steps:
                record["workflow_steps"] = list(dict.fromkeys([*record.get("workflow_steps", []), *workflow_steps]))
        record["updated_at"] = now
        _reinforce_lifecycle(record, now=now)
        _bump(summary, "updated")
        operations.append(_make_operation(run_id, "update", record["memory_id"], reason, source_event_ids, now=now))
        return

    if op == "supersede":
        record = _find_record(existing_records, str(target_id))
        if record is None:
            return
        record["status"] = "superseded"
        record["valid_to"] = now
        record["updated_at"] = now
        _transition_lifecycle(record, status="superseded", now=now)
        replacement = _record_from_candidate(candidate, now=now, run_id=run_id, supersedes=[record["memory_id"]])
        existing_records.append(replacement)
        _bump(summary, "superseded")
        _bump(summary, "created")
        operations.append(
            _make_operation(
                run_id,
                "supersede",
                record["memory_id"],
                reason,
                source_event_ids,
                now=now,
                payload={"replacement_id": replacement["memory_id"]},
            )
        )
        operations.append(
            _make_operation(
                run_id,
                "create",
                replacement["memory_id"],
                "created replacement durable memory",
                source_event_ids,
                now=now,
            )
        )
        return

    if op == "mark_contested":
        record = _find_record(existing_records, str(target_id)) if target_id else None
        if record is not None and record["type"] == "contested_fact":
            record["source_event_ids"] = sorted(
                set(record["source_event_ids"]) | set(candidate["derived_from_event_ids"])
            )
            record["conflicts_with"] = sorted(set(record["conflicts_with"]) | set(candidate.get("conflicts_with", [])))
            record["status"] = "contested"
            record["updated_at"] = now
            _transition_lifecycle(record, status="contested", now=now)
            _bump(summary, "contested")
            operations.append(
                _make_operation(run_id, "mark_contested", record["memory_id"], reason, source_event_ids, now=now)
            )
            return

        conflicts = list(candidate.get("conflicts_with", []))
        if record is not None:
            conflicts = [record["memory_id"], *conflicts]
        contested = _record_from_candidate(
            candidate,
            now=now,
            run_id=run_id,
            status="contested",
            conflicts_with=conflicts,
        )
        existing_records.append(contested)
        _bump(summary, "contested")
        operations.append(
            _make_operation(run_id, "mark_contested", contested["memory_id"], reason, source_event_ids, now=now)
        )


def _find_record(records: list[dict[str, Any]], memory_id: str) -> dict[str, Any] | None:
    for record in records:
        if record["memory_id"] == memory_id:
            return record
    return None
