from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .bootstrap import bootstrap_index
from .consolidator import consolidate
from .extractor import extract_candidates
from .models import MemoryEvent
from .storage import MemoryStore
from .util import REPO_ROOT, json_dumps, stable_id, to_iso, utc_now
from .validation import validate_document
from .retriever import retrieve


def load_event_payloads(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        payload = json.loads(text)
        return payload if isinstance(payload, list) else [payload]
    if text.startswith("{") and "\n" not in text:
        payload = json.loads(text)
        return payload if isinstance(payload, list) else [payload]
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        rows.append(json.loads(line))
    return rows


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    store = MemoryStore(Path(args.workspace))
    store.ensure_layout()
    return {"workspace": str(store.workspace), "memory_root": str(store.memory_root), "status": "initialized"}


def command_append_event(args: argparse.Namespace) -> dict[str, Any]:
    store = MemoryStore(Path(args.workspace))
    store.ensure_layout()
    event_payloads = load_event_payloads(Path(args.events))
    written = []
    for payload in event_payloads:
        validate_document("memory-event.schema.json", payload)
        path = store.append_event(MemoryEvent(**payload))
        written.append(str(path.relative_to(store.workspace)))
    return {"workspace": str(store.workspace), "written_files": sorted(set(written)), "events": len(event_payloads)}


def command_extract(args: argparse.Namespace) -> dict[str, Any]:
    store = MemoryStore(Path(args.workspace))
    store.ensure_layout()
    if args.events:
        events = load_event_payloads(Path(args.events))
        event_ids = [event["event_id"] for event in events]
    else:
        processed = store.load_processed_event_ids()
        events = [event for event in store.load_events() if event["event_id"] not in processed]
        event_ids = [event["event_id"] for event in events]
    created_at = args.now or to_iso(utc_now())
    candidates = extract_candidates(events, origin_mode="scheduled", now=created_at)
    run_id = stable_id("extract", created_at, len(candidates), len(events))
    if candidates:
        store.append_candidates(candidates, run_id)
    if not args.events:
        store.mark_events_processed(event_ids)
    return {
        "workspace": str(store.workspace),
        "run_id": run_id,
        "processed_events": len(events),
        "created_candidates": len(candidates),
    }


def command_bootstrap_index(args: argparse.Namespace) -> dict[str, Any]:
    store = MemoryStore(Path(args.workspace))
    store.ensure_layout()
    events = load_event_payloads(Path(args.events))
    report = bootstrap_index(store, events, now=args.now)
    return {
        "workspace": str(store.workspace),
        "run_id": report["run_id"],
        "categories": len(report["categories"]),
        "candidates": len(report["candidates"]),
        "raw_only_ids": len(report["raw_only_ids"]),
        "quarantine_ids": len(report["quarantine_ids"]),
    }


def command_consolidate(args: argparse.Namespace) -> dict[str, Any]:
    store = MemoryStore(Path(args.workspace))
    store.ensure_layout()
    result = consolidate(store, now=args.now, sleep_before_write=args.sleep_before_write)
    result["workspace"] = str(store.workspace)
    return result


def command_retrieve(args: argparse.Namespace) -> dict[str, Any]:
    store = MemoryStore(Path(args.workspace))
    store.ensure_layout()
    response = retrieve(store, query=args.query, limit=args.limit, now=args.now, include_contested=args.include_contested)
    response["workspace"] = str(store.workspace)
    return response


def command_demo(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace)
    store = MemoryStore(workspace)
    store.ensure_layout()
    fixture = REPO_ROOT / "tests" / "fixtures" / "golden_events.jsonl"
    events = load_event_payloads(fixture)
    for event in events:
        validate_document("memory-event.schema.json", event)
        store.append_event(MemoryEvent(**event))

    extraction = command_extract(argparse.Namespace(workspace=str(workspace), events=None, now=args.now))
    consolidation = command_consolidate(
        argparse.Namespace(workspace=str(workspace), now=args.now, sleep_before_write=0.0)
    )
    retrieval = command_retrieve(
        argparse.Namespace(
            workspace=str(workspace),
            query="What package manager, workflow, and environment requirements should I use?",
            limit=5,
            now=args.now,
            include_contested=False,
        )
    )
    return {
        "workspace": str(workspace),
        "memory_root": str(store.memory_root),
        "fixture": str(fixture.relative_to(REPO_ROOT)),
        "events_appended": len(events),
        "extract": extraction,
        "consolidate": consolidation,
        "retrieve": retrieval,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opendream-memory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--workspace", required=True)
    init_parser.set_defaults(func=command_init)

    append_parser = subparsers.add_parser("append-event")
    append_parser.add_argument("--workspace", required=True)
    append_parser.add_argument("--events", required=True, help="JSON, JSON array, or JSONL file")
    append_parser.set_defaults(func=command_append_event)

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("--workspace", required=True)
    extract_parser.add_argument("--events", help="Optional JSON, JSON array, or JSONL file")
    extract_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    extract_parser.set_defaults(func=command_extract)

    bootstrap_parser = subparsers.add_parser("bootstrap-index")
    bootstrap_parser.add_argument("--workspace", required=True)
    bootstrap_parser.add_argument("--events", required=True)
    bootstrap_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    bootstrap_parser.set_defaults(func=command_bootstrap_index)

    consolidate_parser = subparsers.add_parser("consolidate")
    consolidate_parser.add_argument("--workspace", required=True)
    consolidate_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    consolidate_parser.add_argument("--sleep-before-write", type=float, default=0.0, help=argparse.SUPPRESS)
    consolidate_parser.set_defaults(func=command_consolidate)

    retrieve_parser = subparsers.add_parser("retrieve")
    retrieve_parser.add_argument("--workspace", required=True)
    retrieve_parser.add_argument("--query", required=True)
    retrieve_parser.add_argument("--limit", type=int, default=5)
    retrieve_parser.add_argument("--include-contested", action="store_true")
    retrieve_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    retrieve_parser.set_defaults(func=command_retrieve)

    demo_parser = subparsers.add_parser("demo")
    demo_parser.add_argument("--workspace", required=True)
    demo_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    demo_parser.set_defaults(func=command_demo)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    print(json_dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
