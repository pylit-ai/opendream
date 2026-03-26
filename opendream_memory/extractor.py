from __future__ import annotations

from typing import Any

from .models import MemoryCandidate
from .util import first_tag, parse_tags, stable_id, summarize, to_iso, utc_now


TYPE_CONFIDENCE = {
    "user_preference": 0.8,
    "project_decision": 0.9,
    "environment_requirement": 0.85,
    "procedural_workflow": 0.7,
    "anti_pattern": 0.75,
    "pending_item": 0.6,
    "contested_fact": 0.55,
    "semantic_fact": 0.5,
}


def classify_event(event: dict[str, Any]) -> str | None:
    kind = event["kind"]
    content = event["content"].lower()
    tags = parse_tags(event.get("tags"))

    if event.get("sensitivity") in {"secret", "sensitive", "do_not_store"}:
        return None

    if kind in {"remember_request", "preference_signal"}:
        return "user_preference"
    if kind == "project_decision":
        return "project_decision"
    if kind == "environment_requirement":
        return "environment_requirement"
    if kind in {"user_correction", "contradiction_signal"}:
        return "contested_fact"
    if kind == "pending_item":
        return "pending_item"
    if kind in {"workflow_step", "task_outcome"} and "workflow" in tags:
        return "procedural_workflow"
    if kind in {"debug_outcome", "tool_failure"} and ("anti-pattern" in content or "avoid" in content or "anti-pattern" in tags):
        return "anti_pattern"
    if kind in {"debug_outcome", "task_outcome", "tool_failure"}:
        return "semantic_fact"
    return None


def build_title(event: dict[str, Any], candidate_type: str) -> str:
    key = first_tag(event.get("tags"), "key") or first_tag(event.get("tags"), "workflow")
    if not key:
        key = summarize(event["content"], 48).replace(" ", "-").lower()

    prefixes = {
        "user_preference": "Preference",
        "project_decision": "Decision",
        "environment_requirement": "Environment",
        "procedural_workflow": "Workflow",
        "anti_pattern": "Anti-pattern",
        "pending_item": "Pending",
        "contested_fact": "Contested",
        "semantic_fact": "Fact",
    }
    return f"{prefixes[candidate_type]}: {key}"


def extract_candidate(
    event: dict[str, Any],
    *,
    origin_mode: str,
    now: str | None = None,
) -> MemoryCandidate | None:
    candidate_type = classify_event(event)
    if candidate_type is None:
        return None

    title = build_title(event, candidate_type)
    confidence = event.get("confidence_hint")
    if confidence is None:
        confidence = TYPE_CONFIDENCE[candidate_type]

    tags = parse_tags(event.get("tags"))
    if candidate_type == "procedural_workflow" and "success" not in tags:
        confidence = min(confidence, 0.4)

    salience = round(min(1.0, confidence + 0.1), 2)
    body = event["content"].strip()
    summary = summarize(body, 140)
    created_at = now or to_iso(utc_now())
    candidate_id = stable_id("cand", event["event_id"], candidate_type, title, body)
    conflicts_with = tags.get("conflict", [])

    return MemoryCandidate(
        candidate_id=candidate_id,
        derived_from_event_ids=[event["event_id"]],
        type=candidate_type,
        scope=event["scope"],
        title=title,
        summary=summary,
        body=body,
        confidence=round(float(confidence), 2),
        salience=salience,
        status="new",
        created_at=created_at,
        origin_mode=origin_mode,
        retrieval_boost=0.0,
        memory_refs=[],
        conflicts_with=conflicts_with,
    )


def extract_candidates(
    events: list[dict[str, Any]],
    *,
    origin_mode: str,
    now: str | None = None,
) -> list[MemoryCandidate]:
    candidates: list[MemoryCandidate] = []
    for event in events:
        candidate = extract_candidate(event, origin_mode=origin_mode, now=now)
        if candidate is not None:
            candidates.append(candidate)
    return candidates
