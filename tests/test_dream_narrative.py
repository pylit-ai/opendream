from __future__ import annotations

from opendream.dream_narrative import synthesize_dream_narrative


def test_narrative_completed_semantic_proposals() -> None:
    text = synthesize_dream_narrative(
        {
            "status": "completed",
            "mode": "hybrid",
            "proposals_generated": 4,
            "proposals_approved": 2,
            "proposals_rejected": 1,
            "learned_context_created": 2,
        }
    )
    assert "Hybrid dream reviewed 4 proposal(s)" in text
    assert "created 2 learned-context record(s)" in text


def test_narrative_completed_deterministic_events() -> None:
    text = synthesize_dream_narrative(
        {
            "status": "completed",
            "gathered_rows": 6,
            "appended_events": 3,
        }
    )
    assert "gathered 6 transcript row(s)" in text
    assert "staged 3 event(s)" in text


def test_narrative_completed_no_changes() -> None:
    assert "completed with no proposal or event changes" in synthesize_dream_narrative({"status": "completed"})


def test_narrative_skipped_known_reasons() -> None:
    assert "no agent transcripts" in synthesize_dream_narrative({"status": "skipped", "reason": "no-episodes"})
    assert "no memory-worthy signal" in synthesize_dream_narrative(
        {"status": "skipped", "reason": "insufficient-signal", "gathered_rows": 2}
    )
    assert "already up to date" in synthesize_dream_narrative({"status": "skipped", "reason": "no-backlog"})
    assert "minimum interval" in synthesize_dream_narrative({"status": "skipped", "reason": "min-interval"})
    assert "held the lock" in synthesize_dream_narrative({"status": "skipped", "reason": "lock-held"})


def test_narrative_failed_and_unknown_skip() -> None:
    assert "Dream failed" in synthesize_dream_narrative({"status": "failed", "reason": "provider error"})
    assert synthesize_dream_narrative({"status": "skipped", "reason": "custom"}) == "Dream skipped (custom)."
