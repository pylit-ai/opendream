from __future__ import annotations

from typing import Any


def synthesize_dream_narrative(summary: dict[str, Any]) -> str:
    """Return a deterministic one-sentence operator summary for a dream run."""
    status = str(summary.get("status") or "unknown")
    reason = str(summary.get("reason") or "").strip()
    mode = str(summary.get("mode") or summary.get("type") or "deterministic")
    if status == "skipped":
        if reason == "no-episodes":
            return (
                "Dream skipped because no agent transcripts were available; "
                "ingest transcripts or provide explicit episodes."
            )
        if reason in {"no-signal", "insufficient-signal"}:
            gathered = _int(summary.get("gathered_rows") or summary.get("signal_row_count"))
            return (
                f"Dream skipped after scanning {gathered} signal row(s) because "
                "no memory-worthy signal cleared policy."
            )
        if reason == "no-backlog":
            return "Dream skipped because transcript and event signal were already up to date."
        if reason == "min-interval":
            return "Dream skipped because the minimum interval between cycles has not elapsed."
        if reason == "lock-held":
            return "Dream skipped because another dream or consolidation cycle held the lock."
        return f"Dream skipped ({reason or 'unknown reason'})."

    if status == "failed":
        return f"Dream failed ({reason or 'unknown reason'}); inspect the run detail and audit artifacts."

    approved = _int(summary.get("proposals_approved"))
    generated = _int(summary.get("proposals_generated"))
    created = _int(summary.get("learned_context_created"))
    rejected = _int(summary.get("proposals_rejected"))
    appended = _int(summary.get("appended_events"))
    gathered = _int(summary.get("gathered_rows") or summary.get("signal_row_count"))
    signal_source = str(summary.get("latest_signal_source") or "").strip()
    if generated or approved or created:
        return (
            f"{_label_mode(mode)} dream reviewed {generated} proposal(s), approved {approved}, "
            f"created {created} learned-context record(s), and rejected {rejected}."
        )
    if mode in {"semantic", "hybrid"}:
        return (
            f"{_label_mode(mode)} dream scanned {gathered} {_signal_label(signal_source)} row(s), "
            "generated 0 learned-context proposals, and created 0 learned-context records."
        )
    if appended or gathered:
        return (
            f"Dream gathered {gathered} transcript row(s), staged {appended} event(s), "
            "and ran deterministic memory maintenance."
        )
    return f"{_label_mode(mode)} dream completed with no proposal or event changes."


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _label_mode(mode: str) -> str:
    normalized = mode.replace("_", " ").strip().lower()
    if normalized in {"", "dream"}:
        return "Deterministic"
    return normalized.capitalize()


def _signal_label(source: str) -> str:
    if source == "explicit_events":
        return "explicit-event"
    if source == "transcript_episodes":
        return "transcript"
    return "signal"
