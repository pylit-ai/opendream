from __future__ import annotations

import difflib
import json
import os
import time
from collections import defaultdict
from collections.abc import Iterable, Sequence
from contextlib import AbstractContextManager
from datetime import timedelta
from pathlib import Path
from typing import Any

from .models import (
    Annotation,
    AutomationJob,
    AutomationRecord,
    ConsolidationOperation,
    ContextAssembly,
    MemoryCandidate,
    MemoryEvent,
    MemoryRecord,
    ReviewDecision,
    StartupIndexEntry,
)
from .util import (
    append_jsonl,
    atomic_write_text,
    ensure_relative_to,
    parse_timestamp,
    read_json,
    stable_id,
    summarize,
    to_iso,
    utc_now,
    write_json,
)
from .validation import validate_document

DEFAULT_CONFIG: dict[str, Any] = {
    "locks": {"ttl_seconds": 1800},
    "index_policy": {"max_entries": 40, "max_chars_per_summary": 140},
    "dream": {"max_recent_episodes": 120, "min_episode_signals": 1},
    "planner": {"mode": "builtin", "command": None, "timeout_seconds": 20},
    "verifier": {"mode": "builtin", "command": None, "timeout_seconds": 20},
    "retrieval": {"embedding_enabled": True, "semantic_merge_threshold": 0.72},
    "retention": {
        "candidate_ttl_days": 14,
        "pending_item_decay_days": 7,
        "weak_memory_quarantine_days": 30,
    },
    "promotion": {"workflow_min_successful_recalls": 2},
    "scheduler": {"min_new_events": 1, "min_interval_seconds": 0},
}

STORE_KIND_PRECEDENCE = {
    "project": 0,
    "workspace": 1,
    "agent": 2,
    "global": 3,
}
VALID_STORE_KINDS = frozenset(STORE_KIND_PRECEDENCE)

# Default layout lives under `.opendream/` so repo-root `memory/` is free for brownfield trees.
DEFAULT_MEMORY_DIR = ".opendream/memory"
LEGACY_MEMORY_DIR = "memory"


def _memory_dir_from_store_json(store_path: Path) -> str | None:
    payload = read_json(store_path, {})
    if not isinstance(payload, dict):
        return None
    layout = payload.get("layout")
    if not isinstance(layout, dict):
        return None
    md = layout.get("memory_dir")
    if isinstance(md, str) and md.strip():
        return md.strip()
    return None


def resolve_memory_dir_name(workspace: Path, memory_dir: str | None) -> str:
    """Resolve the memory directory name for a workspace.

    Explicit ``memory_dir`` wins. Otherwise, if a legacy or modern ``store.json`` exists,
    its ``layout.memory_dir`` is used (with path-specific fallbacks). Fresh workspaces
    default to :data:`DEFAULT_MEMORY_DIR`.
    """
    if memory_dir is not None:
        name = memory_dir.strip()
        if not name:
            raise ValueError("memory_dir must be non-empty when provided")
        candidate = Path(name)
        if candidate.is_absolute():
            raise ValueError("memory_dir must be relative to the workspace")
        return name

    ws = Path(workspace).expanduser().resolve()
    legacy_store = ws / LEGACY_MEMORY_DIR / "state" / "store.json"
    modern_store = ws / Path(DEFAULT_MEMORY_DIR) / "state" / "store.json"

    if legacy_store.exists():
        return _memory_dir_from_store_json(legacy_store) or LEGACY_MEMORY_DIR
    if modern_store.exists():
        return _memory_dir_from_store_json(modern_store) or DEFAULT_MEMORY_DIR
    return DEFAULT_MEMORY_DIR


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class LockError(RuntimeError):
    """Raised when the consolidator lock cannot be acquired."""


class FileLock(AbstractContextManager["FileLock"]):
    def __init__(self, path: Path, ttl_seconds: int) -> None:
        self.path = path
        self.ttl_seconds = ttl_seconds
        self.acquired = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if self._is_stale():
                self.path.unlink(missing_ok=True)
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            else:
                raise LockError(f"lock already held: {self.path}") from None
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            payload = {"pid": os.getpid(), "acquired_at": to_iso(utc_now())}
            handle.write(json.dumps(payload))
        self.acquired = True

    def _is_stale(self, *, now: float | None = None) -> bool:
        if not self.path.exists():
            return False
        current = time.time() if now is None else now
        age_seconds = current - self.path.stat().st_mtime
        return age_seconds > self.ttl_seconds

    def describe(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"present": False, "stale": False, "path": str(self.path)}
        payload = read_json(self.path, {})
        return {
            "present": True,
            "stale": self._is_stale(),
            "path": str(self.path),
            "pid": payload.get("pid"),
            "acquired_at": payload.get("acquired_at"),
        }

    def release(self) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, exc_tb: object) -> None:
        self.release()


class MemoryStore:
    def __init__(
        self,
        workspace: Path,
        config: dict[str, Any] | None = None,
        store_kind_hint: str | None = None,
        memory_dir: str | None = None,
        compat_mode: str | None = None,
    ) -> None:
        self.workspace = Path(workspace).expanduser()
        self.memory_dir_name = resolve_memory_dir_name(self.workspace, memory_dir)
        self.memory_root = self.workspace / self.memory_dir_name
        self.config = _deep_merge(DEFAULT_CONFIG, config or {})
        self.store_kind_hint = store_kind_hint
        self.compat_mode_hint = compat_mode
        self.topics_dir = self.memory_root / "topics"
        self.events_dir = self.memory_root / "state" / "events"
        self.transcripts_dir = self.memory_root / "state" / "transcripts"
        self.candidates_dir = self.memory_root / "state" / "candidates"
        self.audit_consolidation_dir = self.memory_root / "audit" / "consolidation"
        self.audit_retrieval_dir = self.memory_root / "audit" / "retrieval"
        self.audit_context_dir = self.memory_root / "audit" / "context"
        self.audit_bootstrap_dir = self.memory_root / "audit" / "bootstrap"
        self.audit_dream_dir = self.memory_root / "audit" / "dream"
        self.audit_plan_dir = self.memory_root / "audit" / "plans"
        self.audit_verifier_dir = self.memory_root / "audit" / "verifier"
        self.audit_worker_dir = self.memory_root / "audit" / "worker"
        self.audit_service_dir = self.memory_root / "audit" / "service"
        self.audit_autowire_dir = self.memory_root / "audit" / "autowire"
        self.audit_mutation_dir = self.memory_root / "audit" / "mutations"
        self.annotations_dir = self.memory_root / "audit" / "annotations"
        self.reviews_dir = self.memory_root / "audit" / "reviews"
        self.exports_dir = self.memory_root / "audit" / "exports"
        self.automation_root = self.memory_root / "automation"
        self.automation_jobs_dir = self.automation_root / "jobs"
        self.automation_state_dir = self.automation_root / "state"
        self.automation_records_dir = self.automation_root / "records"
        self.automation_audit_dir = self.automation_root / "audit"
        self.locks_dir = self.memory_root / "locks"
        self.state_dir = self.memory_root / "state"
        self.durable_records_path = self.state_dir / "durable_records.json"
        self.index_json_path = self.state_dir / "index.json"
        self.observability_index_path = self.state_dir / "observability_index.json"
        self.memory_md_path = self.memory_root / "MEMORY.md"
        self.processed_candidates_path = self.state_dir / "processed_candidates.json"
        self.extraction_state_path = self.state_dir / "processed_events.json"
        self.maintenance_state_path = self.state_dir / "maintenance_state.json"
        self.dream_state_path = self.state_dir / "dream_state.json"
        self.dream_queue_path = self.state_dir / "dream_queue.json"
        self.dream_worker_state_path = self.state_dir / "dream_worker_state.json"
        self.worker_health_path = self.state_dir / "worker_health.json"
        self.service_manifest_path = self.state_dir / "service_manifest.json"
        self.service_runtime_path = self.state_dir / "service_runtime.json"
        self.store_metadata_path = self.state_dir / "store.json"

    def default_store_metadata(self, *, store_kind: str | None = None) -> dict[str, Any]:
        resolved_kind = store_kind or self.store_kind_hint or "project"
        if resolved_kind not in VALID_STORE_KINDS:
            raise ValueError(f"unsupported store kind: {resolved_kind}")
        scheduler = self.config["scheduler"]
        return {
            "store_id": stable_id("store", self.workspace.resolve(), resolved_kind),
            "store_kind": resolved_kind,
            "workspace": str(self.workspace),
            "created_at": to_iso(utc_now()),
            "layout": {
                "memory_dir": self.memory_dir_name,
                "compat_mode": self.compat_mode_hint or "canonical",
            },
            "scheduler": {
                "min_new_events": int(scheduler["min_new_events"]),
                "min_interval_seconds": int(scheduler["min_interval_seconds"]),
            },
            "dream": {
                "max_recent_episodes": int(self.config["dream"]["max_recent_episodes"]),
                "min_episode_signals": int(self.config["dream"]["min_episode_signals"]),
            },
        }

    def is_initialized(self) -> bool:
        return self.store_metadata_path.exists()

    def load_store_metadata(self) -> dict[str, Any]:
        metadata = self.default_store_metadata()
        if not self.store_metadata_path.exists():
            return metadata
        payload = read_json(self.store_metadata_path, {})
        if not isinstance(payload, dict):
            return metadata
        merged = dict(metadata)
        for key in ("store_id", "store_kind", "workspace", "created_at"):
            if key in payload:
                merged[key] = payload[key]
        merged["scheduler"] = _deep_merge(metadata["scheduler"], payload.get("scheduler", {}))
        merged["dream"] = _deep_merge(metadata["dream"], payload.get("dream", {}))
        merged["layout"] = _deep_merge(metadata["layout"], payload.get("layout", {}))
        return merged

    @property
    def store_kind(self) -> str:
        return str(self.load_store_metadata()["store_kind"])

    @property
    def store_id(self) -> str:
        return str(self.load_store_metadata()["store_id"])

    @property
    def compat_mode(self) -> str:
        return str(self.load_store_metadata()["layout"]["compat_mode"])

    def initialize(self, *, store_kind: str = "project", compat_mode: str | None = None) -> dict[str, Any]:
        metadata = self.load_store_metadata()
        metadata["store_kind"] = store_kind
        metadata["store_id"] = stable_id("store", self.workspace.resolve(), store_kind)
        metadata["workspace"] = str(self.workspace)
        metadata.setdefault("layout", {})
        metadata["layout"]["memory_dir"] = self.memory_dir_name
        metadata["layout"]["compat_mode"] = compat_mode or self.compat_mode_hint or metadata["layout"].get(
            "compat_mode", "canonical"
        )
        if not self.store_metadata_path.exists():
            metadata["created_at"] = to_iso(utc_now())
        self._ensure_directories()
        self._initialize_default_files()
        write_json(self.store_metadata_path, metadata)
        return metadata

    def ensure_layout(self) -> None:
        self._ensure_directories()
        self._initialize_default_files()
        if not self.store_metadata_path.exists():
            write_json(self.store_metadata_path, self.default_store_metadata())

    def memory_layout_advisory(self) -> dict[str, Any]:
        """Single source of truth for where this store reads/writes; flags common shadow paths."""
        ws = self.workspace.resolve()
        canonical = self.memory_root.resolve()
        try:
            active_rel = str(canonical.relative_to(ws))
        except ValueError:
            active_rel = str(canonical)
        shadows: list[str] = []
        for candidate in (
            (self.workspace / Path(DEFAULT_MEMORY_DIR)).resolve(),
            (self.workspace / LEGACY_MEMORY_DIR).resolve(),
        ):
            if candidate.exists() and candidate.is_dir() and candidate != canonical:
                try:
                    shadows.append(str(candidate.relative_to(ws)))
                except ValueError:
                    shadows.append(str(candidate))
        warnings: list[str] = []
        if shadows:
            warnings.append(
                "Alternate memory directory(ies) exist under this workspace; "
                f"authoritative durable data for this CLI invocation lives only under {active_rel!r}. "
                "Remove or migrate shadow paths so humans and tooling do not read the wrong tree."
            )
        return {
            "active_memory_root": active_rel,
            "memory_dir_name": self.memory_dir_name,
            "shadow_memory_paths": shadows,
            "warnings": warnings,
        }

    def _ensure_directories(self) -> None:
        for path in [
            self.memory_root,
            self.topics_dir,
            self.events_dir,
            self.transcripts_dir,
            self.candidates_dir,
            self.audit_consolidation_dir,
            self.audit_retrieval_dir,
            self.audit_context_dir,
            self.audit_bootstrap_dir,
            self.audit_dream_dir,
            self.audit_plan_dir,
            self.audit_verifier_dir,
            self.audit_worker_dir,
            self.audit_service_dir,
            self.audit_autowire_dir,
            self.audit_mutation_dir,
            self.annotations_dir,
            self.reviews_dir,
            self.exports_dir,
            self.automation_root,
            self.automation_jobs_dir,
            self.automation_state_dir,
            self.automation_records_dir,
            self.automation_audit_dir,
            self.locks_dir,
            self.state_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def _initialize_default_files(self) -> None:
        if not self.durable_records_path.exists():
            write_json(self.durable_records_path, [])
        if not self.index_json_path.exists():
            write_json(self.index_json_path, {"generated_at": to_iso(utc_now()), "entries": []})
        if not self.observability_index_path.exists():
            write_json(self.observability_index_path, {"generated_at": to_iso(utc_now()), "entities": {}})
        if not self.worker_health_path.exists():
            write_json(self.worker_health_path, {})
        if not self.service_manifest_path.exists():
            write_json(self.service_manifest_path, {})
        if not self.service_runtime_path.exists():
            write_json(self.service_runtime_path, {})
        if not self.memory_md_path.exists():
            atomic_write_text(self.memory_md_path, "# Startup Memory Index\n\n")

    def scheduler_policy(
        self,
        *,
        min_new_events: int | None = None,
        min_interval_seconds: int | None = None,
    ) -> dict[str, int]:
        scheduler = self.load_store_metadata()["scheduler"]
        return {
            "min_new_events": int(min_new_events if min_new_events is not None else scheduler["min_new_events"]),
            "min_interval_seconds": int(
                min_interval_seconds if min_interval_seconds is not None else scheduler["min_interval_seconds"]
            ),
        }

    def dream_policy(
        self,
        *,
        max_recent_episodes: int | None = None,
        min_episode_signals: int | None = None,
    ) -> dict[str, int]:
        dream = self.load_store_metadata()["dream"]
        return {
            "max_recent_episodes": int(
                max_recent_episodes if max_recent_episodes is not None else dream["max_recent_episodes"]
            ),
            "min_episode_signals": int(
                min_episode_signals if min_episode_signals is not None else dream["min_episode_signals"]
            ),
        }

    def lock(self) -> FileLock:
        self.ensure_layout()
        ttl = int(self.config["locks"]["ttl_seconds"])
        return FileLock(self.locks_dir / "consolidator.lock", ttl_seconds=ttl)

    def dream_lock(self) -> FileLock:
        self.ensure_layout()
        ttl = int(self.config["locks"]["ttl_seconds"])
        return FileLock(self.locks_dir / "dream.lock", ttl_seconds=ttl)

    def lock_state(self) -> dict[str, Any]:
        ttl = int(self.config["locks"]["ttl_seconds"])
        return FileLock(self.locks_dir / "consolidator.lock", ttl_seconds=ttl).describe()

    def dream_lock_state(self) -> dict[str, Any]:
        ttl = int(self.config["locks"]["ttl_seconds"])
        return FileLock(self.locks_dir / "dream.lock", ttl_seconds=ttl).describe()

    def dream_worker_lock(self) -> FileLock:
        self.ensure_layout()
        ttl = int(self.config["locks"]["ttl_seconds"])
        return FileLock(self.locks_dir / "dream-worker.lock", ttl_seconds=ttl)

    def dream_worker_lock_state(self) -> dict[str, Any]:
        ttl = int(self.config["locks"]["ttl_seconds"])
        return FileLock(self.locks_dir / "dream-worker.lock", ttl_seconds=ttl).describe()

    def pending_event_count(self) -> int:
        if not self.is_initialized():
            return 0
        processed_ids = self.load_processed_event_ids()
        return sum(1 for event in self.load_events() if event["event_id"] not in processed_ids)

    def status_snapshot(
        self,
        *,
        now: str | None = None,
        min_new_events: int | None = None,
        min_interval_seconds: int | None = None,
    ) -> dict[str, Any]:
        timestamp = now or to_iso(utc_now())
        metadata = self.load_store_metadata()
        if not self.is_initialized():
            return {
                "workspace": str(self.workspace),
                "store_id": metadata["store_id"],
                "store_kind": metadata["store_kind"],
                "initialized": False,
                "state": "uninitialized",
                "pending_events": 0,
                "pending_candidates": 0,
                "last_run_at": None,
                "lock": self.lock_state(),
                "policy": self.scheduler_policy(
                    min_new_events=min_new_events,
                    min_interval_seconds=min_interval_seconds,
                ),
                "dream": {
                    "state": "never_ran",
                    "last_ran_at": None,
                    "last_run_summary": None,
                    "last_run_reason": None,
                    "last_run_duration_ms": None,
                    "last_episode_timestamp": None,
                    "queue_depth": 0,
                    "queued_jobs": [],
                    "lock": self.dream_lock_state(),
                    "worker_lock": self.dream_worker_lock_state(),
                    "worker": {"state": "idle", "processed_jobs": 0},
                    "worker_health": self.load_worker_health(),
                    "policy": metadata["dream"],
                    "transcript_dir": str(self.transcripts_dir),
                    "available_episode_files": 0,
                },
                "automation": self.automation_summary(now=timestamp),
                "next_eligible_reason": "not-initialized",
                "next_eligible_at": None,
            }

        policy = self.scheduler_policy(
            min_new_events=min_new_events,
            min_interval_seconds=min_interval_seconds,
        )
        lock = self.lock_state()
        maintenance_state = self.load_maintenance_state()
        last_run_at = maintenance_state.get("last_run_at")
        pending_events = self.pending_event_count()
        pending_candidates = len(self.load_pending_candidates())
        dream_state = self.load_dream_state()
        dream_queue = self.load_dream_queue()
        dream_worker_state = self.load_dream_worker_state()
        next_eligible_reason = "eligible"
        next_eligible_at = None

        if lock["present"] and not lock["stale"]:
            state = "locked"
            next_eligible_reason = "lock-held"
        elif pending_events > 0 or pending_candidates > 0:
            state = "pending"
        else:
            state = "idle"
            next_eligible_reason = "no-work"

        if last_run_at and policy["min_interval_seconds"] > 0:
            next_run_at = parse_timestamp(last_run_at) + timedelta(seconds=policy["min_interval_seconds"])
            if parse_timestamp(timestamp) < next_run_at:
                next_eligible_reason = "min-interval"
                next_eligible_at = to_iso(next_run_at)

        if state == "pending" and pending_events < policy["min_new_events"] and pending_candidates == 0:
            next_eligible_reason = "min-new-events"

        return {
            "workspace": str(self.workspace),
            "store_id": metadata["store_id"],
            "store_kind": metadata["store_kind"],
            "initialized": True,
            "state": state,
            "pending_events": pending_events,
            "pending_candidates": pending_candidates,
            "last_run_at": last_run_at,
            "lock": lock,
            "policy": policy,
            "dream": {
                "state": dream_state.get("state", "never_ran"),
                "last_ran_at": dream_state.get("last_ran_at"),
                "last_run_summary": dream_state.get("last_run_summary"),
                "last_run_reason": dream_state.get("last_run_reason"),
                "last_run_duration_ms": dream_state.get("last_run_duration_ms"),
                "last_episode_timestamp": dream_state.get("last_episode_timestamp"),
                "queue_depth": len([job for job in dream_queue if job.get("status") == "queued"]),
                "queued_jobs": [job for job in dream_queue if job.get("status") == "queued"][:10],
                "lock": self.dream_lock_state(),
                "worker_lock": self.dream_worker_lock_state(),
                "worker": dream_worker_state or {"state": "idle", "processed_jobs": 0},
                "worker_health": self.load_worker_health(),
                "policy": self.load_store_metadata()["dream"],
                "transcript_dir": str(self.transcripts_dir),
                "available_episode_files": len(list(self.transcripts_dir.glob("*.jsonl"))),
            },
            "automation": self.automation_summary(now=timestamp),
            "next_eligible_reason": next_eligible_reason,
            "next_eligible_at": next_eligible_at,
        }

    def automation_summary(self, *, now: str | None = None) -> dict[str, Any]:
        timestamp = now or to_iso(utc_now())
        if not self.is_initialized():
            return {
                "job_count": 0,
                "enabled_jobs": 0,
                "due_job_ids": [],
                "active_records": 0,
                "stale_records": 0,
                "jobs": [],
            }

        jobs = self.load_automation_jobs()
        records = self.load_automation_records()
        records_by_job: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            records_by_job[str(record.get("job_id", ""))].append(record)

        due_job_ids: list[str] = []
        summaries: list[dict[str, Any]] = []
        for job in jobs:
            job_id = str(job.get("job_id", ""))
            state = self.load_automation_state(job_id)
            interval_seconds = int(job.get("trigger", {}).get("interval_seconds", 0))
            last_run_at = state.get("last_run_at")
            due = bool(job.get("enabled", True))
            if due and last_run_at and interval_seconds > 0:
                next_run_at = parse_timestamp(str(last_run_at)) + timedelta(seconds=interval_seconds)
                due = parse_timestamp(timestamp) >= next_run_at
            if due:
                due_job_ids.append(job_id)
            job_records = records_by_job.get(job_id, [])
            summaries.append(
                {
                    "job_id": job_id,
                    "title": job.get("title"),
                    "enabled": bool(job.get("enabled", True)),
                    "record_type": job.get("output", {}).get("record_type", "generic"),
                    "due": due,
                    "last_run_at": last_run_at,
                    "last_status": state.get("last_status"),
                    "active_records": sum(1 for item in job_records if item.get("status") == "active"),
                    "stale_records": sum(1 for item in job_records if item.get("status") == "stale"),
                }
            )

        return {
            "job_count": len(jobs),
            "enabled_jobs": sum(1 for job in jobs if job.get("enabled", True)),
            "due_job_ids": sorted(due_job_ids),
            "active_records": sum(1 for item in records if item.get("status") == "active"),
            "stale_records": sum(1 for item in records if item.get("status") == "stale"),
            "jobs": sorted(summaries, key=lambda item: item["job_id"]),
        }

    def append_event(self, event: MemoryEvent) -> Path:
        self.ensure_layout()
        payload = event.to_dict()
        validate_document("memory-event.schema.json", payload)
        month = parse_timestamp(event.timestamp).strftime("%Y-%m")
        path = self.events_dir / f"events-{month}.jsonl"
        append_jsonl(path, [payload])
        return path

    def load_events(self) -> list[dict[str, Any]]:
        self.ensure_layout()
        events: list[dict[str, Any]] = []
        for path in sorted(self.events_dir.glob("*.jsonl")):
            events.extend(self._load_jsonl(path))
        return events

    def append_candidates(self, candidates: Iterable[MemoryCandidate], run_id: str) -> Path:
        self.ensure_layout()
        path = self.candidates_dir / f"{run_id}.jsonl"
        rows: list[dict[str, Any]] = []
        for candidate in candidates:
            payload = candidate.to_dict()
            validate_document("memory-candidate.schema.json", payload)
            rows.append(payload)
        append_jsonl(path, rows)
        return path

    def load_pending_candidates(self) -> list[dict[str, Any]]:
        if not self.is_initialized():
            return []
        processed = set(read_json(self.processed_candidates_path, []))
        candidates: list[dict[str, Any]] = []
        for path in sorted(self.candidates_dir.glob("*.jsonl")):
            for item in self._load_jsonl(path):
                if item["candidate_id"] not in processed:
                    candidates.append(item)
        return candidates

    def mark_candidates_processed(self, candidate_ids: Iterable[str]) -> None:
        processed = set(read_json(self.processed_candidates_path, []))
        processed.update(candidate_ids)
        write_json(self.processed_candidates_path, sorted(processed))

    def load_processed_event_ids(self) -> set[str]:
        return set(read_json(self.extraction_state_path, []))

    def mark_events_processed(self, event_ids: Iterable[str]) -> None:
        processed = self.load_processed_event_ids()
        processed.update(event_ids)
        write_json(self.extraction_state_path, sorted(processed))

    def load_durable_records(self) -> list[dict[str, Any]]:
        self.ensure_layout()
        payload = read_json(self.durable_records_path, [])
        return payload if isinstance(payload, list) else []

    def load_startup_index(self) -> dict[str, Any]:
        self.ensure_layout()
        payload = read_json(self.index_json_path, {"generated_at": to_iso(utc_now()), "entries": []})
        return payload if isinstance(payload, dict) else {"generated_at": to_iso(utc_now()), "entries": []}

    def load_maintenance_state(self) -> dict[str, Any]:
        self.ensure_layout()
        payload = read_json(self.maintenance_state_path, {})
        return payload if isinstance(payload, dict) else {}

    def save_maintenance_state(self, payload: dict[str, Any]) -> None:
        self.ensure_layout()
        write_json(self.maintenance_state_path, payload)

    def load_dream_state(self) -> dict[str, Any]:
        self.ensure_layout()
        payload = read_json(self.dream_state_path, {})
        return payload if isinstance(payload, dict) else {}

    def save_dream_state(self, payload: dict[str, Any]) -> None:
        self.ensure_layout()
        write_json(self.dream_state_path, payload)

    def load_dream_queue(self) -> list[dict[str, Any]]:
        self.ensure_layout()
        payload = read_json(self.dream_queue_path, [])
        return payload if isinstance(payload, list) else []

    def save_dream_queue(self, jobs: list[dict[str, Any]]) -> None:
        self.ensure_layout()
        write_json(self.dream_queue_path, jobs)

    def load_dream_worker_state(self) -> dict[str, Any]:
        self.ensure_layout()
        payload = read_json(self.dream_worker_state_path, {})
        return payload if isinstance(payload, dict) else {}

    def save_dream_worker_state(self, payload: dict[str, Any]) -> None:
        self.ensure_layout()
        write_json(self.dream_worker_state_path, payload)

    def load_worker_health(self) -> dict[str, Any]:
        self.ensure_layout()
        payload = read_json(self.worker_health_path, {})
        return payload if isinstance(payload, dict) else {}

    def save_worker_health(self, payload: dict[str, Any]) -> None:
        self.ensure_layout()
        write_json(self.worker_health_path, payload)

    def load_service_manifest(self) -> dict[str, Any]:
        self.ensure_layout()
        payload = read_json(self.service_manifest_path, {})
        return payload if isinstance(payload, dict) else {}

    def save_service_manifest(self, payload: dict[str, Any]) -> None:
        self.ensure_layout()
        write_json(self.service_manifest_path, payload)

    def load_service_runtime(self) -> dict[str, Any]:
        self.ensure_layout()
        payload = read_json(self.service_runtime_path, {})
        return payload if isinstance(payload, dict) else {}

    def save_service_runtime(self, payload: dict[str, Any]) -> None:
        self.ensure_layout()
        write_json(self.service_runtime_path, payload)

    def save_automation_job(self, payload: AutomationJob | dict[str, Any]) -> Path:
        self.ensure_layout()
        serialized = payload.to_dict() if isinstance(payload, AutomationJob) else payload
        validate_document("automation-job.schema.json", serialized)
        job_id = str(serialized["job_id"])
        path = self.automation_jobs_dir / f"{job_id}.json"
        write_json(path, serialized)
        return path

    def load_automation_job(self, job_id: str) -> dict[str, Any]:
        self.ensure_layout()
        payload = read_json(self.automation_jobs_dir / f"{job_id}.json", {})
        return payload if isinstance(payload, dict) else {}

    def load_automation_jobs(self) -> list[dict[str, Any]]:
        self.ensure_layout()
        jobs: list[dict[str, Any]] = []
        for path in sorted(self.automation_jobs_dir.glob("*.json")):
            payload = read_json(path, {})
            if isinstance(payload, dict):
                jobs.append(payload)
        return jobs

    def load_automation_state(self, job_id: str) -> dict[str, Any]:
        self.ensure_layout()
        payload = read_json(self.automation_state_dir / f"{job_id}.json", {})
        return payload if isinstance(payload, dict) else {}

    def save_automation_state(self, job_id: str, payload: dict[str, Any]) -> Path:
        self.ensure_layout()
        path = self.automation_state_dir / f"{job_id}.json"
        write_json(path, payload)
        return path

    def save_automation_records(
        self,
        job_id: str,
        record_type: str,
        records: Sequence[AutomationRecord | dict[str, Any]],
    ) -> Path:
        self.ensure_layout()
        serialized: list[dict[str, Any]] = []
        for record in records:
            payload = record.to_dict() if isinstance(record, AutomationRecord) else record
            validate_document("automation-record.schema.json", payload)
            serialized.append(payload)
        path = self.automation_records_dir / record_type / f"{job_id}.json"
        write_json(path, serialized)
        return path

    def load_automation_records(self, job_id: str | None = None) -> list[dict[str, Any]]:
        self.ensure_layout()
        rows: list[dict[str, Any]] = []
        for path in sorted(self.automation_records_dir.glob("*/*.json")):
            if job_id is not None and path.stem != job_id:
                continue
            payload = read_json(path, [])
            if isinstance(payload, list):
                rows.extend(item for item in payload if isinstance(item, dict))
        return rows

    def write_automation_run_report(self, payload: dict[str, Any]) -> Path:
        self.ensure_layout()
        validate_document("automation-run-report.schema.json", payload)
        report_id = str(
            payload.get(
                "run_id",
                stable_id("automation-run", payload.get("generated_at", to_iso(utc_now()))),
            )
        )
        path = self.automation_audit_dir / f"{report_id}.json"
        write_json(path, payload)
        return path

    def load_observability_index(self) -> dict[str, Any]:
        self.ensure_layout()
        payload = read_json(self.observability_index_path, {"generated_at": to_iso(utc_now()), "entities": {}})
        return payload if isinstance(payload, dict) else {"generated_at": to_iso(utc_now()), "entities": {}}

    def save_observability_index(self, payload: dict[str, Any]) -> None:
        self.ensure_layout()
        write_json(self.observability_index_path, payload)

    def save_durable_records(self, records: list[MemoryRecord]) -> None:
        serialized = [record.to_dict() for record in sorted(records, key=lambda item: item.memory_id)]
        for record in serialized:
            validate_document("memory-topic.schema.json", record)
        write_json(self.durable_records_path, serialized)
        for record in serialized:
            self._write_topic_markdown(record)
        self._write_compat_views(serialized)

    def save_startup_index(self, entries: list[StartupIndexEntry], generated_at: str) -> None:
        policy = self.config["index_policy"]
        limited_entries = entries[: int(policy["max_entries"])]
        payload = {
            "generated_at": generated_at,
            "entries": [entry.to_dict() for entry in limited_entries],
        }
        validate_document("memory-index.schema.json", payload)
        write_json(self.index_json_path, payload)

        lines = ["# Startup Memory Index", "", f"Generated: {generated_at}", ""]
        for entry in limited_entries:
            summary = summarize(entry.summary, int(policy["max_chars_per_summary"]))
            lines.append(f"- [{entry.type}] {entry.title} :: {summary} ({entry.path})")
        atomic_write_text(self.memory_md_path, "\n".join(lines) + "\n")

    def write_consolidation_audit(
        self,
        run_id: str,
        operations: list[ConsolidationOperation],
        summary: dict[str, Any],
        before_snapshot: dict[str, str],
    ) -> dict[str, str]:
        self.ensure_layout()
        op_path = self.audit_consolidation_dir / f"{run_id}.jsonl"
        rows: list[dict[str, Any]] = []
        for operation in operations:
            payload = operation.to_dict()
            validate_document("consolidation-op.schema.json", payload)
            rows.append(payload)
        append_jsonl(op_path, rows)
        return self.write_mutation_audit(
            action="consolidation",
            run_id=run_id,
            target_paths=[op_path, self.durable_records_path, self.index_json_path, self.memory_md_path],
            summary=summary,
            before_snapshot=before_snapshot,
            audit_dir=self.audit_consolidation_dir,
        )

    def write_bootstrap_report(self, run_id: str, report: dict[str, Any]) -> Path:
        path = self.audit_bootstrap_dir / f"{run_id}.json"
        write_json(path, report)
        return path

    def write_retrieval_audit(self, run_id: str, payload: dict[str, Any]) -> Path:
        path = self.audit_retrieval_dir / f"{run_id}.json"
        write_json(path, payload)
        return path

    def write_context_assembly(self, assembly: ContextAssembly) -> Path:
        path = self.audit_context_dir / f"{assembly.context_id}.json"
        write_json(path, assembly.to_dict())
        return path

    def load_context_assemblies(self) -> list[dict[str, Any]]:
        self.ensure_layout()
        assemblies: list[dict[str, Any]] = []
        for path in sorted(self.audit_context_dir.glob("*.json")):
            payload = read_json(path, {})
            if isinstance(payload, dict):
                payload.setdefault("source_path", str(path))
                assemblies.append(payload)
        return assemblies

    def write_dream_audit(
        self,
        run_id: str,
        summary: dict[str, Any],
        before_snapshot: dict[str, str],
    ) -> None:
        self.write_mutation_audit(
            action="dream",
            run_id=run_id,
            target_paths=[self.events_dir, self.durable_records_path, self.index_json_path, self.memory_md_path],
            summary=summary,
            before_snapshot=before_snapshot,
            audit_dir=self.audit_dream_dir,
        )

    def write_plan_audit(self, run_id: str, payload: dict[str, Any]) -> Path:
        path = self.audit_plan_dir / f"{run_id}.json"
        write_json(path, payload)
        return path

    def write_verifier_report(self, run_id: str, payload: dict[str, Any]) -> Path:
        path = self.audit_verifier_dir / f"{run_id}.json"
        write_json(path, payload)
        return path

    def write_worker_audit(
        self,
        run_id: str,
        summary: dict[str, Any],
        before_snapshot: dict[str, str],
    ) -> dict[str, str]:
        return self.write_mutation_audit(
            action="dream-worker",
            run_id=run_id,
            target_paths=[self.dream_queue_path, self.dream_worker_state_path, self.dream_state_path],
            summary=summary,
            before_snapshot=before_snapshot,
            audit_dir=self.audit_worker_dir,
        )

    def write_service_report(self, payload: dict[str, Any]) -> Path:
        report_id = str(payload.get("report_id", stable_id("service", payload.get("generated_at", to_iso(utc_now())))))
        path = self.audit_service_dir / f"{report_id}.json"
        write_json(path, payload)
        return path

    def write_autowire_report(self, payload: dict[str, Any]) -> Path:
        report_id = stable_id("autowire", payload.get("workspace", ""), payload.get("generated_at", to_iso(utc_now())))
        path = self.audit_autowire_dir / f"{report_id}.json"
        write_json(path, payload)
        return path

    def append_annotation(self, annotation: Annotation) -> Path:
        path = self.annotations_dir / f"{annotation.created_at[:10]}.jsonl"
        append_jsonl(path, [annotation.to_dict()])
        return path

    def load_annotations(self) -> list[dict[str, Any]]:
        self.ensure_layout()
        rows: list[dict[str, Any]] = []
        for path in sorted(self.annotations_dir.glob("*.jsonl")):
            rows.extend(self._load_jsonl(path))
        return rows

    def append_review_decision(self, decision: ReviewDecision) -> Path:
        path = self.reviews_dir / f"{decision.created_at[:10]}.jsonl"
        append_jsonl(path, [decision.to_dict()])
        return path

    def load_review_decisions(self) -> list[dict[str, Any]]:
        self.ensure_layout()
        rows: list[dict[str, Any]] = []
        for path in sorted(self.reviews_dir.glob("*.jsonl")):
            rows.extend(self._load_jsonl(path))
        return rows

    def write_export_record(self, export_id: str, payload: dict[str, Any]) -> Path:
        path = self.exports_dir / f"{export_id}.json"
        write_json(path, payload)
        return path

    def load_export_records(self) -> list[dict[str, Any]]:
        self.ensure_layout()
        rows: list[dict[str, Any]] = []
        for path in sorted(self.exports_dir.glob("*.json")):
            payload = read_json(path, {})
            if isinstance(payload, dict):
                payload.setdefault("source_path", str(path))
                rows.append(payload)
        return rows

    def write_mutation_audit(
        self,
        *,
        action: str,
        run_id: str,
        target_paths: list[Path],
        summary: dict[str, Any],
        before_snapshot: dict[str, str],
        audit_dir: Path | None = None,
    ) -> dict[str, str]:
        destination = audit_dir or self.audit_mutation_dir
        self.ensure_layout()
        summary_payload = {
            "action": action,
            "run_id": run_id,
            "workspace": str(self.workspace),
            "memory_root": str(self.memory_root),
            "target_paths": [
                str(path.relative_to(self.workspace)) if path.is_absolute() and path.exists() else str(path)
                for path in target_paths
            ],
            "summary": summary,
        }
        summary_path = destination / f"{run_id}-summary.json"
        write_json(summary_path, summary_payload)

        after_snapshot = self.snapshot_store_text()
        diff_lines: list[str] = []
        for relative_path in sorted(set(before_snapshot) | set(after_snapshot)):
            before = before_snapshot.get(relative_path, "").splitlines(keepends=True)
            after = after_snapshot.get(relative_path, "").splitlines(keepends=True)
            if before == after:
                continue
            diff_lines.extend(
                difflib.unified_diff(
                    before,
                    after,
                    fromfile=f"before/{relative_path}",
                    tofile=f"after/{relative_path}",
                )
            )
        diff_path = destination / f"{run_id}.diff"
        atomic_write_text(diff_path, "".join(diff_lines))
        return {
            "summary_path": str(summary_path.relative_to(self.workspace)),
            "diff_path": str(diff_path.relative_to(self.workspace)),
        }

    def snapshot_store_text(self) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        if not self.memory_root.exists():
            return snapshot
        for path in sorted(self.memory_root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in {".md", ".json", ".jsonl", ".diff"}:
                continue
            snapshot[str(path.relative_to(self.workspace))] = path.read_text(encoding="utf-8")
        return snapshot

    def snapshot_memory_text(self) -> dict[str, str]:
        return self.snapshot_store_text()

    def iter_memory_paths(self) -> list[Path]:
        if not self.memory_root.exists():
            return []
        return [path for path in self.memory_root.rglob("*") if path.is_file()]

    def _write_topic_markdown(self, record: dict[str, Any]) -> None:
        path = self.topics_dir / f"{record['memory_id']}.md"
        ensure_relative_to(path, self.memory_root)
        lines = [
            f"# {record['title']}",
            "",
            f"- memory_id: {record['memory_id']}",
            f"- type: {record['type']}",
            f"- scope: {record['scope']}",
            f"- status: {record['status']}",
            f"- confidence: {record['confidence']}",
            f"- salience: {record['salience']}",
            f"- updated_at: {record['updated_at']}",
            "",
            "## Summary",
            record["summary"],
            "",
            "## Body",
            record["body"],
            "",
            "## Provenance",
        ]
        for event_id in record["source_event_ids"]:
            lines.append(f"- {event_id}")
        if record["supersedes"]:
            lines.extend(["", "## Supersedes"])
            lines.extend(f"- {item}" for item in record["supersedes"])
        if record["conflicts_with"]:
            lines.extend(["", "## Conflicts"])
            lines.extend(f"- {item}" for item in record["conflicts_with"])
        atomic_write_text(path, "\n".join(lines) + "\n")

    def _write_compat_views(self, records: list[dict[str, Any]]) -> None:
        if self.compat_mode != "autodream":
            return
        grouped = {
            "project.md": [
                record
                for record in records
                if record["status"] == "active" and record["scope"] == "project"
            ],
            "user.md": [
                record
                for record in records
                if record["status"] == "active" and record["scope"] in {"user", "global"}
            ],
        }
        for filename, selected in grouped.items():
            lines = [f"# {filename.replace('.md', '').title()} Memory", ""]
            for record in selected:
                lines.append(f"- [{record['type']}] {record['title']} :: {record['summary']}")
            atomic_write_text(self.memory_root / filename, "\n".join(lines).rstrip() + "\n")

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows


def store_sort_key(store: MemoryStore) -> tuple[int, str]:
    return (STORE_KIND_PRECEDENCE.get(store.store_kind, 99), str(store.workspace))


def load_store_group_manifest(path: Path) -> list[MemoryStore]:
    manifest_path = Path(path).expanduser()
    payload = read_json(manifest_path, {})
    stores_payload = payload.get("stores")
    if not isinstance(stores_payload, list):
        raise ValueError("stores manifest must contain a 'stores' array")

    stores: list[MemoryStore] = []
    seen: set[tuple[str, str]] = set()
    for item in stores_payload:
        if not isinstance(item, dict):
            raise ValueError("each manifest store entry must be an object")
        workspace_value = item.get("workspace")
        if not isinstance(workspace_value, str) or not workspace_value.strip():
            raise ValueError("each manifest store entry must include a workspace")
        store_kind = item.get("store_kind")
        if store_kind is not None and store_kind not in VALID_STORE_KINDS:
            raise ValueError(f"unsupported store kind in manifest: {store_kind}")
        workspace = Path(workspace_value).expanduser()
        if not workspace.is_absolute():
            workspace = (manifest_path.parent / workspace).resolve()
        store = MemoryStore(workspace, store_kind_hint=store_kind)
        key = (str(store.workspace), store.store_kind)
        if key in seen:
            continue
        seen.add(key)
        stores.append(store)

    return sorted(stores, key=store_sort_key)
