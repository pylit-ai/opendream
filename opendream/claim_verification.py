"""Verify-before-assert: claim classification and provenance-tier gating.

Concrete claims that are externally checkable must be verified or source-backed
before promotion. Unverifiable concrete claims are downgraded or quarantined.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import ClaimVerificationReport
from .util import stable_id, to_iso, utc_now
from .validation import validate_document

CLAIM_CLASSES = frozenset({"externally_checkable", "derived_abstraction", "speculative"})
PROVENANCE_TIERS = frozenset({"source_backed", "runtime_verified", "inferred", "speculative"})
VERIFICATION_RESULTS = frozenset({"verified", "downgraded", "quarantined", "rejected"})

# Patterns that suggest externally checkable claims (file counts, paths, versions, framework names).
_CHECKABLE_PATTERNS = [
    re.compile(r"\b\d+\s+files?\b", re.IGNORECASE),
    re.compile(r"\b(?:v|version)\s*\d+", re.IGNORECASE),
    re.compile(
        r"(?:uses?|requires?|depends?\s+on)\s+(?:React|Vue|Django|Flask|FastAPI|Express|Rails|Spring)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:located|found)\s+(?:at|in)\s+[/\\]", re.IGNORECASE),
    re.compile(r"\b\d+\s+(?:tests?|endpoints?|routes?|models?|tables?)\b", re.IGNORECASE),
    re.compile(r"\bport\s+\d{2,5}\b", re.IGNORECASE),
]

_SPECULATIVE_MARKERS = [
    re.compile(r"\b(?:probably|likely|might|maybe|could be|seems?|appears?)\b", re.IGNORECASE),
]


def classify_claim(body: str, *, title: str = "") -> str:
    """Classify a memory claim into one of the three claim classes."""
    text = f"{title} {body}"
    for pattern in _SPECULATIVE_MARKERS:
        if pattern.search(text):
            return "speculative"
    for pattern in _CHECKABLE_PATTERNS:
        if pattern.search(text):
            return "externally_checkable"
    return "derived_abstraction"


def assign_provenance_tier(
    claim_class: str,
    *,
    has_source_evidence: bool = False,
    runtime_verified: bool = False,
) -> str:
    """Assign provenance tier based on claim class and available evidence."""
    if claim_class == "speculative":
        return "speculative"
    if has_source_evidence:
        return "source_backed"
    if runtime_verified:
        return "runtime_verified"
    return "inferred"


def should_promote(claim_class: str, provenance_tier: str) -> tuple[bool, str]:
    """Decide whether a claim should be promoted to active status.

    Returns (should_promote, reason).
    """
    if claim_class == "externally_checkable" and provenance_tier in ("inferred", "speculative"):
        return False, "externally checkable claim lacks verification evidence"
    if claim_class == "speculative" and provenance_tier in ("inferred", "speculative"):
        return False, "speculative claim cannot be promoted without evidence"
    return True, "claim meets provenance requirements"


def verify_claim(
    *,
    claim_id: str,
    body: str,
    title: str = "",
    workspace: Path | None = None,
    verification_reads: list[str] | None = None,
) -> ClaimVerificationReport:
    """Run claim verification and return a report.

    If *workspace* is provided and the claim references paths, attempt to verify
    they exist. Otherwise, classify and assign provenance based on text alone.
    """
    now = to_iso(utc_now())
    claim_class = classify_claim(body, title=title)
    reads: list[str] = list(verification_reads or [])
    has_source_evidence = False
    runtime_verified_flag = False

    # Attempt filesystem verification for externally checkable claims.
    if workspace and claim_class == "externally_checkable":
        path_matches = re.findall(r"(?:at|in)\s+([/\\]\S+)", f"{title} {body}")
        for path_str in path_matches:
            candidate = workspace / path_str.lstrip("/\\")
            reads.append(str(candidate))
            if candidate.exists():
                runtime_verified_flag = True

    provenance_tier = assign_provenance_tier(
        claim_class,
        has_source_evidence=has_source_evidence,
        runtime_verified=runtime_verified_flag,
    )

    promotable, reason = should_promote(claim_class, provenance_tier)
    if promotable:
        result = "verified"
    elif claim_class == "speculative":
        result = "quarantined"
    else:
        result = "downgraded"

    report = ClaimVerificationReport(
        report_id=stable_id("claim-verify", claim_id, now),
        claim_id=claim_id,
        claim_class=claim_class,
        provenance_tier=provenance_tier,
        result=result,
        checked_at=now,
        verification_reads=reads,
        reason=reason,
    )
    validate_document("claim-verification-report.schema.json", report.to_dict())
    return report
