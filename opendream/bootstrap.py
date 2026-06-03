from __future__ import annotations

from collections import defaultdict
from typing import Any

from .extractor import classify_event, extract_candidates
from .storage import MemoryStore
from .util import stable_id, to_iso, utc_now


def bootstrap_index(
    store: MemoryStore,
    events: list[dict[str, Any]],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    created_at = now or to_iso(utc_now())
    candidates = extract_candidates(events, origin_mode="bootstrap", now=created_at)
    accepted = [candidate for candidate in candidates if candidate.confidence >= 0.45]
    quarantined = [candidate for candidate in candidates if candidate.confidence < 0.45]

    accepted_by_id = {candidate.candidate_id for candidate in accepted}
    categories: dict[str, list[str]] = defaultdict(list)
    for candidate in accepted:
        categories[candidate.type].append(candidate.candidate_id)

    raw_only_ids: list[str] = []
    for event in events:
        candidate_type = classify_event(event)
        if candidate_type is None:
            raw_only_ids.append(event["event_id"])

    report = {
        "run_id": stable_id("bootstrap", created_at, len(events)),
        "generated_at": created_at,
        "categories": [
            {
                "name": name,
                "description": f"Bootstrap candidates for {name.replace('_', ' ')}",
                "candidate_ids": sorted(candidate_ids),
            }
            for name, candidate_ids in sorted(categories.items())
        ],
        "candidates": [candidate.to_dict() for candidate in accepted],
        "raw_only_ids": sorted(raw_only_ids),
        "quarantine_ids": sorted(
            candidate.candidate_id
            for candidate in quarantined
            if candidate.candidate_id not in accepted_by_id
        ),
    }

    store.write_bootstrap_report(str(report["run_id"]), report)
    if accepted:
        store.append_candidates(accepted, str(report["run_id"]))
    return report
