"""Delegated semantic envelope ingest pipeline.

Implements WS7 (T39-T43): envelope validation, inbox scanning, archive/failure
handling, conversion to learned-context proposals and event emissions, and
provenance linking.
"""

from __future__ import annotations

import contextlib
import json
import shutil
from pathlib import Path
from typing import Any

from .semantic_verifier import promote_proposal, verify_proposal
from .storage import MemoryStore
from .util import stable_id, to_iso, utc_now
from .validation import SchemaValidationError, validate_document

INBOX_BASE = ".opendream/inbox/semantic"
ARCHIVE_BASE = ".opendream/archive/semantic"


def _inbox_dir(workspace: Path, adapter_id: str | None = None) -> Path:
    base = workspace / INBOX_BASE
    if adapter_id:
        return base / adapter_id
    return base


def _archive_dir(workspace: Path, adapter_id: str | None = None) -> Path:
    base = workspace / ARCHIVE_BASE
    if adapter_id:
        return base / adapter_id
    return base


def validate_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Validate a delegated semantic envelope against the schema.

    Returns dict with 'valid' bool and 'issues' list.
    """
    issues: list[str] = []
    try:
        validate_document("delegated-semantic-envelope.schema.json", envelope)
    except SchemaValidationError as exc:
        issues.append(str(exc))

    # Additional business-rule validation
    proposals = envelope.get("proposals", [])
    if not isinstance(proposals, list):
        issues.append("proposals must be a list")
    elif not proposals:
        issues.append("envelope contains no proposals")

    adapter_id = envelope.get("adapter_id", "")
    if not adapter_id:
        issues.append("adapter_id is required")

    return {"valid": len(issues) == 0, "issues": issues}


def ingest_envelope(
    store: MemoryStore,
    envelope: dict[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Ingest a validated delegated semantic envelope.

    Converts proposals into learned-context proposal entries and runs them
    through the standard verify-promote pipeline.
    """
    timestamp = now or to_iso(utc_now())
    run_id = envelope.get("run_id", stable_id("ingest", timestamp))
    adapter_id = envelope.get("adapter_id", "unknown")

    # Validate first
    validation = validate_envelope(envelope)
    if not validation["valid"]:
        return {
            "run_id": run_id,
            "adapter_id": adapter_id,
            "status": "rejected",
            "reason": "envelope validation failed",
            "issues": validation["issues"],
        }

    proposals = envelope.get("proposals", [])
    proposed_events = envelope.get("proposed_events", [])
    workspace_id = store.store_id

    # Process proposals through verify-promote pipeline
    promoted = 0
    rejected = 0
    source_events = store.load_events()

    for raw_proposal in proposals:
        # Normalize proposal format for the verifier
        proposal = {
            "workspace_id": workspace_id,
            "source_event_ids": raw_proposal.get("source_event_ids", []),
            "source_episode_ids": raw_proposal.get("source_episode_ids", []),
            "source_trace_ids": raw_proposal.get("source_trace_ids", []),
            "query_family_tags": raw_proposal.get("query_family_tags",
                                                   envelope.get("anticipated_query_families", [])),
            "summary": raw_proposal.get("summary", ""),
            "details": raw_proposal.get("details", ""),
            "assumptions": raw_proposal.get("assumptions", f"Delegated from {adapter_id}"),
            "provider_id": f"delegated:{adapter_id}",
            "model_id": raw_proposal.get("model_id", "delegated"),
            "prompt_version": raw_proposal.get("prompt_version", "1"),
            "fresh_until": raw_proposal.get("fresh_until", ""),
            "confidence": raw_proposal.get("confidence", 0.5),
            "estimated_tokens": raw_proposal.get("estimated_tokens", 0),
        }

        vresult = verify_proposal(
            store,
            proposal,
            source_events=source_events[-50:],
        )

        if vresult.get("combined_verdict") in ("approve", "review_required"):
            promote_proposal(store, proposal, vresult, now=timestamp)
            promoted += 1
        else:
            rejected += 1

    # Emit proposed events if any
    events_emitted = 0
    if proposed_events:
        from .integration import emit_event as _emit_event

        for pe in proposed_events:
            try:
                _emit_event(
                    store,
                    kind=pe.get("kind", "delegated_observation"),
                    content=pe.get("content", ""),
                    scope=pe.get("scope", "project"),
                    channel=f"delegated:{adapter_id}",
                    message_ref=f"delegated-ingest:{run_id}",
                )
                events_emitted += 1
            except (ValueError, TypeError):
                pass

    return {
        "run_id": run_id,
        "adapter_id": adapter_id,
        "status": "completed",
        "proposals_received": len(proposals),
        "proposals_promoted": promoted,
        "proposals_rejected": rejected,
        "events_emitted": events_emitted,
        "provenance": {
            "execution_owner": envelope.get("execution_owner", "unknown"),
            "workspace_ref": envelope.get("workspace_ref", ""),
            "created_at": envelope.get("created_at", ""),
        },
    }


def ingest_file(
    store: MemoryStore,
    envelope_path: Path,
    *,
    now: str | None = None,
    archive_on_complete: bool = True,
) -> dict[str, Any]:
    """Ingest a single envelope file.

    On success or validation failure, archives the file.
    """
    workspace = store.workspace
    try:
        raw = json.loads(envelope_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _archive_failed(workspace, envelope_path, str(exc))
        return {
            "file": str(envelope_path),
            "status": "rejected",
            "reason": f"cannot read envelope: {exc}",
        }

    if not isinstance(raw, dict):
        _archive_failed(workspace, envelope_path, "envelope is not a JSON object")
        return {
            "file": str(envelope_path),
            "status": "rejected",
            "reason": "envelope is not a JSON object",
        }

    result = ingest_envelope(store, raw, now=now)
    result["file"] = str(envelope_path)

    if archive_on_complete:
        adapter_id = raw.get("adapter_id", "unknown")
        if result.get("status") == "completed":
            _archive_completed(workspace, envelope_path, adapter_id)
        else:
            _archive_failed(workspace, envelope_path, result.get("reason", "rejected"))

    return result


def scan_inbox(
    store: MemoryStore,
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Scan the inbox for pending envelopes and ingest them all."""
    workspace = store.workspace
    inbox = _inbox_dir(workspace)
    results: list[dict[str, Any]] = []

    if not inbox.exists():
        return {
            "status": "completed",
            "envelopes_found": 0,
            "results": [],
        }

    envelope_files = sorted(inbox.rglob("*.json"))

    for path in envelope_files:
        result = ingest_file(store, path, now=now)
        results.append(result)

    return {
        "status": "completed",
        "envelopes_found": len(envelope_files),
        "envelopes_ingested": sum(1 for r in results if r.get("status") == "completed"),
        "envelopes_rejected": sum(1 for r in results if r.get("status") == "rejected"),
        "results": results,
    }


def _archive_completed(workspace: Path, envelope_path: Path, adapter_id: str) -> None:
    """Move a successfully ingested envelope to the archive."""
    archive = _archive_dir(workspace, adapter_id) / "completed"
    archive.mkdir(parents=True, exist_ok=True)
    dest = archive / envelope_path.name
    with contextlib.suppress(OSError):
        shutil.move(str(envelope_path), str(dest))


def _archive_failed(workspace: Path, envelope_path: Path, reason: str) -> None:
    """Archive a failed envelope with failure reason."""
    archive = _archive_dir(workspace) / "failed"
    archive.mkdir(parents=True, exist_ok=True)
    dest = archive / envelope_path.name
    with contextlib.suppress(OSError):
        shutil.move(str(envelope_path), str(dest))
    # Write failure reason alongside
    reason_path = archive / (envelope_path.stem + ".failure.txt")
    with contextlib.suppress(OSError):
        reason_path.write_text(reason, encoding="utf-8")
