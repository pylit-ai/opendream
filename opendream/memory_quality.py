from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from .provider_registry import semantic_mode_available
from .storage import MemoryStore
from .util import parse_timestamp, to_iso, utc_now

LOW_SIGNAL_TYPES = frozenset({"semantic_fact", "pending_item"})
EPHEMERA_TERMS = (
    "waiting",
    "running",
    "queued",
    "pending",
    "in progress",
    "wip",
)
HOMOGENEOUS_SHARE_THRESHOLD = 0.8
EPHEMERA_RATIO_THRESHOLD = 0.6
DEFAULT_OBSERVATION_WINDOW_DAYS = 14
MIN_RECORDS_FOR_TYPE_WARNING = 5


def analyze_memory_quality(
    store: MemoryStore,
    *,
    now: str | None = None,
    observation_window_days: int = DEFAULT_OBSERVATION_WINDOW_DAYS,
) -> dict[str, Any]:
    """Assess semantic readiness and memory-quality warnings for a workspace."""
    timestamp = now or to_iso(utc_now())
    return assess_memory_quality_snapshot(
        semantic_config=store.load_semantic_config(),
        providers=store.load_provider_registry(),
        durable_records=store.load_durable_records(),
        learned_context_records=store.load_learned_context_records(),
        semantic_availability=semantic_mode_available(store),
        now=timestamp,
        observation_window_days=observation_window_days,
    )


def assess_memory_quality_snapshot(
    *,
    semantic_config: dict[str, Any],
    providers: list[dict[str, Any]],
    durable_records: list[dict[str, Any]],
    learned_context_records: list[dict[str, Any]],
    semantic_availability: dict[str, Any] | None = None,
    now: str | None = None,
    observation_window_days: int = DEFAULT_OBSERVATION_WINDOW_DAYS,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    active_records = [record for record in durable_records if record.get("status") == "active"]
    recent_records = _recent_records(
        active_records,
        now=timestamp,
        observation_window_days=observation_window_days,
    )
    active_learned_context = [
        record for record in learned_context_records if record.get("status") == "active"
    ]

    product_posture = _product_posture(semantic_config)
    availability = semantic_availability or _availability_from_snapshot(semantic_config, providers)
    capability_state, unavailable_reason = _semantic_capability_state(
        semantic_config,
        availability,
    )

    warnings: list[dict[str, Any]] = []
    if capability_state == "degraded":
        warnings.append(
            _warning(
                "semantic_unavailable",
                "warning",
                unavailable_reason or "semantic capability is unavailable",
                "Configure a semantic provider or delegated adapter so semantic-first can actually run.",
                {"provider_count": len(providers)},
            )
        )

    type_counter = Counter(str(record.get("type", "")) for record in recent_records)
    dominant_type = ""
    dominant_type_count = 0
    if type_counter:
        dominant_type, dominant_type_count = type_counter.most_common(1)[0]
    dominant_type_share = dominant_type_count / len(recent_records) if recent_records else 0.0
    if (
        len(recent_records) >= MIN_RECORDS_FOR_TYPE_WARNING
        and dominant_type in LOW_SIGNAL_TYPES
        and dominant_type_share >= HOMOGENEOUS_SHARE_THRESHOLD
    ):
        warnings.append(
            _warning(
                "homogeneous_type_mix",
                "warning",
                f"recent durable memory is dominated by {dominant_type}",
                "Promote more typed durable memory and reduce generic semantic_fact promotions.",
                {
                    "dominant_type": dominant_type,
                    "dominant_type_share": round(dominant_type_share, 3),
                    "recent_record_count": len(recent_records),
                },
            )
        )

    ephemera_count = sum(1 for record in recent_records if _is_ephemeral(record))
    ephemera_ratio = ephemera_count / len(recent_records) if recent_records else 0.0
    if recent_records and ephemera_ratio >= EPHEMERA_RATIO_THRESHOLD:
        warnings.append(
            _warning(
                "ephemera_heavy",
                "warning",
                "recent promoted memory is heavy on waiting/running-style summaries",
                "Tighten pruning or promotion rules so transient execution state stays suppressed.",
                {
                    "ephemera_ratio": round(ephemera_ratio, 3),
                    "ephemera_count": ephemera_count,
                    "recent_record_count": len(recent_records),
                },
            )
        )

    if (
        product_posture == "semantic_first"
        and not active_learned_context
        and recent_records
    ):
        warnings.append(
            _warning(
                "missing_learned_context_activity",
                "warning",
                "semantic-first workspace has no active learned-context records in the observation window",
                "Run or repair the semantic path so repeated-task learning starts materializing.",
                {
                    "active_learned_context_count": 0,
                    "observation_window_days": observation_window_days,
                    "recent_record_count": len(recent_records),
                },
            )
        )

    memory_quality_state = "healthy" if not warnings else "warning"
    return {
        "product_posture": product_posture,
        "semantic_capability_state": capability_state,
        "semantic_unavailability_reason": unavailable_reason,
        "active_execution_strategy": semantic_config.get("execution_strategy", "deterministic"),
        "learned_context_count": len(active_learned_context),
        "next_action": _next_action(capability_state, unavailable_reason, availability),
        "memory_quality": {
            "state": memory_quality_state,
            "warnings": warnings,
            "metrics": {
                "provider_count": len(providers),
                "recent_record_count": len(recent_records),
                "active_learned_context_count": len(active_learned_context),
                "dominant_type": dominant_type or None,
                "dominant_type_share": round(dominant_type_share, 3),
                "ephemera_ratio": round(ephemera_ratio, 3),
            },
        },
    }


def _availability_from_snapshot(
    semantic_config: dict[str, Any],
    providers: list[dict[str, Any]],
) -> dict[str, Any]:
    mode = str(semantic_config.get("mode", "deterministic"))
    if mode == "deterministic":
        return {"available": False, "mode": mode, "reason": "mode is deterministic"}
    if not providers:
        return {"available": False, "mode": mode, "reason": "no providers registered"}
    available_roles: set[str] = set()
    for provider in providers:
        if provider.get("health_status") in {"healthy", "degraded"}:
            available_roles.update(str(role) for role in provider.get("roles", []))
    missing_roles = {"synthesis", "verification"} - available_roles
    if missing_roles:
        return {
            "available": False,
            "mode": mode,
            "reason": f"missing provider roles: {', '.join(sorted(missing_roles))}",
        }
    return {"available": True, "mode": mode}


def _product_posture(semantic_config: dict[str, Any]) -> str:
    mode = str(semantic_config.get("mode", "deterministic"))
    return "deterministic_only" if mode == "deterministic" else "semantic_first"


def _semantic_capability_state(
    semantic_config: dict[str, Any],
    availability: dict[str, Any],
) -> tuple[str, str | None]:
    if _product_posture(semantic_config) == "deterministic_only":
        return "disabled_by_choice", None
    explicit_state = availability.get("semantic_capability_state")
    if isinstance(explicit_state, str) and explicit_state:
        if explicit_state == "ready":
            return "ready", None
        return explicit_state, str(availability.get("reason", "semantic capability unavailable"))
    if availability.get("available"):
        return "ready", None
    return "degraded", str(availability.get("reason", "semantic capability unavailable"))


def _next_action(
    capability_state: str,
    unavailable_reason: str | None,
    availability: dict[str, Any] | None = None,
) -> str:
    if availability and isinstance(availability.get("next_action"), str):
        return str(availability["next_action"])
    if capability_state == "ready":
        return "none"
    if capability_state == "disabled_by_choice":
        return "re-enable semantic mode when you want semantic memory value"
    if unavailable_reason and "provider" in unavailable_reason:
        return "configure a semantic provider or delegated adapter"
    return "repair the semantic path and re-run setup"


def _recent_records(
    records: list[dict[str, Any]],
    *,
    now: str,
    observation_window_days: int,
) -> list[dict[str, Any]]:
    cutoff = parse_timestamp(now) - timedelta(days=observation_window_days)
    recent: list[dict[str, Any]] = []
    for record in records:
        seen_at = str(record.get("updated_at") or record.get("created_at") or "")
        if not seen_at:
            continue
        try:
            if parse_timestamp(seen_at) >= cutoff:
                recent.append(record)
        except ValueError:
            continue
    return recent


def _is_ephemeral(record: dict[str, Any]) -> bool:
    haystack = " ".join(
        [
            str(record.get("title", "")),
            str(record.get("summary", "")),
            str(record.get("body", "")),
        ]
    ).lower()
    return any(term in haystack for term in EPHEMERA_TERMS)


def _warning(
    code: str,
    severity: str,
    message: str,
    remediation: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "remediation": remediation,
        "evidence": evidence,
    }
