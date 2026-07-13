from __future__ import annotations

import hashlib
from typing import Any

from . import __version__
from .storage import MemoryStore
from .util import to_iso, utc_now

CANDIDATE_EXPORT_VERSION = "1"


def _content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _evidence_span(event: dict[str, Any]) -> dict[str, Any]:
    """Return attributable evidence metadata without exporting raw event content."""
    return {
        "event_id": str(event.get("event_id") or ""),
        "session_id": str(event.get("session_id") or ""),
        "turn_id": str(event.get("turn_id") or ""),
        "timestamp": str(event.get("timestamp") or ""),
        "kind": str(event.get("kind") or ""),
        "scope": str(event.get("scope") or ""),
        "source": dict(event.get("source") or {}),
        "reporting_agent": dict(event.get("reporting_agent") or {}),
        "content_sha256": _content_sha256(str(event.get("content") or "")),
    }


def build_candidate_export(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    """Build the stable downstream promotion-candidate contract."""
    generated_at = now or to_iso(utc_now())
    processed = store.load_processed_candidate_ids()
    events_by_id = {
        str(event.get("event_id") or ""): event
        for event in store.load_events()
        if str(event.get("event_id") or "")
    }
    reviews_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for decision in store.load_review_decisions():
        candidate_id = str(decision.get("queue_item_id") or "")
        if candidate_id:
            reviews_by_candidate.setdefault(candidate_id, []).append(decision)
    operations = store.load_consolidation_operations()

    exported_candidates: list[dict[str, Any]] = []
    for candidate in sorted(store.load_candidates(), key=lambda item: str(item.get("candidate_id") or "")):
        candidate_id = str(candidate.get("candidate_id") or "")
        source_ids = [str(item) for item in candidate.get("derived_from_event_ids", [])]
        source_id_set = set(source_ids)
        candidate_operations = [
            operation
            for operation in operations
            if source_id_set.intersection(str(item) for item in operation.get("source_event_ids", []))
        ]
        payload = dict(candidate)
        payload.update(
            {
                "processing_state": "processed" if candidate_id in processed else "pending",
                "evidence_spans": [
                    _evidence_span(events_by_id[event_id])
                    for event_id in source_ids
                    if event_id in events_by_id
                ],
                "missing_source_event_ids": [
                    event_id for event_id in source_ids if event_id not in events_by_id
                ],
                "review_decisions": sorted(
                    reviews_by_candidate.get(candidate_id, []),
                    key=lambda item: (str(item.get("created_at") or ""), str(item.get("id") or "")),
                ),
                "consolidation_operations": sorted(
                    candidate_operations,
                    key=lambda item: (str(item.get("timestamp") or ""), str(item.get("op_id") or "")),
                ),
            }
        )
        exported_candidates.append(payload)

    return {
        "candidate_export_version": CANDIDATE_EXPORT_VERSION,
        "opendream_version": __version__,
        "generated_at": generated_at,
        "workspace": str(store.workspace),
        "candidates": exported_candidates,
    }
