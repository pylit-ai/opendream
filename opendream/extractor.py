from __future__ import annotations

import re
from typing import Any

from .models import MemoryCandidate
from .util import STOPWORDS, first_tag, parse_tags, semantic_tokens, stable_id, summarize, to_iso, tokenize, utc_now

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

_STEP_RE = re.compile(r"^\s*(?:\d+[.)]\s+|[-*]\s+)(.+)", re.MULTILINE)


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
    if kind in {"debug_outcome", "tool_failure"} and (
        "anti-pattern" in content or "avoid" in content or "anti-pattern" in tags
    ):
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


def _information_density(text: str) -> float:
    """Ratio of non-stopword tokens to total tokens. Higher = denser content."""
    all_tokens = tokenize(text)
    if not all_tokens:
        return 0.0
    content_tokens = all_tokens - STOPWORDS
    return len(content_tokens) / len(all_tokens)


def _novelty_score(body: str, existing_records: list[dict[str, Any]]) -> float:
    """Score 0..1 where 1 means completely novel vs existing durable records."""
    if not existing_records:
        return 1.0
    candidate_tokens = semantic_tokens(body)
    if not candidate_tokens:
        return 0.0
    max_similarity = 0.0
    for record in existing_records:
        record_text = " ".join([record.get("title", ""), record.get("summary", ""), record.get("body", "")])
        record_tokens = semantic_tokens(record_text)
        if not record_tokens:
            continue
        similarity = len(candidate_tokens & record_tokens) / len(candidate_tokens | record_tokens)
        if similarity > max_similarity:
            max_similarity = similarity
    return round(1.0 - max_similarity, 4)


def _body_length_penalty(body: str) -> float:
    """Penalize very short bodies that are unlikely to carry useful information."""
    word_count = len(body.split())
    if word_count <= 3:
        return 0.0
    if word_count <= 6:
        return 0.3
    if word_count <= 10:
        return 0.6
    return 1.0


def score_salience(
    body: str,
    candidate_type: str,
    existing_records: list[dict[str, Any]],
) -> float:
    """Compute salience from novelty, information density, type prior, and body length."""
    novelty = _novelty_score(body, existing_records)
    density = _information_density(body)
    type_prior = TYPE_CONFIDENCE.get(candidate_type, 0.5)
    length_factor = _body_length_penalty(body)
    raw = (novelty * 0.3 + density * 0.2 + type_prior * 0.2 + length_factor * 0.3)
    return round(max(0.1, min(1.0, raw)), 2)


def parse_workflow_steps(body: str) -> list[str]:
    """Extract numbered or bulleted steps from a body text."""
    return [match.group(1).strip() for match in _STEP_RE.finditer(body) if match.group(1).strip()]


def extract_candidate(
    event: dict[str, Any],
    *,
    origin_mode: str,
    now: str | None = None,
    existing_records: list[dict[str, Any]] | None = None,
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

    body = event["content"].strip()
    salience = score_salience(body, candidate_type, existing_records or [])
    summary = summarize(body, 140)
    created_at = now or to_iso(utc_now())
    candidate_id = stable_id("cand", event["event_id"], candidate_type, title, body)
    conflicts_with = tags.get("conflict", [])

    workflow_steps: list[str] = []
    if candidate_type == "procedural_workflow":
        workflow_steps = parse_workflow_steps(body)

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
        workflow_steps=workflow_steps,
    )


def filter_by_salience(
    candidates: list[MemoryCandidate],
    min_salience: dict[str, float],
) -> list[MemoryCandidate]:
    """Remove candidates below per-kind salience thresholds."""
    result: list[MemoryCandidate] = []
    for candidate in candidates:
        threshold = min_salience.get(candidate.type, 0.0)
        if candidate.salience >= threshold:
            result.append(candidate)
    return result


def extract_candidates(
    events: list[dict[str, Any]],
    *,
    origin_mode: str,
    now: str | None = None,
    existing_records: list[dict[str, Any]] | None = None,
) -> list[MemoryCandidate]:
    candidates: list[MemoryCandidate] = []
    for event in events:
        candidate = extract_candidate(
            event,
            origin_mode=origin_mode,
            now=now,
            existing_records=existing_records,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates
