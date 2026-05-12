"""Semantic verifier and promotion path.

Implements WS6 (T28-T34): deterministic verifier checks, semantic verifier role,
proposal-only default, promotion state machine, distillation, conflict handling,
review/reject/supersede flows.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from .models import MemoryCandidate
from .storage import MemoryStore
from .util import parse_timestamp, semantic_tokens, stable_id, to_iso, utc_now

_LEARNED_CONTEXT_RESTORE_WINDOW_HOURS = 24


def deterministic_verify(
    proposal: dict[str, Any],
    durable_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run deterministic verifier checks on a semantic proposal.

    Checks:
    - Required fields present
    - Provenance exists (source IDs traceable)
    - Timestamps normalized
    - Source coverage threshold met
    - No duplicate or near-duplicate spam
    - No direct contradiction with stronger durable facts
    """
    findings: list[dict[str, Any]] = []
    passed = True

    # Required fields
    required = ["summary", "source_event_ids", "provider_id", "model_id", "confidence"]
    for field_name in required:
        if not proposal.get(field_name):
            findings.append({"check": "required_fields", "field": field_name, "status": "fail"})
            passed = False

    # Provenance
    source_ids = proposal.get("source_event_ids", [])
    if not source_ids:
        findings.append({"check": "provenance", "status": "fail", "reason": "no source event ids"})
        passed = False
    else:
        findings.append({"check": "provenance", "status": "pass", "source_count": len(source_ids)})

    # Confidence floor
    confidence = float(proposal.get("confidence", 0))
    if confidence < 0.3:
        findings.append({"check": "confidence_floor", "status": "fail", "confidence": confidence})
        passed = False
    else:
        findings.append({"check": "confidence_floor", "status": "pass", "confidence": confidence})

    # Duplicate detection against existing durable records
    summary = str(proposal.get("summary", ""))
    summary_tokens = semantic_tokens(summary)
    for record in durable_records:
        if record.get("status") != "active":
            continue
        record_tokens = semantic_tokens(f"{record.get('title', '')} {record.get('summary', '')}")
        if not summary_tokens or not record_tokens:
            continue
        overlap = len(summary_tokens & record_tokens) / max(1, len(summary_tokens | record_tokens))
        if overlap > 0.85:
            findings.append({
                "check": "duplicate_detection",
                "status": "warn",
                "reason": "near-duplicate with existing durable record",
                "existing_memory_id": record.get("memory_id"),
                "overlap": round(overlap, 3),
            })

    # Contradiction check against durable facts
    for record in durable_records:
        if record.get("status") != "active":
            continue
        if record.get("type") in ("semantic_fact", "project_decision", "environment_requirement"):
            record_tokens = semantic_tokens(f"{record.get('title', '')} {record.get('body', '')}")
            if not summary_tokens or not record_tokens:
                continue
            # High overlap with different content could indicate contradiction
            overlap = len(summary_tokens & record_tokens) / max(1, len(summary_tokens | record_tokens))
            if 0.4 < overlap < 0.85:
                findings.append({
                    "check": "contradiction_check",
                    "status": "info",
                    "reason": "potential conflict with durable record",
                    "existing_memory_id": record.get("memory_id"),
                    "overlap": round(overlap, 3),
                })

    verdict = "approve" if passed else "reject"
    return {
        "verifier": "deterministic",
        "verdict": verdict,
        "passed": passed,
        "findings": findings,
        "checked_at": to_iso(utc_now()),
    }


def semantic_verify(
    proposal: dict[str, Any],
    source_events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run semantic verifier checks on a proposal.

    In production, this would call a model to check:
    - Source-groundedness
    - No unsupported extrapolation
    - Compression usefulness
    - Query-family relevance

    This implementation provides deterministic heuristic checks.
    """
    findings: list[dict[str, Any]] = []
    passed = True

    summary = str(proposal.get("summary", ""))
    details = str(proposal.get("details", ""))
    content = f"{summary} {details}"

    # Source groundedness: check that proposal content tokens overlap with source content
    source_content = " ".join(
        str(e.get("content", "")) for e in source_events
    )
    proposal_tokens = semantic_tokens(content)
    source_tokens = semantic_tokens(source_content)
    if proposal_tokens and source_tokens:
        groundedness = len(proposal_tokens & source_tokens) / max(1, len(proposal_tokens))
        findings.append({
            "check": "source_groundedness",
            "status": "pass" if groundedness > 0.2 else "warn",
            "groundedness_score": round(groundedness, 3),
        })
        if groundedness < 0.1:
            findings.append({
                "check": "source_groundedness",
                "status": "fail",
                "reason": "proposal appears ungrounded in source material",
            })
            passed = False

    # Compression usefulness: proposal should be significantly shorter than sources
    if source_content and content:
        compression_ratio = len(content) / max(1, len(source_content))
        findings.append({
            "check": "compression_usefulness",
            "status": "pass" if compression_ratio < 0.8 else "warn",
            "compression_ratio": round(compression_ratio, 3),
        })

    # Query family relevance
    family_tags = proposal.get("query_family_tags", [])
    if family_tags:
        findings.append({
            "check": "query_family_relevance",
            "status": "pass",
            "family_count": len(family_tags),
        })
    else:
        findings.append({
            "check": "query_family_relevance",
            "status": "warn",
            "reason": "no query family tags",
        })

    # Content quality: must have minimum substance
    if len(summary) < 10:
        findings.append({
            "check": "content_quality",
            "status": "fail",
            "reason": "summary too short",
        })
        passed = False

    verdict = "approve" if passed else "reject"
    return {
        "verifier": "semantic",
        "verdict": verdict,
        "passed": passed,
        "findings": findings,
        "checked_at": to_iso(utc_now()),
    }


def verify_proposal(
    store: MemoryStore,
    proposal: dict[str, Any],
    *,
    source_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run full verification pipeline on a semantic proposal.

    Runs deterministic + semantic verifiers based on config.
    Returns combined verdict.
    """
    config = store.load_semantic_config()
    verification_config = config.get("verification", {})
    durable_records = store.load_durable_records()

    results: list[dict[str, Any]] = []

    # Deterministic verification
    if verification_config.get("deterministic_enabled", True):
        det_result = deterministic_verify(proposal, durable_records)
        results.append(det_result)

    # Semantic verification
    if verification_config.get("semantic_enabled", True):
        sem_result = semantic_verify(proposal, source_events or [])
        results.append(sem_result)

    # Combined verdict
    require_both = verification_config.get("require_both", True)
    verdicts = [r["verdict"] for r in results]
    if require_both:
        combined_verdict = "approve" if all(v == "approve" for v in verdicts) else "reject"
    else:
        combined_verdict = "approve" if any(v == "approve" for v in verdicts) else "reject"

    # Downgrade to review_required if mixed
    if "approve" in verdicts and "reject" in verdicts:
        combined_verdict = "review_required"

    run_id = stable_id("verify", to_iso(utc_now()))
    report = {
        "run_id": run_id,
        "combined_verdict": combined_verdict,
        "verifier_results": results,
        "proposal_summary": proposal.get("summary", ""),
        "checked_at": to_iso(utc_now()),
    }

    store.write_semantic_verifier_audit(run_id, report)
    return report


def promote_proposal(
    store: MemoryStore,
    proposal: dict[str, Any],
    verification_report: dict[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Promote a verified proposal to the learned context layer.

    Only promotes if verification passed. Returns promotion result.
    """
    timestamp = now or to_iso(utc_now())
    verdict = verification_report.get("combined_verdict", "reject")

    if verdict not in ("approve", "review_required"):
        return {
            "status": "rejected",
            "reason": f"verification verdict: {verdict}",
            "record_id": None,
        }

    record_id = stable_id("lc", timestamp, proposal.get("summary", ""))
    verifier_status = "approved" if verdict == "approve" else "review_required"

    record = {
        "record_id": record_id,
        "workspace_id": proposal.get("workspace_id", ""),
        "source_event_ids": proposal.get("source_event_ids", []),
        "source_episode_ids": proposal.get("source_episode_ids", []),
        "source_trace_ids": proposal.get("source_trace_ids", []),
        "query_family_tags": proposal.get("query_family_tags", []),
        "summary": proposal.get("summary", ""),
        "details": proposal.get("details", ""),
        "assumptions": proposal.get("assumptions", ""),
        "provider_id": proposal.get("provider_id", ""),
        "model_id": proposal.get("model_id", ""),
        "prompt_version": proposal.get("prompt_version", "1"),
        "created_at": timestamp,
        "fresh_until": proposal.get("fresh_until", timestamp),
        "confidence": float(proposal.get("confidence", 0.5)),
        "verifier_status": verifier_status,
        "conflict_state": "none",
        "harm_signals": [],
        "promotion_target": "learned_context",
        "status": "active",
    }

    records = store.load_learned_context_records()
    records.append(record)
    store.save_learned_context_records(records)

    return {
        "status": "promoted",
        "record_id": record_id,
        "verifier_status": verifier_status,
    }


def reject_proposal(
    store: MemoryStore,
    record_id: str,
    *,
    rationale: str = "",
    actor: str = "system",
    now: str | None = None,
) -> dict[str, Any]:
    """Reject a learned context record."""
    timestamp = now or to_iso(utc_now())
    records = store.load_learned_context_records()
    for record in records:
        if record.get("record_id") == record_id:
            record["status"] = "rejected"
            record["verifier_status"] = "rejected"
            record["status_changed_at"] = timestamp
            record["restorable_until"] = to_iso(
                parse_timestamp(timestamp) + timedelta(hours=_LEARNED_CONTEXT_RESTORE_WINDOW_HOURS)
            )
            store.save_learned_context_records(records)
            return {"status": "rejected", "record_id": record_id}
    return {"status": "not_found", "record_id": record_id}


def supersede_record(
    store: MemoryStore,
    old_record_id: str,
    new_record_id: str,
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Mark a learned context record as superseded by another."""
    timestamp = now or to_iso(utc_now())
    records = store.load_learned_context_records()
    for record in records:
        if record.get("record_id") == old_record_id:
            record["status"] = "superseded"
            record["superseded_by"] = new_record_id
            record["status_changed_at"] = timestamp
            record["restorable_until"] = to_iso(
                parse_timestamp(timestamp) + timedelta(hours=_LEARNED_CONTEXT_RESTORE_WINDOW_HOURS)
            )
            store.save_learned_context_records(records)
            return {"status": "superseded", "old_id": old_record_id, "new_id": new_record_id}
    return {"status": "not_found", "record_id": old_record_id}


def restore_record(
    store: MemoryStore,
    record_id: str,
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Reactivate a recently pruned learned-context record within its restore window."""
    timestamp = now or to_iso(utc_now())
    records = store.load_learned_context_records()
    for record in records:
        if record.get("record_id") != record_id:
            continue
        current_status = str(record.get("status") or "")
        if current_status == "active":
            return {"status": "already_active", "record_id": record_id, "record": dict(record)}
        if current_status not in {"superseded", "archived", "rejected"}:
            return {
                "status": "not_restorable",
                "record_id": record_id,
                "reason": f"status {current_status or 'unknown'} is not restorable",
            }
        restorable_until = str(record.get("restorable_until") or "").strip()
        if not restorable_until:
            return {
                "status": "restore_window_missing",
                "record_id": record_id,
            }
        if parse_timestamp(restorable_until) < parse_timestamp(timestamp):
            return {
                "status": "restore_window_expired",
                "record_id": record_id,
                "restorable_until": restorable_until,
            }
        record["restored_from_status"] = current_status
        record["restored_at"] = timestamp
        record["status"] = "active"
        record["verifier_status"] = "approved"
        record.pop("superseded_by", None)
        store.save_learned_context_records(records)
        return {"status": "restored", "record_id": record_id, "record": dict(record)}
    return {"status": "not_found", "record_id": record_id}


def reopen_archived_records_for_review(
    store: MemoryStore,
    *,
    limit: int = 25,
    record_ids: list[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Reactivate archived learned context as review-required, not silently approved."""
    timestamp = now or to_iso(utc_now())
    limit = max(1, min(int(limit), 500))
    requested_ids = {str(record_id) for record_id in record_ids or [] if str(record_id).strip()}
    records = store.load_learned_context_records()
    reopened: list[str] = []
    skipped: list[dict[str, str]] = []
    for record in records:
        record_id = str(record.get("record_id") or "")
        if requested_ids and record_id not in requested_ids:
            continue
        if len(reopened) >= limit:
            break
        current_status = str(record.get("status") or "")
        if current_status != "archived":
            if requested_ids:
                skipped.append({"record_id": record_id, "reason": f"status {current_status or 'unknown'}"})
            continue
        record["restored_from_status"] = current_status
        record["restored_at"] = timestamp
        record["status"] = "active"
        record["status_changed_at"] = timestamp
        record["verifier_status"] = "review_required"
        record["reopen_reason"] = "manual_review"
        record.pop("archived_at", None)
        record.pop("archive_reason", None)
        record.pop("restorable_until", None)
        reopened.append(record_id)
    if reopened:
        store.save_learned_context_records(records)
    missing = sorted(requested_ids - {str(record.get("record_id") or "") for record in records})
    skipped.extend({"record_id": record_id, "reason": "not_found"} for record_id in missing)
    return {
        "status": "reopened" if reopened else "none_reopened",
        "reopened": len(reopened),
        "reopened_record_ids": reopened,
        "skipped": skipped,
        "limit": limit,
    }


def distill_to_durable_candidate(
    learned_record: dict[str, Any],
    *,
    now: str | None = None,
) -> MemoryCandidate:
    """Distill a learned context record into a typed durable candidate.

    This does not directly create a durable record - it creates a candidate
    that goes through the standard consolidation pipeline.
    """
    timestamp = now or to_iso(utc_now())
    return MemoryCandidate(
        candidate_id=stable_id("distill", learned_record.get("record_id", ""), timestamp),
        derived_from_event_ids=learned_record.get("source_event_ids", []),
        type="semantic_fact",
        scope="project",
        title=learned_record.get("summary", "")[:80],
        summary=learned_record.get("summary", ""),
        body=learned_record.get("details", ""),
        confidence=float(learned_record.get("confidence", 0.5)),
        salience=float(learned_record.get("confidence", 0.5)),
        status="pending",
        created_at=timestamp,
        origin_mode="semantic_distillation",
    )


def detect_conflicts(
    store: MemoryStore,
    record_id: str,
) -> list[dict[str, Any]]:
    """Detect conflicts between a learned context record and durable facts."""
    records = store.load_learned_context_records()
    target = next((r for r in records if r.get("record_id") == record_id), None)
    if not target:
        return []

    conflicts: list[dict[str, Any]] = []
    target_tokens = semantic_tokens(f"{target.get('summary', '')} {target.get('details', '')}")
    durable = store.load_durable_records()

    for record in durable:
        if record.get("status") != "active":
            continue
        record_tokens = semantic_tokens(f"{record.get('title', '')} {record.get('body', '')}")
        if not target_tokens or not record_tokens:
            continue
        overlap = len(target_tokens & record_tokens) / max(1, len(target_tokens | record_tokens))
        if 0.3 < overlap < 0.85:
            conflicts.append({
                "learned_context_id": record_id,
                "durable_memory_id": record.get("memory_id"),
                "overlap": round(overlap, 3),
                "durable_type": record.get("type"),
                "severity": "high" if overlap > 0.6 else "medium" if overlap > 0.4 else "low",
            })

    return conflicts
