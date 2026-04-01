from __future__ import annotations

import time
from typing import Any

from .claim_verification import classify_claim, verify_claim
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
                and exemplar["type"] == candidate["type"]
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
    status: str = "active",
    supersedes: list[str] | None = None,
    conflicts_with: list[str] | None = None,
) -> dict[str, Any]:
    candidate_created_at = candidate["created_at"]
    record: dict[str, Any] = {
        "memory_id": stable_id("mem", candidate["candidate_id"], now),
        "type": candidate["type"],
        "scope": candidate["scope"],
        "title": candidate["title"],
        "summary": candidate["summary"],
        "body": candidate["body"],
        "status": status,
        "confidence": candidate["confidence"],
        "salience": candidate["salience"],
        "source_event_ids": list(candidate["derived_from_event_ids"]),
        "supersedes": supersedes or [],
        "conflicts_with": conflicts_with or list(candidate.get("conflicts_with", [])),
        "valid_from": candidate_created_at,
        "valid_to": None,
        "access_count": 0,
        "last_accessed_at": None,
        "created_at": candidate_created_at,
        "updated_at": candidate_created_at,
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
        _bump(summary, "quarantined")
        operations.append(_make_operation(run_id, "quarantine", record["memory_id"], reason, source_event_ids, now=now))
        return

    if not isinstance(candidate, dict):
        return

    if op == "create":
        new_record = _record_from_candidate(candidate, now=now)
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
        record["updated_at"] = now
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
        replacement = _record_from_candidate(candidate, now=now, supersedes=[record["memory_id"]])
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
            _bump(summary, "contested")
            operations.append(
                _make_operation(run_id, "mark_contested", record["memory_id"], reason, source_event_ids, now=now)
            )
            return

        conflicts = list(candidate.get("conflicts_with", []))
        if record is not None:
            conflicts = [record["memory_id"], *conflicts]
        contested = _record_from_candidate(candidate, now=now, status="contested", conflicts_with=conflicts)
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
