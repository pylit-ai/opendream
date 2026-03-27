from __future__ import annotations

import difflib
import json
import os
import time
from contextlib import AbstractContextManager
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable

from .models import ConsolidationOperation, MemoryCandidate, MemoryEvent, MemoryRecord, StartupIndexEntry
from .util import ensure_relative_to, parse_timestamp, read_json, stable_id, summarize, to_iso, utc_now, write_json
from .validation import validate_document


DEFAULT_CONFIG: dict[str, Any] = {
    "locks": {"ttl_seconds": 1800},
    "index_policy": {"max_entries": 40, "max_chars_per_summary": 140},
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
                raise LockError(f"lock already held: {self.path}")
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

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, exc_tb: object) -> None:
        self.release()


class MemoryStore:
    def __init__(self, workspace: Path, config: dict[str, Any] | None = None, store_kind_hint: str | None = None) -> None:
        self.workspace = Path(workspace).expanduser()
        self.memory_root = self.workspace / "memory"
        self.config = _deep_merge(DEFAULT_CONFIG, config or {})
        self.store_kind_hint = store_kind_hint
        self.topics_dir = self.memory_root / "topics"
        self.events_dir = self.memory_root / "state" / "events"
        self.candidates_dir = self.memory_root / "state" / "candidates"
        self.audit_consolidation_dir = self.memory_root / "audit" / "consolidation"
        self.audit_retrieval_dir = self.memory_root / "audit" / "retrieval"
        self.audit_bootstrap_dir = self.memory_root / "audit" / "bootstrap"
        self.locks_dir = self.memory_root / "locks"
        self.state_dir = self.memory_root / "state"
        self.durable_records_path = self.state_dir / "durable_records.json"
        self.index_json_path = self.state_dir / "index.json"
        self.memory_md_path = self.memory_root / "MEMORY.md"
        self.processed_candidates_path = self.state_dir / "processed_candidates.json"
        self.extraction_state_path = self.state_dir / "processed_events.json"
        self.maintenance_state_path = self.state_dir / "maintenance_state.json"
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
            "scheduler": {
                "min_new_events": int(scheduler["min_new_events"]),
                "min_interval_seconds": int(scheduler["min_interval_seconds"]),
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
        return merged

    @property
    def store_kind(self) -> str:
        return str(self.load_store_metadata()["store_kind"])

    @property
    def store_id(self) -> str:
        return str(self.load_store_metadata()["store_id"])

    def initialize(self, *, store_kind: str = "project") -> dict[str, Any]:
        metadata = self.load_store_metadata()
        metadata["store_kind"] = store_kind
        metadata["store_id"] = stable_id("store", self.workspace.resolve(), store_kind)
        metadata["workspace"] = str(self.workspace)
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

    def _ensure_directories(self) -> None:
        for path in [
            self.memory_root,
            self.topics_dir,
            self.events_dir,
            self.candidates_dir,
            self.audit_consolidation_dir,
            self.audit_retrieval_dir,
            self.audit_bootstrap_dir,
            self.locks_dir,
            self.state_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def _initialize_default_files(self) -> None:
        if not self.durable_records_path.exists():
            write_json(self.durable_records_path, [])
        if not self.index_json_path.exists():
            write_json(self.index_json_path, {"generated_at": to_iso(utc_now()), "entries": []})
        if not self.memory_md_path.exists():
            self.memory_md_path.write_text("# Startup Memory Index\n\n", encoding="utf-8")

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

    def lock(self) -> FileLock:
        self.ensure_layout()
        ttl = int(self.config["locks"]["ttl_seconds"])
        return FileLock(self.locks_dir / "consolidator.lock", ttl_seconds=ttl)

    def lock_state(self) -> dict[str, Any]:
        ttl = int(self.config["locks"]["ttl_seconds"])
        return FileLock(self.locks_dir / "consolidator.lock", ttl_seconds=ttl).describe()

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
            "next_eligible_reason": next_eligible_reason,
            "next_eligible_at": next_eligible_at,
        }

    def append_event(self, event: MemoryEvent) -> Path:
        self.ensure_layout()
        payload = event.to_dict()
        validate_document("memory-event.schema.json", payload)
        month = parse_timestamp(event.timestamp).strftime("%Y-%m")
        path = self.events_dir / f"events-{month}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
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
        with path.open("a", encoding="utf-8") as handle:
            for candidate in candidates:
                payload = candidate.to_dict()
                validate_document("memory-candidate.schema.json", payload)
                handle.write(json.dumps(payload, sort_keys=True) + "\n")
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
        return read_json(self.durable_records_path, [])

    def load_startup_index(self) -> dict[str, Any]:
        self.ensure_layout()
        return read_json(self.index_json_path, {"generated_at": to_iso(utc_now()), "entries": []})

    def load_maintenance_state(self) -> dict[str, Any]:
        self.ensure_layout()
        return read_json(self.maintenance_state_path, {})

    def save_maintenance_state(self, payload: dict[str, Any]) -> None:
        self.ensure_layout()
        write_json(self.maintenance_state_path, payload)

    def save_durable_records(self, records: list[MemoryRecord]) -> None:
        serialized = [record.to_dict() for record in sorted(records, key=lambda item: item.memory_id)]
        for record in serialized:
            validate_document("memory-topic.schema.json", record)
        write_json(self.durable_records_path, serialized)
        for record in serialized:
            self._write_topic_markdown(record)

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
        self.memory_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_consolidation_audit(
        self,
        run_id: str,
        operations: list[ConsolidationOperation],
        summary: dict[str, Any],
        before_snapshot: dict[str, str],
    ) -> None:
        self.ensure_layout()
        op_path = self.audit_consolidation_dir / f"{run_id}.jsonl"
        with op_path.open("w", encoding="utf-8") as handle:
            for operation in operations:
                payload = operation.to_dict()
                validate_document("consolidation-op.schema.json", payload)
                handle.write(json.dumps(payload, sort_keys=True) + "\n")
        write_json(self.audit_consolidation_dir / f"{run_id}-summary.json", summary)

        after_snapshot = self.snapshot_memory_text()
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
        (self.audit_consolidation_dir / f"{run_id}.diff").write_text("".join(diff_lines), encoding="utf-8")

    def write_bootstrap_report(self, run_id: str, report: dict[str, Any]) -> Path:
        path = self.audit_bootstrap_dir / f"{run_id}.json"
        write_json(path, report)
        return path

    def write_retrieval_audit(self, run_id: str, payload: dict[str, Any]) -> Path:
        path = self.audit_retrieval_dir / f"{run_id}.json"
        write_json(path, payload)
        return path

    def snapshot_memory_text(self) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        if self.memory_md_path.exists():
            snapshot[str(self.memory_md_path.relative_to(self.workspace))] = self.memory_md_path.read_text(encoding="utf-8")
        for path in sorted(self.topics_dir.glob("*.md")):
            snapshot[str(path.relative_to(self.workspace))] = path.read_text(encoding="utf-8")
        return snapshot

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
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

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
