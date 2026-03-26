from __future__ import annotations

import time
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from .models import ConsolidationOperation, MemoryRecord, StartupIndexEntry
from .storage import LockError, MemoryStore
from .util import parse_timestamp, stable_id, summarize, to_iso, utc_now


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


def _record_from_candidate(
    candidate: dict[str, Any],
    *,
    now: str,
    status: str = "active",
    supersedes: list[str] | None = None,
    conflicts_with: list[str] | None = None,
) -> dict[str, Any]:
    candidate_created_at = candidate["created_at"]
    return {
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


def _same_body(existing: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return existing["body"].strip() == candidate["body"].strip()


def _build_startup_index(records: list[dict[str, Any]]) -> list[StartupIndexEntry]:
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
                path=f"memory/topics/{record['memory_id']}.md",
                priority=priority,
            )
        )
    return sorted(entries, key=lambda item: (-item.priority, item.title))


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
            return _consolidate_locked(store, run_id=run_id, now=timestamp)
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
        }


def _consolidate_locked(store: MemoryStore, *, run_id: str, now: str) -> dict[str, Any]:
    before_snapshot = store.snapshot_memory_text()
    existing_records = [dict(item) for item in store.load_durable_records()]
    pending_candidates = sorted(store.load_pending_candidates(), key=lambda item: (item["created_at"], item["candidate_id"]))
    existing_lookup = {(item["scope"], item["type"], item["title"]): item for item in existing_records if item["status"] == "active"}
    workflow_evidence = Counter()
    workflow_events: dict[tuple[str, str], set[str]] = defaultdict(set)
    threshold = int(store.config["promotion"]["workflow_min_successful_recalls"])
    candidate_ttl_days = int(store.config["retention"]["candidate_ttl_days"])
    processed_candidate_ids: list[str] = []
    operations: list[ConsolidationOperation] = []
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
    }

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

    for candidate in pending_candidates:
        processed_candidate_ids.append(candidate["candidate_id"])
        candidate_age = parse_timestamp(now) - parse_timestamp(candidate["created_at"])
        if candidate_age > timedelta(days=candidate_ttl_days):
            summary["quarantined"] += 1
            operations.append(
                _make_operation(
                    run_id,
                    "quarantine",
                    candidate["candidate_id"],
                    "candidate expired before consolidation",
                    candidate["derived_from_event_ids"],
                    now=now,
                )
            )
            continue

        if candidate["confidence"] < 0.45:
            summary["quarantined"] += 1
            operations.append(
                _make_operation(
                    run_id,
                    "quarantine",
                    candidate["candidate_id"],
                    "candidate confidence below promotion threshold",
                    candidate["derived_from_event_ids"],
                    now=now,
                )
            )
            continue

        lookup_key = (candidate["scope"], candidate["type"], candidate["title"])
        existing = existing_lookup.get(lookup_key)

        if candidate["type"] == "procedural_workflow":
            workflow_key = (candidate["scope"], candidate["title"])
            if workflow_evidence[workflow_key] < threshold:
                summary["quarantined"] += 1
                operations.append(
                    _make_operation(
                        run_id,
                        "quarantine",
                        candidate["candidate_id"],
                        "workflow requires repeated successful evidence before promotion",
                        candidate["derived_from_event_ids"],
                        now=now,
                    )
                )
                continue

        if candidate["type"] == "contested_fact":
            if existing:
                existing["source_event_ids"] = sorted(set(existing["source_event_ids"]) | set(candidate["derived_from_event_ids"]))
                existing["conflicts_with"] = sorted(set(existing["conflicts_with"]) | set(candidate.get("conflicts_with", [])))
                existing["status"] = "contested"
                existing["updated_at"] = now
                summary["contested"] += 1
                operations.append(
                    _make_operation(
                        run_id,
                        "mark_contested",
                        existing["memory_id"],
                        "updated contested memory with new evidence",
                        candidate["derived_from_event_ids"],
                        now=now,
                    )
                )
            else:
                record = _record_from_candidate(candidate, now=now, status="contested")
                existing_records.append(record)
                existing_lookup[lookup_key] = record
                summary["contested"] += 1
                operations.append(
                    _make_operation(
                        run_id,
                        "mark_contested",
                        record["memory_id"],
                        "created contested memory from contradiction signal",
                        candidate["derived_from_event_ids"],
                        now=now,
                    )
                )
            continue

        if existing and _same_body(existing, candidate):
            existing["source_event_ids"] = sorted(set(existing["source_event_ids"]) | set(candidate["derived_from_event_ids"]))
            existing["conflicts_with"] = sorted(set(existing["conflicts_with"]) | set(candidate.get("conflicts_with", [])))
            existing["confidence"] = round(max(existing["confidence"], candidate["confidence"]), 2)
            existing["salience"] = round(max(existing["salience"], candidate["salience"]), 2)
            existing["updated_at"] = now
            summary["updated"] += 1
            operations.append(
                _make_operation(
                    run_id,
                    "update",
                    existing["memory_id"],
                    "merged duplicate durable evidence",
                    candidate["derived_from_event_ids"],
                    now=now,
                )
            )
            continue

        if existing and candidate["type"] in SUPERSEDE_TYPES:
            existing["status"] = "superseded"
            existing["valid_to"] = now
            existing["updated_at"] = now
            new_record = _record_from_candidate(candidate, now=now, supersedes=[existing["memory_id"]])
            existing_records.append(new_record)
            existing_lookup[lookup_key] = new_record
            summary["superseded"] += 1
            summary["created"] += 1
            operations.append(
                _make_operation(
                    run_id,
                    "supersede",
                    existing["memory_id"],
                    "superseded by stronger or newer explicit durable memory",
                    candidate["derived_from_event_ids"],
                    now=now,
                    payload={"replacement_id": new_record["memory_id"]},
                )
            )
            operations.append(
                _make_operation(
                    run_id,
                    "create",
                    new_record["memory_id"],
                    "created replacement durable memory",
                    candidate["derived_from_event_ids"],
                    now=now,
                )
            )
            continue

        if existing and candidate["type"] not in SUPERSEDE_TYPES:
            contested = _record_from_candidate(
                candidate,
                now=now,
                status="contested",
                conflicts_with=[existing["memory_id"], *candidate.get("conflicts_with", [])],
            )
            existing_records.append(contested)
            summary["contested"] += 1
            operations.append(
                _make_operation(
                    run_id,
                    "mark_contested",
                    contested["memory_id"],
                    "conflicting evidence kept as contested memory",
                    candidate["derived_from_event_ids"],
                    now=now,
                )
            )
            continue

        new_record = _record_from_candidate(candidate, now=now)
        if candidate["type"] == "procedural_workflow":
            workflow_key = (candidate["scope"], candidate["title"])
            new_record["source_event_ids"] = sorted(workflow_events[workflow_key])
        existing_records.append(new_record)
        existing_lookup[lookup_key] = new_record
        summary["created"] += 1
        operations.append(
            _make_operation(
                run_id,
                "create",
                new_record["memory_id"],
                "created new durable memory",
                candidate["derived_from_event_ids"],
                now=now,
            )
        )

    pending_decay_days = int(store.config["retention"]["pending_item_decay_days"])
    weak_decay_days = int(store.config["retention"]["weak_memory_quarantine_days"])
    now_dt = parse_timestamp(now)
    for record in existing_records:
        if record["status"] != "active":
            continue
        age_days = (now_dt - parse_timestamp(record["updated_at"])).days
        if record["type"] == "pending_item" and age_days > pending_decay_days:
            record["status"] = "deprecated"
            record["updated_at"] = now
            summary["quarantined"] += 1
            operations.append(
                _make_operation(
                    run_id,
                    "quarantine",
                    record["memory_id"],
                    "stale pending item removed from startup index",
                    record["source_event_ids"],
                    now=now,
                )
            )
        elif record["type"] == "semantic_fact" and record["confidence"] < 0.5 and age_days > weak_decay_days:
            record["status"] = "deprecated"
            record["updated_at"] = now
            summary["quarantined"] += 1
            operations.append(
                _make_operation(
                    run_id,
                    "quarantine",
                    record["memory_id"],
                    "stale low-confidence fact quarantined",
                    record["source_event_ids"],
                    now=now,
                )
            )

    record_models = [MemoryRecord(**record) for record in existing_records]
    store.save_durable_records(record_models)
    entries = _build_startup_index(existing_records)
    store.save_startup_index(entries, generated_at=now)
    summary["startup_index_entries"] = len(entries[: int(store.config["index_policy"]["max_entries"])])
    store.write_consolidation_audit(run_id, operations, summary, before_snapshot)
    store.mark_candidates_processed(processed_candidate_ids)
    return summary
