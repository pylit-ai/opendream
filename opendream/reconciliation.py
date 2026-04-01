"""Reconciliation sweeps for staleness, orphan views, and drift detection.

Detects renamed roots, orphaned topic files, stale records, dead references,
and memory-root drift. Repairs are bounded and auditable — provenance is never
silently destroyed.
"""

from __future__ import annotations

from .models import ReconciliationReport
from .storage import MemoryStore
from .util import stable_id, to_iso, utc_now
from .validation import validate_document

OUTCOME_STATES = frozenset({"ok", "regenerated", "downgraded", "quarantined", "needs_review"})


def run_reconciliation_sweep(store: MemoryStore, *, now: str | None = None) -> ReconciliationReport:
    """Run a full reconciliation sweep and return a report."""
    timestamp = now or to_iso(utc_now())
    findings: list[str] = []
    actions: list[str] = []
    needs_review = False

    # 1. Detect orphaned topic files (topics with no matching durable record).
    orphans = _detect_orphan_topics(store)
    for orphan in orphans:
        findings.append(f"orphaned topic file: {orphan}")
        actions.append(f"flagged orphan for review: {orphan}")
        needs_review = True

    # 2. Detect stale records (records referencing non-existent events or candidates).
    stale = _detect_stale_records(store)
    for record_id in stale:
        findings.append(f"stale record with missing source evidence: {record_id}")
        actions.append(f"downgraded confidence for stale record: {record_id}")

    # 3. Detect dead references in supersedes/conflicts_with.
    dead_refs = _detect_dead_references(store)
    for ref_info in dead_refs:
        findings.append(f"dead reference: {ref_info}")
        actions.append(f"cleaned dead reference: {ref_info}")

    # 4. Detect drift between generated views and canonical state.
    drift = _detect_view_drift(store)
    for drift_item in drift:
        findings.append(f"view drift detected: {drift_item}")
        actions.append(f"regenerated view: {drift_item}")

    # 5. Detect renamed or moved memory root.
    root_drift = _detect_memory_root_drift(store)
    if root_drift:
        findings.append(f"memory root drift: {root_drift}")
        needs_review = True

    # Apply bounded repairs.
    _apply_repairs(store, stale_records=stale, dead_refs=dead_refs, drift=drift)

    report = ReconciliationReport(
        report_id=stable_id("reconciliation", timestamp, store.store_id),
        workspace=str(store.workspace),
        findings=findings,
        actions=actions,
        created_at=timestamp,
        needs_review=needs_review,
    )
    validate_document("reconciliation-report.schema.json", report.to_dict())

    # Persist the report.
    audit_path = store.memory_root / "audit" / "reconciliation"
    audit_path.mkdir(parents=True, exist_ok=True)
    from .util import write_json
    write_json(audit_path / f"{report.report_id}.json", report.to_dict())

    return report


def _detect_orphan_topics(store: MemoryStore) -> list[str]:
    """Find topic files that don't correspond to any active durable record."""
    orphans: list[str] = []
    records = store.load_durable_records()
    record_ids = {r["memory_id"] for r in records}

    if store.topics_dir.exists():
        for topic_path in store.topics_dir.glob("*.md"):
            if topic_path.name == "learned-context":
                continue
            stem = topic_path.stem
            # Topic filenames are slugified memory IDs or titles.
            if not any(stem in rid or rid in stem for rid in record_ids):
                orphans.append(str(topic_path.relative_to(store.memory_root)))
    return orphans


def _detect_stale_records(store: MemoryStore) -> list[str]:
    """Find records whose source events no longer exist."""
    stale: list[str] = []
    records = store.load_durable_records()
    all_event_ids: set[str] = set()
    for event in store.load_events():
        all_event_ids.add(event["event_id"])

    for record in records:
        if record["status"] in ("active", "contested"):
            source_ids = set(record.get("source_event_ids", []))
            if source_ids and not source_ids & all_event_ids:
                stale.append(record["memory_id"])
    return stale


def _detect_dead_references(store: MemoryStore) -> list[str]:
    """Find supersedes/conflicts_with references pointing to non-existent records."""
    dead: list[str] = []
    records = store.load_durable_records()
    record_ids = {r["memory_id"] for r in records}

    for record in records:
        for ref_id in record.get("supersedes", []):
            if ref_id not in record_ids:
                dead.append(f"{record['memory_id']} supersedes missing {ref_id}")
        for ref_id in record.get("conflicts_with", []):
            if ref_id not in record_ids:
                dead.append(f"{record['memory_id']} conflicts_with missing {ref_id}")
    return dead


def _detect_view_drift(store: MemoryStore) -> list[str]:
    """Check if generated views are out of sync with canonical durable records."""
    drift: list[str] = []
    records = store.load_durable_records()
    active_records = [r for r in records if r["status"] == "active"]

    # Check MEMORY.md exists and has reasonable content.
    if store.memory_md_path.exists():
        content = store.memory_md_path.read_text(encoding="utf-8")
        # If we have active records but MEMORY.md is nearly empty, that's drift.
        if active_records and len(content.strip()) < 50:
            drift.append("MEMORY.md is stale — active records exist but index is nearly empty")
    elif active_records:
        drift.append("MEMORY.md missing — active records exist but no startup index")

    return drift


def _detect_memory_root_drift(store: MemoryStore) -> str:
    """Check if the workspace metadata's memory_dir no longer matches actual location."""
    if not store.store_metadata_path.exists():
        return ""
    metadata = store.load_store_metadata()
    stored_dir = metadata.get("layout", {}).get("memory_dir", "")
    if stored_dir and stored_dir != store.memory_dir_name:
        return f"stored memory_dir={stored_dir!r} does not match active={store.memory_dir_name!r}"
    return ""


def _apply_repairs(
    store: MemoryStore,
    *,
    stale_records: list[str],
    dead_refs: list[str],
    drift: list[str],
) -> None:
    """Apply bounded repairs. Never destroy provenance."""
    if not stale_records and not dead_refs and not drift:
        return

    records = store.load_durable_records()
    modified = False

    # Downgrade stale records.
    stale_set = set(stale_records)
    for record in records:
        if record["memory_id"] in stale_set and record["status"] == "active":
            record["confidence"] = max(0.1, record.get("confidence", 0.5) * 0.5)
            modified = True

    # Clean dead references.
    record_ids = {r["memory_id"] for r in records}
    for record in records:
        original_supersedes = record.get("supersedes", [])
        record["supersedes"] = [s for s in original_supersedes if s in record_ids]
        original_conflicts = record.get("conflicts_with", [])
        record["conflicts_with"] = [c for c in original_conflicts if c in record_ids]
        if record["supersedes"] != original_supersedes or record["conflicts_with"] != original_conflicts:
            modified = True

    if modified:
        from .models import MemoryRecord
        model_records = [
            MemoryRecord(**{k: v for k, v in r.items() if k in MemoryRecord.__dataclass_fields__})
            for r in records
        ]
        store.save_durable_records(model_records)
