from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from .models import AutomationJob, AutomationRecord
from .storage import MemoryStore
from .util import parse_timestamp, slugify, stable_id, summarize, to_iso, utc_now
from .validation import validate_document


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def _normalize_job_payload(payload: dict[str, Any], *, now: str) -> dict[str, Any]:
    job = dict(payload)
    title = str(job.get("title", "")).strip()
    if not title:
        raise ValueError("automation job requires a title")
    job_id = str(job.get("job_id", "")).strip() or slugify(title)
    trigger = dict(job.get("trigger", {}))
    input_selectors = dict(job.get("input_selectors", {}))
    output = dict(job.get("output", {}))
    merge_policy = dict(job.get("merge_policy", {}))
    decay_policy = dict(job.get("decay_policy", {}))
    review_policy = dict(job.get("review_policy", {}))
    security_policy = dict(job.get("security_policy", {}))

    normalized = AutomationJob(
        version=1,
        job_id=job_id,
        title=title,
        description=str(job.get("description", "")).strip(),
        skill_ref=str(job.get("skill_ref", "builtin://projection-engine")),
        enabled=bool(job.get("enabled", True)),
        trigger={
            "type": str(trigger.get("type", "interval")),
            "interval_seconds": int(trigger.get("interval_seconds", 3600)),
        },
        input_selectors={
            "memory_types_any": [str(item) for item in input_selectors.get("memory_types_any", [])],
            "text_terms_any": [str(item) for item in input_selectors.get("text_terms_any", [])],
            "statuses_any": [str(item) for item in input_selectors.get("statuses_any", ["active"])],
            "limit": int(input_selectors.get("limit", 25)),
        },
        output={
            "record_type": str(output.get("record_type", "generic")),
            "max_records": int(output.get("max_records", 25)),
        },
        merge_policy={"dedupe_by": str(merge_policy.get("dedupe_by", "title"))},
        decay_policy={"stale_after_runs": int(decay_policy.get("stale_after_runs", 1))},
        review_policy={
            "require_manual_review": bool(review_policy.get("require_manual_review", True)),
            "auto_surface_limit": int(review_policy.get("auto_surface_limit", 3)),
        },
        security_policy={"allow_sensitive": bool(security_policy.get("allow_sensitive", False))},
        created_at=str(job.get("created_at", now)),
        updated_at=now,
    ).to_dict()
    validate_document("automation-job.schema.json", normalized)
    return normalized


def register_job(store: MemoryStore, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    normalized = _normalize_job_payload(payload, now=timestamp)
    path = store.save_automation_job(normalized)
    return {
        "status": "registered",
        "job": normalized,
        "job_path": str(path.relative_to(store.workspace)),
    }


def _job_due(job: dict[str, Any], state: dict[str, Any], *, now: str) -> bool:
    if not bool(job.get("enabled", True)):
        return False
    last_run_at = state.get("last_run_at")
    interval_seconds = int(job.get("trigger", {}).get("interval_seconds", 0))
    if not last_run_at or interval_seconds <= 0:
        return True
    return parse_timestamp(now) >= parse_timestamp(str(last_run_at)) + timedelta(seconds=interval_seconds)


def _matching_source_records(store: MemoryStore, job: dict[str, Any]) -> list[dict[str, Any]]:
    selectors = job.get("input_selectors", {})
    types_any = {str(item).lower() for item in selectors.get("memory_types_any", []) if str(item).strip()}
    text_terms_any = [str(item).lower() for item in selectors.get("text_terms_any", []) if str(item).strip()]
    statuses_any = {str(item).lower() for item in selectors.get("statuses_any", []) if str(item).strip()}
    limit = int(selectors.get("limit", 25))

    matched: list[dict[str, Any]] = []
    for record in store.load_durable_records():
        if statuses_any and str(record.get("status", "")).lower() not in statuses_any:
            continue
        if types_any and str(record.get("type", "")).lower() not in types_any:
            continue
        haystack = " ".join(
            [
                str(record.get("title", "")),
                str(record.get("summary", "")),
                str(record.get("body", "")),
            ]
        ).lower()
        if text_terms_any and not any(term in haystack for term in text_terms_any):
            continue
        matched.append(record)

    matched.sort(
        key=lambda item: (
            -float(item.get("salience", 0.0)),
            -float(item.get("confidence", 0.0)),
            str(item.get("title", "")),
        )
    )
    return matched[:limit]


def _projection_title(record_type: str, source_title: str) -> str:
    prefix = record_type.replace("-", " ").title()
    if source_title.startswith(f"{prefix}:"):
        return source_title
    return f"{prefix}: {source_title}"


def _dedupe_key(source_record: dict[str, Any], job: dict[str, Any]) -> str:
    dedupe_by = str(job.get("merge_policy", {}).get("dedupe_by", "title"))
    base = str(source_record.get("title", ""))
    if dedupe_by == "title+summary":
        base = f"{base} {source_record.get('summary', '')}"
    return slugify(base)


def _projection_record(
    job: dict[str, Any],
    source_record: dict[str, Any],
    *,
    timestamp: str,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dedupe_key = _dedupe_key(source_record, job)
    record_type = str(job.get("output", {}).get("record_type", "generic"))
    salience = float(source_record.get("salience", 0.0))
    confidence = float(source_record.get("confidence", 0.0))
    created_at = str(existing.get("created_at", timestamp)) if existing else timestamp
    source_memory_ids = sorted(
        {
            str(source_record.get("memory_id", "")),
            *([str(item) for item in existing.get("source_memory_ids", [])] if existing else []),
        }
        - {""}
    )
    source_titles = sorted(
        {
            str(source_record.get("title", "")),
            *([str(item) for item in existing.get("source_titles", [])] if existing else []),
        }
        - {""}
    )
    record = AutomationRecord(
        version=1,
        record_id=stable_id("automation", job["job_id"], dedupe_key),
        job_id=str(job["job_id"]),
        record_type=record_type,
        title=_projection_title(record_type, str(source_record.get("title", ""))),
        summary=summarize(str(source_record.get("summary", "") or source_record.get("body", "")), 180),
        status="active",
        confidence=_clamp_score(max(confidence, float(existing.get("confidence", 0.0)) if existing else 0.0)),
        priority=_clamp_score(
            max(
                (salience + confidence) / 2.0,
                float(existing.get("priority", 0.0)) if existing else 0.0,
            )
        ),
        dedupe_key=dedupe_key,
        source_memory_ids=source_memory_ids,
        source_titles=source_titles,
        missed_runs=0,
        created_at=created_at,
        updated_at=timestamp,
        last_seen_at=timestamp,
        stale_at=None,
    ).to_dict()
    validate_document("automation-record.schema.json", record)
    return record


def run_job(store: MemoryStore, job_id: str, *, now: str | None = None) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    store.ensure_layout()
    job = store.load_automation_job(job_id)
    if not job:
        raise ValueError(f"automation job not found: {job_id}")

    normalized_job = _normalize_job_payload(job, now=timestamp)
    if normalized_job != job:
        store.save_automation_job(normalized_job)
    job = normalized_job

    run_id = stable_id("automation-run", job_id, timestamp)
    before_snapshot = store.snapshot_store_text()
    state = store.load_automation_state(job_id)
    record_type = str(job.get("output", {}).get("record_type", "generic"))

    if not job.get("enabled", True):
        existing_job_records = store.load_automation_records(job_id)
        state_path = store.save_automation_state(
            job_id,
            {
                **state,
                "job_id": job_id,
                "last_run_at": timestamp,
                "last_status": "skipped",
                "last_reason": "disabled",
                "last_run_id": run_id,
                "run_count": int(state.get("run_count", 0)),
            },
        )
        report = {
            "version": 1,
            "run_id": run_id,
            "job_id": job_id,
            "generated_at": timestamp,
            "status": "skipped",
            "reason": "disabled",
            "record_type": record_type,
            "source_memory_count": 0,
            "selected_memory_count": 0,
            "written_record_count": len(existing_job_records),
            "active_record_count": sum(1 for item in existing_job_records if item.get("status") == "active"),
            "stale_record_count": sum(1 for item in existing_job_records if item.get("status") == "stale"),
        }
        report_path = store.write_automation_run_report(report)
        audit = store.write_mutation_audit(
            action="automation-run",
            run_id=run_id,
            target_paths=[state_path, report_path],
            summary={"status": "skipped", "reason": "disabled", "job_id": job_id},
            before_snapshot=before_snapshot,
            audit_dir=store.automation_audit_dir,
        )
        report["audit"] = audit
        report["report_path"] = str(report_path.relative_to(store.workspace))
        store.write_automation_run_report(report)
        return report

    selected = _matching_source_records(store, job)
    existing_records = {str(item.get("dedupe_key", "")): item for item in store.load_automation_records(job_id)}
    merged: dict[str, dict[str, Any]] = {}
    for source in selected[: int(job.get("output", {}).get("max_records", 25))]:
        key = _dedupe_key(source, job)
        merged[key] = _projection_record(job, source, timestamp=timestamp, existing=existing_records.get(key))

    stale_after_runs = int(job.get("decay_policy", {}).get("stale_after_runs", 1))
    for key, existing in existing_records.items():
        if key in merged:
            continue
        carried = dict(existing)
        carried["missed_runs"] = int(carried.get("missed_runs", 0)) + 1
        carried["updated_at"] = timestamp
        if carried["missed_runs"] >= stale_after_runs:
            carried["status"] = "stale"
            carried["stale_at"] = timestamp
        validate_document("automation-record.schema.json", carried)
        merged[key] = carried

    records = sorted(
        merged.values(),
        key=lambda item: (item.get("status") != "active", -float(item.get("priority", 0.0)), item.get("title", "")),
    )
    records_path = store.save_automation_records(job_id, record_type, records)
    state_path = store.save_automation_state(
        job_id,
        {
            "job_id": job_id,
            "last_run_at": timestamp,
            "last_status": "completed",
            "last_reason": "ok" if selected else "no-matches",
            "last_run_id": run_id,
            "run_count": int(state.get("run_count", 0)) + 1,
        },
    )
    report = {
        "version": 1,
        "run_id": run_id,
        "job_id": job_id,
        "generated_at": timestamp,
        "status": "completed",
        "reason": "ok" if selected else "no-matches",
        "record_type": record_type,
        "source_memory_count": len(store.load_durable_records()),
        "selected_memory_count": len(selected),
        "written_record_count": len(records),
        "active_record_count": sum(1 for item in records if item.get("status") == "active"),
        "stale_record_count": sum(1 for item in records if item.get("status") == "stale"),
    }
    report_path = store.write_automation_run_report(report)
    audit = store.write_mutation_audit(
        action="automation-run",
        run_id=run_id,
        target_paths=[records_path, state_path, report_path],
        summary={
            "status": "completed",
            "job_id": job_id,
            "selected_memory_count": len(selected),
            "written_record_count": len(records),
        },
        before_snapshot=before_snapshot,
        audit_dir=store.automation_audit_dir,
    )
    report["audit"] = audit
    report["report_path"] = str(report_path.relative_to(store.workspace))
    store.write_automation_run_report(report)
    return report


def tick(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    store.ensure_layout()
    jobs = store.load_automation_jobs()
    due_jobs = [
        job
        for job in jobs
        if _job_due(job, store.load_automation_state(str(job.get("job_id", ""))), now=timestamp)
    ]
    if not due_jobs:
        return {
            "status": "skipped",
            "reason": "no-due-jobs",
            "job_count": len(jobs),
            "completed_jobs": [],
        }

    results = [run_job(store, str(job["job_id"]), now=timestamp) for job in due_jobs]
    return {
        "status": "completed" if any(item.get("status") == "completed" for item in results) else "skipped",
        "reason": "ok",
        "job_count": len(jobs),
        "completed_jobs": results,
    }


def status(store: MemoryStore, *, job_id: str | None = None, now: str | None = None) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    summary = store.automation_summary(now=timestamp)
    if job_id is None:
        return {
            "status": "ok",
            "workspace": str(store.workspace),
            "automation": summary,
        }

    job = store.load_automation_job(job_id)
    if not job:
        raise ValueError(f"automation job not found: {job_id}")
    state = store.load_automation_state(job_id)
    records = store.load_automation_records(job_id)
    return {
        "status": "ok",
        "workspace": str(store.workspace),
        "automation": summary,
        "job": job,
        "job_state": state,
        "records": records,
    }


def review(store: MemoryStore, job_id: str, *, limit: int = 10, now: str | None = None) -> dict[str, Any]:
    payload = status(store, job_id=job_id, now=now)
    records = list(payload.get("records", []))
    records.sort(
        key=lambda item: (
            item.get("status") != "active",
            -float(item.get("priority", 0.0)),
            item.get("title", ""),
        )
    )
    payload["records"] = records[:limit]
    return payload


def load_job_spec(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("automation spec must decode to an object")
    return payload


# ── Semantic automation jobs (WS8: T41-T45) ──────────────────────────────

SEMANTIC_REFRESH_JOB_TEMPLATE: dict[str, Any] = {
    "version": 1,
    "title": "Semantic refresh",
    "description": "Refresh learned context by re-running semantic dreaming on recent transcripts",
    "skill_ref": "builtin://semantic-refresh",
    "enabled": True,
    "trigger": {"type": "interval", "interval_seconds": 3600},
    "input_selectors": {"types": ["semantic_fact", "project_decision"], "statuses": ["active"]},
    "output": {"record_type": "semantic_refresh"},
    "merge_policy": {"strategy": "dedupe_by_title"},
    "decay_policy": {"stale_after_runs": 5},
    "review_policy": {"auto_approve": True, "require_review_above_confidence": 0.9},
    "security_policy": {"allow_code_mutation": False, "require_isolation": True},
}

STRATEGIST_JOB_TEMPLATE: dict[str, Any] = {
    "version": 1,
    "title": "Strategist",
    "description": "Generate strategic projections using learned context",
    "skill_ref": "builtin://strategist",
    "enabled": True,
    "trigger": {"type": "interval", "interval_seconds": 7200},
    "input_selectors": {"types": ["project_decision", "semantic_fact"], "statuses": ["active"]},
    "output": {"record_type": "strategy"},
    "merge_policy": {"strategy": "dedupe_by_title"},
    "decay_policy": {"stale_after_runs": 3},
    "review_policy": {"auto_approve": False, "require_review_above_confidence": 0.7},
    "security_policy": {"allow_code_mutation": False, "require_isolation": True},
}


def register_semantic_refresh_job(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    """Register the semantic refresh automation job."""
    job_payload = dict(SEMANTIC_REFRESH_JOB_TEMPLATE)
    job_payload["job_id"] = "semantic-refresh"
    job_payload["created_at"] = now or to_iso(utc_now())
    job_payload["updated_at"] = job_payload["created_at"]
    return register_job(store, job_payload, now=now)


def register_strategist_job(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    """Register the strategist automation job."""
    job_payload = dict(STRATEGIST_JOB_TEMPLATE)
    job_payload["job_id"] = "strategist"
    job_payload["created_at"] = now or to_iso(utc_now())
    job_payload["updated_at"] = job_payload["created_at"]
    return register_job(store, job_payload, now=now)


def run_semantic_refresh(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    """Run semantic refresh: re-evaluate learned context freshness and quality.

    This job:
    1. Checks learned context freshness
    2. Marks stale records
    3. Detects conflicts with newer durable facts
    4. Creates refresh projection records
    """
    timestamp = now or to_iso(utc_now())
    learned_records = store.load_learned_context_records()
    refreshed = 0
    stale_marked = 0
    conflicts_found = 0

    for record in learned_records:
        if record.get("status") != "active":
            continue

        # Check freshness
        fresh_until = record.get("fresh_until", "")
        if fresh_until:
            try:
                from .util import parse_timestamp
                if parse_timestamp(fresh_until) < parse_timestamp(timestamp):
                    record["status"] = "archived"
                    record["harm_signals"] = record.get("harm_signals", []) + ["stale_auto_archived"]
                    stale_marked += 1
                    continue
            except (ValueError, TypeError):
                pass

        # Check for conflicts with durable facts
        from .semantic_verifier import detect_conflicts
        conflicts = detect_conflicts(store, str(record.get("record_id", "")))
        if conflicts:
            record["conflict_state"] = "detected"
            record["harm_signals"] = record.get("harm_signals", []) + [
                f"conflict_with:{c.get('durable_memory_id', '')}" for c in conflicts
            ]
            conflicts_found += len(conflicts)

        refreshed += 1

    store.save_learned_context_records(learned_records)

    return {
        "status": "completed",
        "refreshed": refreshed,
        "stale_marked": stale_marked,
        "conflicts_found": conflicts_found,
        "total_learned_records": len(learned_records),
        "ran_at": timestamp,
    }


def scaffold_dream_job(
    workspace: Path,
    adapter_id: str,
    kind: str,
) -> dict[str, Any]:
    """Generate a scaffold job spec for feature-radar, bug-radar, fix-radar, or semantic-refresh.

    Creates adapter-specific job spec files and delegated return path conventions.
    """
    valid_kinds = ("feature-radar", "bug-radar", "fix-radar", "semantic-refresh")
    if kind not in valid_kinds:
        raise ValueError(f"invalid kind: {kind!r}; use one of {valid_kinds}")

    from .semantic_adapters import get_adapter_manifest

    manifest = get_adapter_manifest(adapter_id)
    if manifest is None:
        raise ValueError(f"unknown adapter: {adapter_id}")

    scaffold_dir = workspace / ".opendream" / "dream-jobs" / adapter_id
    scaffold_dir.mkdir(parents=True, exist_ok=True)

    ingest_mode = manifest.get("ingest_mode", "direct-report")
    execution_owner = manifest.get("execution_owner", "opendream-local")

    job_spec = {
        "version": 1,
        "job_id": f"{kind}-{adapter_id}",
        "title": f"{kind} via {adapter_id}",
        "description": f"Scaffolded {kind} job for {adapter_id} execution surface",
        "skill_ref": "builtin://projection-engine",
        "enabled": True,
        "trigger": {
            "type": "interval",
            "interval_seconds": 3600 if kind == "semantic-refresh" else 86400,
        },
        "input_selectors": {
            "memory_types_any": _kind_memory_types(kind),
            "text_terms_any": [],
            "statuses_any": ["active"],
            "limit": 25,
        },
        "output": {
            "record_type": kind,
            "title_template": f"{kind} projection",
            "summary_template": f"Automated {kind} projection from {{source_count}} source records",
        },
        "merge_policy": {"strategy": "replace_by_dedupe_key"},
        "decay_policy": {"ttl_seconds": 604800},
        "review_policy": {"auto_approve": False, "notify_on_create": True},
        "security_policy": {"write_boundary": "memory-only", "network": False},
        "adapter_context": {
            "adapter_id": adapter_id,
            "execution_owner": execution_owner,
            "ingest_mode": ingest_mode,
            "return_path": f".opendream/inbox/semantic/{adapter_id}/" if ingest_mode == "delegated-envelope" else None,
        },
    }

    job_path = scaffold_dir / f"{kind}.json"
    from .util import write_json
    write_json(job_path, job_spec)

    created_files = [str(job_path)]

    # Create delegated prompt/instructions for vendor-runtime adapters
    if ingest_mode == "delegated-envelope":
        prompt_path = scaffold_dir / f"{kind}-prompt.md"
        prompt_path.write_text(
            f"# {kind} delegated task for OpenDream\n\n"
            f"## Adapter: {adapter_id}\n"
            f"## Kind: {kind}\n\n"
            f"## Objective\n"
            f"Run a {kind} cycle for the OpenDream memory workspace.\n\n"
            f"## Steps\n"
            f"1. Read the workspace memory store and recent episodes\n"
            f"2. {_kind_objective(kind)}\n"
            f"3. Synthesize proposals with provenance\n"
            f"4. Write a delegated semantic envelope to:\n"
            f"   `.opendream/inbox/semantic/{adapter_id}/<timestamp>-<run-id>.json`\n"
            f"5. The envelope must validate against `delegated-semantic-envelope.schema.json`\n\n"
            f"## Important\n"
            f"- Do NOT modify durable memory directly\n"
            f"- Write only to the designated inbox path\n"
            f"- Include provenance metadata in the envelope\n"
            f"- Projections are non-canonical until promoted through verification\n",
            encoding="utf-8",
        )
        created_files.append(str(prompt_path))

        # Ensure inbox exists
        inbox = workspace / ".opendream" / "inbox" / "semantic" / adapter_id
        inbox.mkdir(parents=True, exist_ok=True)

    return {
        "adapter_id": adapter_id,
        "kind": kind,
        "scaffold_dir": str(scaffold_dir),
        "created_files": created_files,
        "execution_owner": execution_owner,
        "ingest_mode": ingest_mode,
    }


def _kind_memory_types(kind: str) -> list[str]:
    """Return relevant memory types for a radar/refresh kind."""
    mapping = {
        "feature-radar": ["project_decision", "semantic_fact", "feature_request"],
        "bug-radar": ["bug_report", "error_pattern", "semantic_fact"],
        "fix-radar": ["bug_fix", "project_decision", "semantic_fact"],
        "semantic-refresh": ["semantic_fact", "learned_context", "project_decision"],
    }
    return mapping.get(kind, ["semantic_fact"])


def _kind_objective(kind: str) -> str:
    """Return a human-readable objective description for a radar/refresh kind."""
    mapping = {
        "feature-radar": "Identify feature patterns and opportunities",
        "bug-radar": "Identify bugs and issues from recent activity",
        "fix-radar": "Identify fix patterns and resolutions",
        "semantic-refresh": "Refresh learned context from recent activity",
    }
    return mapping.get(kind, "Analyze memory workspace")
