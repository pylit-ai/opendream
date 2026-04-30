from __future__ import annotations

from statistics import median
from typing import Any, cast

IDLE_REASONS = frozenset({"no-episodes", "insufficient-signal"})
SIGNAL_BUCKET_SIZE = 10
MIN_DURATION_BASELINE = 3


def score_dream_change_points(
    cycles: list[dict[str, Any]],
    *,
    newest_first: bool = True,
) -> list[dict[str, Any]]:
    """Return cycles annotated with deterministic change-point metadata."""
    chronological = list(reversed(cycles)) if newest_first else list(cycles)
    scored: list[dict[str, Any]] = []
    for cycle in chronological:
        row = dict(cycle)
        row["change_point"] = _score_cycle(row, scored)
        scored.append(row)
    return list(reversed(scored)) if newest_first else scored


def _score_cycle(cycle: dict[str, Any], previous: list[dict[str, Any]]) -> dict[str, Any]:
    signature = effect_signature(cycle)
    contributors: list[dict[str, Any]] = []

    if _is_idle_skip(cycle):
        return _change_point(
            score=0,
            severity="low",
            kind="noop",
            label="Idle cycle: no new signal was available.",
            contributors=[],
            signature=signature,
            is_noop=True,
        )

    failure = _failure_reason(cycle)
    if failure:
        contributors.append({"key": "reason", "value": failure, "weight": 75})
        return _change_point(
            score=75,
            severity="high",
            kind="failure",
            label=f"Dream failed or skipped unexpectedly: {failure}.",
            contributors=contributors,
            signature=signature,
            is_noop=False,
        )

    material = _material_contributors(cycle)
    if material:
        score = min(95, 80 + sum(int(item["value"]) for item in material if isinstance(item.get("value"), int)) * 3)
        return _change_point(
            score=score,
            severity="high",
            kind="material",
            label=_material_label(material),
            contributors=material,
            signature=signature,
            is_noop=False,
        )

    drift = _drift_contributors(cycle, previous)
    if drift:
        return _change_point(
            score=45,
            severity="medium",
            kind="drift",
            label=_drift_label(drift),
            contributors=drift,
            signature=signature,
            is_noop=False,
        )

    anomaly = _duration_anomaly_contributor(cycle, previous)
    if anomaly:
        return _change_point(
            score=60,
            severity="medium",
            kind="duration_anomaly",
            label=f"{anomaly['phase']} {anomaly['ratio']}x baseline.",
            contributors=[anomaly],
            signature=signature,
            is_noop=False,
        )

    return _change_point(
        score=0,
        severity="low",
        kind="noop",
        label="No observable dream effect.",
        contributors=[],
        signature=signature,
        is_noop=True,
    )


def effect_signature(cycle: dict[str, Any]) -> str:
    return "|".join(
        [
            str(cycle.get("mode") or cycle.get("type") or "dream"),
            str(cycle.get("status") or "").lower(),
            str(cycle.get("reason") or ""),
            _signal_bucket(_int(cycle.get("signal_row_count"))),
            ">".join(str(item) for item in cycle.get("phases", []) if item),
            str(cycle.get("model_id") or ""),
        ]
    )


def _change_point(
    *,
    score: int,
    severity: str,
    kind: str,
    label: str,
    contributors: list[dict[str, Any]],
    signature: str,
    is_noop: bool,
) -> dict[str, Any]:
    return {
        "score": score,
        "severity": severity,
        "kind": kind,
        "label": label,
        "contributors": contributors,
        "signature": signature,
        "is_noop": is_noop,
    }


def _failure_reason(cycle: dict[str, Any]) -> str:
    status = str(cycle.get("status") or "").lower()
    reason = str(cycle.get("reason") or "")
    if status in {"failed", "error"}:
        return reason or status
    if status == "skipped" and reason not in IDLE_REASONS:
        return reason or "skipped"
    return ""


def _is_idle_skip(cycle: dict[str, Any]) -> bool:
    return str(cycle.get("status") or "").lower() == "skipped" and str(cycle.get("reason") or "") in IDLE_REASONS


def _material_contributors(cycle: dict[str, Any]) -> list[dict[str, Any]]:
    funnel = _dict(cycle.get("funnel"))
    summary = _dict(cycle.get("summary"))
    contributors: list[dict[str, Any]] = []
    for key in ("generated", "approved", "created"):
        value = _int(funnel.get(key))
        if value > 0:
            contributors.append({"key": key, "value": value, "weight": 80})
    for key in ("learned_context_superseded", "proposals_rejected"):
        value = _int(cycle.get(key) or summary.get(key))
        if value > 0:
            contributors.append({"key": key, "value": value, "weight": 80})
    appended = _int(cycle.get("appended_events") or summary.get("appended_events") or summary.get("staged_events"))
    if appended > 0:
        contributors.append({"key": "appended_events", "value": appended, "weight": 80})
    return contributors


def _material_label(contributors: list[dict[str, Any]]) -> str:
    phrases: list[str] = []
    for item in contributors:
        key = str(item.get("key"))
        value = _int(item.get("value"))
        if key == "generated":
            phrases.append(f"generated {value} proposal{'' if value == 1 else 's'}")
        elif key == "approved":
            phrases.append(f"approved {value} proposal{'' if value == 1 else 's'}")
        elif key == "created":
            phrases.append(f"created {value} learned-context record{'' if value == 1 else 's'}")
        elif key == "learned_context_superseded":
            phrases.append(f"superseded {value} learned-context record{'' if value == 1 else 's'}")
        elif key == "proposals_rejected":
            phrases.append(f"rejected {value} proposal{'' if value == 1 else 's'}")
        elif key == "appended_events":
            phrases.append(f"staged {value} memory event{'' if value == 1 else 's'}")
    return f"Memory changed: {', '.join(phrases[:3])}."


def _drift_contributors(cycle: dict[str, Any], previous: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not previous:
        return []
    prior = previous[-1]
    contributors: list[dict[str, Any]] = []

    current_signal = _int(cycle.get("signal_row_count"))
    prior_signal = _int(prior.get("signal_row_count"))
    signal_delta = current_signal - prior_signal
    if abs(signal_delta) >= max(SIGNAL_BUCKET_SIZE, round(max(prior_signal, 1) * 0.1)):
        contributors.append(
            {
                "key": "signal_row_count",
                "from": prior_signal,
                "to": current_signal,
                "delta": signal_delta,
                "weight": 45,
            }
        )

    for key in ("mode", "status", "reason", "model_id"):
        before = prior.get(key)
        after = cycle.get(key)
        if before != after and (before or after):
            contributors.append({"key": key, "from": before, "to": after, "weight": 35})

    before_phases = prior.get("phases")
    after_phases = cycle.get("phases")
    if before_phases != after_phases and (before_phases or after_phases):
        contributors.append({"key": "phases", "from": before_phases, "to": after_phases, "weight": 35})

    before_funnel = _dict(prior.get("funnel"))
    after_funnel = _dict(cycle.get("funnel"))
    for key in ("selected", "generated", "approved", "created"):
        before_value = _int(before_funnel.get(key))
        after_value = _int(after_funnel.get(key))
        if before_value != after_value:
            contributors.append({"key": f"funnel.{key}", "from": before_value, "to": after_value, "weight": 40})

    return contributors


def _drift_label(contributors: list[dict[str, Any]]) -> str:
    first = contributors[0]
    key = str(first.get("key"))
    if key == "signal_row_count":
        return f"Signal drift: {first.get('from')} -> {first.get('to')} transcripts."
    return f"Dream drift: {key} changed from {first.get('from')} to {first.get('to')}."


def _duration_anomaly_contributor(cycle: dict[str, Any], previous: list[dict[str, Any]]) -> dict[str, Any] | None:
    current = cycle.get("phase_durations") if isinstance(cycle.get("phase_durations"), dict) else {}
    if not current:
        return None
    best: dict[str, Any] | None = None
    for phase, raw_duration in current.items():
        duration = _int(raw_duration)
        baseline_values = [
            _int(row.get("phase_durations", {}).get(phase))
            for row in previous
            if isinstance(row.get("phase_durations"), dict) and _int(row.get("phase_durations", {}).get(phase)) > 0
        ]
        if len(baseline_values) < MIN_DURATION_BASELINE:
            continue
        baseline = median(baseline_values)
        if baseline <= 0:
            continue
        ratio = duration / baseline
        if ratio < 3 or duration - baseline < 500:
            continue
        contributor = {
            "key": "phase_duration",
            "phase": phase,
            "baseline_ms": round(baseline),
            "duration_ms": duration,
            "ratio": round(ratio, 1),
            "weight": 60,
        }
        if best is None or float(contributor["ratio"]) > float(best["ratio"]):
            best = contributor
    return best


def _signal_bucket(value: int) -> str:
    start = (value // SIGNAL_BUCKET_SIZE) * SIGNAL_BUCKET_SIZE
    return f"{start}-{start + SIGNAL_BUCKET_SIZE - 1}"


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}
