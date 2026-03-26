from __future__ import annotations

import difflib
import json
import os
import time
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Iterable

from .models import ConsolidationOperation, MemoryCandidate, MemoryEvent, MemoryRecord, StartupIndexEntry
from .util import ensure_relative_to, parse_timestamp, read_json, summarize, to_iso, utc_now, write_json
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
}


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

    def _is_stale(self) -> bool:
        if not self.path.exists():
            return False
        age_seconds = time.time() - self.path.stat().st_mtime
        return age_seconds > self.ttl_seconds

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
    def __init__(self, workspace: Path, config: dict[str, Any] | None = None) -> None:
        self.workspace = workspace
        self.memory_root = workspace / "memory"
        self.config = DEFAULT_CONFIG | (config or {})
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

    def ensure_layout(self) -> None:
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
        if not self.durable_records_path.exists():
            write_json(self.durable_records_path, [])
        if not self.index_json_path.exists():
            write_json(self.index_json_path, {"generated_at": to_iso(utc_now()), "entries": []})
        if not self.memory_md_path.exists():
            self.memory_md_path.write_text("# Startup Memory Index\n\n", encoding="utf-8")

    def lock(self) -> FileLock:
        ttl = int(self.config["locks"]["ttl_seconds"])
        return FileLock(self.locks_dir / "consolidator.lock", ttl_seconds=ttl)

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
