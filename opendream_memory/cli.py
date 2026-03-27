from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import __version__
from .bootstrap import bootstrap_index
from .consolidator import consolidate
from .extractor import extract_candidates
from .integration import emit_event, maintain, maintain_stores, prepare_context, status, status_stores, tick, tick_stores
from .models import MemoryEvent
from .retriever import retrieve
from .storage import MemoryStore, VALID_STORE_KINDS, load_store_group_manifest, store_sort_key
from .util import FIXTURE_ROOT, json_dumps, stable_id, to_iso, utc_now
from .validation import validate_document


def load_event_payloads(path: Path) -> list[dict[str, Any]]:
    text = path.expanduser().read_text(encoding="utf-8").strip()
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


def build_store(workspace: str, *, store_kind_hint: str | None = None) -> MemoryStore:
    hint = store_kind_hint if store_kind_hint in VALID_STORE_KINDS else None
    return MemoryStore(Path(workspace), store_kind_hint=hint)


def add_store_group_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--stores-manifest")
    parser.add_argument("--include-global", action="store_true")
    parser.add_argument("--global-workspace")
    parser.add_argument("--include-project", action="store_true")
    parser.add_argument("--project-workspace")


def resolve_store_group(args: argparse.Namespace) -> list[MemoryStore]:
    if getattr(args, "stores_manifest", None):
        return load_store_group_manifest(Path(args.stores_manifest))

    stores: list[MemoryStore] = []
    seen: set[str] = set()

    def add_store(store: MemoryStore) -> None:
        key = str(store.workspace)
        if key in seen:
            return
        seen.add(key)
        stores.append(store)

    primary = build_store(args.workspace)
    add_store(primary)

    include_global = getattr(args, "include_global", False)
    global_workspace = getattr(args, "global_workspace", None)
    if include_global:
        if global_workspace:
            add_store(build_store(global_workspace, store_kind_hint="global"))
        elif primary.store_kind != "global":
            raise ValueError("--include-global requires --global-workspace when the primary store is not global")

    include_project = getattr(args, "include_project", False)
    project_workspace = getattr(args, "project_workspace", None)
    if include_project:
        if project_workspace:
            add_store(build_store(project_workspace, store_kind_hint="project"))
        elif primary.store_kind != "project":
            raise ValueError("--include-project requires --project-workspace when the primary store is not project")

    return sorted(stores, key=store_sort_key)


def resolve_emit_target(args: argparse.Namespace) -> MemoryStore:
    route = args.route
    if route == "global":
        if args.global_workspace:
            target = build_store(args.global_workspace, store_kind_hint="global")
            if not target.is_initialized():
                target.initialize(store_kind="global")
            return target
        target = build_store(args.workspace)
        if target.store_kind != "global":
            raise ValueError("--route global requires --global-workspace or a global primary workspace")
        return target

    target = build_store(args.workspace)
    if not target.is_initialized():
        target.initialize(store_kind="project")
    return target


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(args.workspace, store_kind_hint=args.store_kind)
    metadata = store.initialize(store_kind=args.store_kind)
    return {
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "store_id": metadata["store_id"],
        "store_kind": metadata["store_kind"],
        "status": "initialized",
    }


def command_append_event(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(args.workspace)
    store.ensure_layout()
    event_payloads = load_event_payloads(Path(args.events))
    written = []
    for payload in event_payloads:
        validate_document("memory-event.schema.json", payload)
        path = store.append_event(MemoryEvent(**payload))
        written.append(str(path.relative_to(store.workspace)))
    return {"workspace": str(store.workspace), "written_files": sorted(set(written)), "events": len(event_payloads)}


def command_emit_event(args: argparse.Namespace) -> dict[str, Any]:
    store = resolve_emit_target(args)
    return emit_event(
        store,
        kind=args.kind,
        content=args.content,
        scope=args.scope,
        channel=args.channel,
        message_ref=args.message_ref,
        session_id=args.session_id,
        turn_id=args.turn_id,
        event_id=args.event_id,
        timestamp=args.timestamp,
        tags=args.tag,
        confidence_hint=args.confidence_hint,
        sensitivity=args.sensitivity,
    )


def command_extract(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(args.workspace)
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
    store = build_store(args.workspace)
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
    store = build_store(args.workspace)
    store.ensure_layout()
    result = consolidate(store, now=args.now, sleep_before_write=args.sleep_before_write)
    result["workspace"] = str(store.workspace)
    return result


def command_retrieve(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(args.workspace)
    store.ensure_layout()
    response = retrieve(store, query=args.query, limit=args.limit, now=args.now, include_contested=args.include_contested)
    response["workspace"] = str(store.workspace)
    return response


def command_maintain(args: argparse.Namespace) -> dict[str, Any]:
    stores = resolve_store_group(args)
    if len(stores) > 1 or args.stores_manifest:
        return maintain_stores(
            stores,
            now=args.now,
            min_new_events=args.min_new_events,
            min_interval_seconds=args.min_interval_seconds,
        )
    return maintain(
        stores[0],
        now=args.now,
        min_new_events=args.min_new_events,
        min_interval_seconds=args.min_interval_seconds,
    )


def command_prepare_context(args: argparse.Namespace) -> dict[str, Any]:
    stores = resolve_store_group(args)
    return prepare_context(stores if len(stores) > 1 or args.stores_manifest else stores[0], query=args.query, limit=args.limit, now=args.now)


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    stores = resolve_store_group(args)
    if len(stores) > 1 or args.stores_manifest:
        return status_stores(
            stores,
            now=args.now,
            min_new_events=args.min_new_events,
            min_interval_seconds=args.min_interval_seconds,
        )
    return status(
        stores[0],
        now=args.now,
        min_new_events=args.min_new_events,
        min_interval_seconds=args.min_interval_seconds,
    )


def command_tick(args: argparse.Namespace) -> dict[str, Any]:
    stores = resolve_store_group(args)
    if len(stores) > 1 or args.stores_manifest:
        return tick_stores(
            stores,
            now=args.now,
            min_new_events=args.min_new_events,
            min_interval_seconds=args.min_interval_seconds,
        )
    return tick(
        stores[0],
        now=args.now,
        min_new_events=args.min_new_events,
        min_interval_seconds=args.min_interval_seconds,
    )


def command_demo(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace)
    store = build_store(str(workspace), store_kind_hint="project")
    store.ensure_layout()
    fixture = FIXTURE_ROOT / "golden_events.jsonl"
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
        "fixture": fixture.name,
        "events_appended": len(events),
        "extract": extraction,
        "consolidate": consolidation,
        "retrieve": retrieval,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opendream-memory")
    parser.add_argument("--version", action="version", version=f"opendream-memory {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--workspace", required=True)
    init_parser.add_argument("--store-kind", choices=sorted(VALID_STORE_KINDS), default="project")
    init_parser.set_defaults(func=command_init)

    append_parser = subparsers.add_parser("append-event")
    append_parser.add_argument("--workspace", required=True)
    append_parser.add_argument("--events", required=True, help="JSON, JSON array, or JSONL file")
    append_parser.set_defaults(func=command_append_event)

    emit_parser = subparsers.add_parser("emit-event")
    emit_parser.add_argument("--workspace", required=True)
    emit_parser.add_argument("--kind", required=True)
    emit_parser.add_argument("--content", required=True)
    emit_parser.add_argument("--scope", default="project")
    emit_parser.add_argument("--channel", default="cli")
    emit_parser.add_argument("--message-ref", required=True)
    emit_parser.add_argument("--session-id")
    emit_parser.add_argument("--turn-id")
    emit_parser.add_argument("--event-id")
    emit_parser.add_argument("--timestamp")
    emit_parser.add_argument("--tag", action="append", default=[])
    emit_parser.add_argument("--confidence-hint", type=float)
    emit_parser.add_argument("--sensitivity", default="normal")
    emit_parser.add_argument("--route", choices=["project", "global"], default="project")
    emit_parser.add_argument("--global-workspace")
    emit_parser.set_defaults(func=command_emit_event)

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

    maintain_parser = subparsers.add_parser("maintain")
    maintain_parser.add_argument("--workspace", required=True)
    maintain_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    maintain_parser.add_argument("--min-new-events", type=int)
    maintain_parser.add_argument("--min-interval-seconds", type=int)
    add_store_group_arguments(maintain_parser)
    maintain_parser.set_defaults(func=command_maintain)

    retrieve_parser = subparsers.add_parser("retrieve")
    retrieve_parser.add_argument("--workspace", required=True)
    retrieve_parser.add_argument("--query", required=True)
    retrieve_parser.add_argument("--limit", type=int, default=5)
    retrieve_parser.add_argument("--include-contested", action="store_true")
    retrieve_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    retrieve_parser.set_defaults(func=command_retrieve)

    prepare_context_parser = subparsers.add_parser("prepare-context")
    prepare_context_parser.add_argument("--workspace", required=True)
    prepare_context_parser.add_argument("--query", required=True)
    prepare_context_parser.add_argument("--limit", type=int, default=5)
    prepare_context_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    add_store_group_arguments(prepare_context_parser)
    prepare_context_parser.set_defaults(func=command_prepare_context)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--workspace", required=True)
    status_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    status_parser.add_argument("--min-new-events", type=int)
    status_parser.add_argument("--min-interval-seconds", type=int)
    add_store_group_arguments(status_parser)
    status_parser.set_defaults(func=command_status)

    tick_parser = subparsers.add_parser("tick")
    tick_parser.add_argument("--workspace", required=True)
    tick_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    tick_parser.add_argument("--min-new-events", type=int)
    tick_parser.add_argument("--min-interval-seconds", type=int)
    add_store_group_arguments(tick_parser)
    tick_parser.set_defaults(func=command_tick)

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
