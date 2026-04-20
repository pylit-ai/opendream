from __future__ import annotations

from typing import Any


def build_semantic_readiness(config: dict[str, Any]) -> dict[str, Any]:
    mode = str(config.get("mode", "deterministic") or "deterministic")
    execution_strategy = str(config.get("execution_strategy", "deterministic") or "deterministic")
    candidate_strategies = [
        str(item)
        for item in config.get("candidate_strategies", [])
        if str(item).strip()
    ]

    if mode == "deterministic":
        return {
            "product_posture": "deterministic-by-choice",
            "semantic_capability_state": "disabled_by_choice",
            "semantic_unavailability_reason": None,
        }

    runnable_non_deterministic = execution_strategy != "deterministic" and execution_strategy in candidate_strategies
    if runnable_non_deterministic:
        return {
            "product_posture": "semantic-first",
            "semantic_capability_state": "ready",
            "semantic_unavailability_reason": None,
        }

    if any(strategy != "deterministic" for strategy in candidate_strategies):
        reason = (
            "Semantic-first posture is configured, but the recommended semantic execution path "
            "has not been applied yet."
        )
        state = "setup_required"
    else:
        reason = (
            "Semantic-first posture is configured, but no runnable semantic execution path "
            "is currently available; deterministic fallback is active."
        )
        state = "degraded"

    return {
        "product_posture": "semantic-first",
        "semantic_capability_state": state,
        "semantic_unavailability_reason": reason,
    }


def empty_memory_quality() -> dict[str, Any]:
    return {
        "status": "unknown",
        "warning_count": 0,
        "warnings": [],
    }


def empty_context_pruning() -> dict[str, Any]:
    return {
        "status": "not_available",
        "profile": None,
        "raw_candidate_count": 0,
        "injected_count": 0,
        "suppressed_count": 0,
    }


SEMANTIC_READ_MODEL_FIELDS = [
    "product_posture",
    "semantic_capability_state",
    "semantic_unavailability_reason",
    "memory_quality",
    "context_pruning",
    "next_action",
]
