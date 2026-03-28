from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, NoReturn

from . import __version__
from .bootstrap import bootstrap_index
from .consolidator import consolidate
from .dream import dream_run, dream_tick, dream_worker, enqueue_dream_job
from .evaluation import run_dream_fidelity_eval, run_memory_quality_eval
from .extractor import extract_candidates
from .integration import (
    emit_event,
    maintain,
    maintain_stores,
    prepare_context,
    status,
    status_stores,
    tick,
    tick_stores,
)
from .models import MemoryEvent
from .observability import index_observability
from .retriever import retrieve
from .storage import VALID_STORE_KINDS, MemoryStore, load_store_group_manifest, store_sort_key
from .util import FIXTURE_ROOT, json_dumps, stable_id, to_iso, utc_now
from .validation import validate_document
from .webapp import build_server

TOP_LEVEL_EXAMPLES = """Examples:
  opendream init --workspace .tmp/ws
  opendream demo --workspace .tmp/ws
  opendream dream worker --workspace .tmp/ws --once
"""


class OpenDreamArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        detail = f"{self.prog}: error: {message}\n"
        hint = _error_hint(self.prog, message)
        if hint:
            detail += f"Hint: {hint}\n"
        self.exit(2, detail)


def _error_hint(prog: str, message: str) -> str | None:
    if prog == "opendream" and "required: command" in message:
        return (
            "try `opendream init --workspace .tmp/ws` or "
            "`opendream demo --workspace .tmp/ws`; use `opendream -h` "
            "for the full command tree"
        )
    if prog == "opendream dream" and "required: dream_command" in message:
        return "try `opendream dream status --workspace .tmp/ws` or `opendream dream worker --workspace .tmp/ws --once`"
    return None


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


def build_store(
    workspace: str,
    *,
    store_kind_hint: str | None = None,
    memory_dir: str | None = None,
    compat_mode: str | None = None,
) -> MemoryStore:
    hint = store_kind_hint if store_kind_hint in VALID_STORE_KINDS else None
    return MemoryStore(Path(workspace), store_kind_hint=hint, memory_dir=memory_dir, compat_mode=compat_mode)


def resolve_episode_paths(store: MemoryStore, paths: list[str] | None) -> list[Path]:
    if paths:
        return [Path(path).expanduser() for path in paths]
    store.ensure_layout()
    return sorted(store.transcripts_dir.glob("*.jsonl"))


def add_layout_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--memory-dir", help="Relative directory under the workspace for memory artifacts")
    parser.add_argument("--compat-mode", choices=["canonical", "autodream"], default=None)


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

    primary = build_store(
        args.workspace,
        memory_dir=getattr(args, "memory_dir", None),
        compat_mode=getattr(args, "compat_mode", None),
    )
    add_store(primary)

    include_global = getattr(args, "include_global", False)
    global_workspace = getattr(args, "global_workspace", None)
    if include_global:
        if global_workspace:
            add_store(
                build_store(
                    global_workspace,
                    store_kind_hint="global",
                    memory_dir=getattr(args, "memory_dir", None),
                    compat_mode=getattr(args, "compat_mode", None),
                )
            )
        elif primary.store_kind != "global":
            raise ValueError("--include-global requires --global-workspace when the primary store is not global")

    include_project = getattr(args, "include_project", False)
    project_workspace = getattr(args, "project_workspace", None)
    if include_project:
        if project_workspace:
            add_store(
                build_store(
                    project_workspace,
                    store_kind_hint="project",
                    memory_dir=getattr(args, "memory_dir", None),
                    compat_mode=getattr(args, "compat_mode", None),
                )
            )
        elif primary.store_kind != "project":
            raise ValueError("--include-project requires --project-workspace when the primary store is not project")

    return sorted(stores, key=store_sort_key)


def resolve_emit_target(args: argparse.Namespace) -> MemoryStore:
    route = args.route
    if route == "global":
        if args.global_workspace:
            target = build_store(
                args.global_workspace,
                store_kind_hint="global",
                memory_dir=args.memory_dir,
                compat_mode=args.compat_mode,
            )
            if not target.is_initialized():
                target.initialize(store_kind="global", compat_mode=args.compat_mode)
            return target
        target = build_store(args.workspace, memory_dir=args.memory_dir, compat_mode=args.compat_mode)
        if target.store_kind != "global":
            raise ValueError("--route global requires --global-workspace or a global primary workspace")
        return target

    target = build_store(args.workspace, memory_dir=args.memory_dir, compat_mode=args.compat_mode)
    if not target.is_initialized():
        target.initialize(store_kind="project", compat_mode=args.compat_mode)
    return target


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(
        args.workspace,
        store_kind_hint=args.store_kind,
        memory_dir=args.memory_dir,
        compat_mode=args.compat_mode,
    )
    metadata = store.initialize(store_kind=args.store_kind, compat_mode=args.compat_mode)
    return {
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "store_id": metadata["store_id"],
        "store_kind": metadata["store_kind"],
        "compat_mode": metadata["layout"]["compat_mode"],
        "status": "initialized",
    }


def command_append_event(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(args.workspace, memory_dir=args.memory_dir, compat_mode=args.compat_mode)
    store.ensure_layout()
    event_payloads = load_event_payloads(Path(args.events))
    written = []
    before_snapshot = store.snapshot_store_text()
    for payload in event_payloads:
        validate_document("memory-event.schema.json", payload)
        path = store.append_event(MemoryEvent(**payload))
        written.append(str(path.relative_to(store.workspace)))
    audit = store.write_mutation_audit(
        action="append-event",
        run_id=stable_id("append", args.events, len(event_payloads)),
        target_paths=[store.events_dir],
        summary={"events": len(event_payloads), "written_files": sorted(set(written))},
        before_snapshot=before_snapshot,
    )
    return {
        "workspace": str(store.workspace),
        "written_files": sorted(set(written)),
        "events": len(event_payloads),
        "audit": audit,
    }


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
    store = build_store(args.workspace, memory_dir=args.memory_dir, compat_mode=args.compat_mode)
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
    before_snapshot = store.snapshot_store_text()
    if candidates:
        store.append_candidates(candidates, run_id)
    if not args.events:
        store.mark_events_processed(event_ids)
    audit = store.write_mutation_audit(
        action="extract",
        run_id=run_id,
        target_paths=[store.candidates_dir, store.extraction_state_path],
        summary={"processed_events": len(events), "created_candidates": len(candidates)},
        before_snapshot=before_snapshot,
    )
    return {
        "workspace": str(store.workspace),
        "run_id": run_id,
        "processed_events": len(events),
        "created_candidates": len(candidates),
        "audit": audit,
    }


def command_bootstrap_index(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(args.workspace, memory_dir=args.memory_dir, compat_mode=args.compat_mode)
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
    store = build_store(args.workspace, memory_dir=args.memory_dir, compat_mode=args.compat_mode)
    store.ensure_layout()
    result = consolidate(store, now=args.now, sleep_before_write=args.sleep_before_write)
    result["workspace"] = str(store.workspace)
    return result


def command_retrieve(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(args.workspace, memory_dir=args.memory_dir, compat_mode=args.compat_mode)
    store.ensure_layout()
    response = retrieve(
        store,
        query=args.query,
        limit=args.limit,
        now=args.now,
        include_contested=args.include_contested,
    )
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
    selected_stores = stores if len(stores) > 1 or args.stores_manifest else stores[0]
    return prepare_context(
        selected_stores,
        query=args.query,
        limit=args.limit,
        now=args.now,
    )


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
    store = build_store(
        str(workspace),
        store_kind_hint="project",
        memory_dir=args.memory_dir,
        compat_mode=args.compat_mode,
    )
    store.ensure_layout()
    fixture = FIXTURE_ROOT / "golden_events.jsonl"
    events = load_event_payloads(fixture)
    for event in events:
        validate_document("memory-event.schema.json", event)
        store.append_event(MemoryEvent(**event))

    extraction = command_extract(
        argparse.Namespace(
            workspace=str(workspace),
            events=None,
            now=args.now,
            memory_dir=args.memory_dir,
            compat_mode=args.compat_mode,
        )
    )
    consolidation = command_consolidate(
        argparse.Namespace(
            workspace=str(workspace),
            now=args.now,
            sleep_before_write=0.0,
            memory_dir=args.memory_dir,
            compat_mode=args.compat_mode,
        )
    )
    retrieval = command_retrieve(
        argparse.Namespace(
            workspace=str(workspace),
            query="What package manager, workflow, and environment requirements should I use?",
            limit=5,
            now=args.now,
            include_contested=False,
            memory_dir=args.memory_dir,
            compat_mode=args.compat_mode,
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


def command_dream_run(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(
        args.workspace,
        memory_dir=args.memory_dir,
        compat_mode=args.compat_mode,
    )
    if not store.is_initialized():
        store.initialize(store_kind="project", compat_mode=args.compat_mode)
    episode_paths = resolve_episode_paths(store, getattr(args, "episodes", None))
    result = dream_run(
        store,
        episode_paths=episode_paths,
        now=args.now,
        max_recent_episodes=args.max_recent_episodes,
        min_episode_signals=args.min_episode_signals,
    )
    result["workspace"] = str(store.workspace)
    result["memory_root"] = str(store.memory_root)
    return result


def command_dream_status(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(
        args.workspace,
        memory_dir=args.memory_dir,
        compat_mode=args.compat_mode,
    )
    snapshot = store.status_snapshot(now=args.now)
    return {
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "dream": snapshot["dream"],
    }


def command_dream_tick(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(
        args.workspace,
        memory_dir=args.memory_dir,
        compat_mode=args.compat_mode,
    )
    if not store.is_initialized():
        store.initialize(store_kind="project", compat_mode=args.compat_mode)
    episode_paths = resolve_episode_paths(store, getattr(args, "episodes", None))
    result = dream_tick(
        store,
        episode_paths=episode_paths,
        now=args.now,
        max_recent_episodes=args.max_recent_episodes,
        min_episode_signals=args.min_episode_signals,
        min_interval_seconds=args.min_interval_seconds,
    )
    result["workspace"] = str(store.workspace)
    result["memory_root"] = str(store.memory_root)
    return result


def command_dream_enqueue(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(
        args.workspace,
        memory_dir=args.memory_dir,
        compat_mode=args.compat_mode,
    )
    if not store.is_initialized():
        store.initialize(store_kind="project", compat_mode=args.compat_mode)
    episode_paths = resolve_episode_paths(store, getattr(args, "episodes", None))
    if not episode_paths:
        return {
            "status": "skipped",
            "reason": "no-episodes",
            "queue_depth": len([item for item in store.load_dream_queue() if item.get("status") == "queued"]),
            "workspace": str(store.workspace),
            "memory_root": str(store.memory_root),
        }
    result = enqueue_dream_job(
        store,
        episode_paths=episode_paths,
        now=args.now,
        max_recent_episodes=args.max_recent_episodes,
        min_episode_signals=args.min_episode_signals,
        trigger_class=args.trigger_class,
    )
    result["workspace"] = str(store.workspace)
    result["memory_root"] = str(store.memory_root)
    return result


def command_dream_worker(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(
        args.workspace,
        memory_dir=args.memory_dir,
        compat_mode=args.compat_mode,
    )
    if not store.is_initialized():
        store.initialize(store_kind="project", compat_mode=args.compat_mode)
    result = dream_worker(
        store,
        now=args.now,
        interval_seconds=args.interval_seconds,
        max_polls=1 if args.once else args.max_polls,
        max_jobs_per_poll=args.max_jobs_per_poll,
        idle_exit=args.idle_exit,
        process_backlog=not args.no_backlog,
    )
    result["workspace"] = str(store.workspace)
    result["memory_root"] = str(store.memory_root)
    return result


def command_eval_memory_quality(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(
        args.workspace,
        memory_dir=args.memory_dir,
        compat_mode=args.compat_mode,
    )
    if not store.is_initialized():
        store.initialize(store_kind="project", compat_mode=args.compat_mode)
    fixture_path = Path(args.fixture) if args.fixture else None
    return run_memory_quality_eval(store, fixture_path=fixture_path, now=args.now)


def command_eval_dream_fidelity(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(
        args.workspace,
        memory_dir=args.memory_dir,
        compat_mode=args.compat_mode or "autodream",
    )
    if not store.is_initialized():
        store.initialize(store_kind="project", compat_mode=args.compat_mode or "autodream")
    fixture_path = Path(args.fixture) if args.fixture else None
    return run_dream_fidelity_eval(store, fixture_path=fixture_path, now=args.now)


def command_index_observability(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(
        args.workspace,
        memory_dir=args.memory_dir,
        compat_mode=args.compat_mode,
    )
    if not store.is_initialized():
        store.initialize(store_kind="project", compat_mode=args.compat_mode)
    index = index_observability(store, now=args.now)
    return {
        "workspace": str(store.workspace),
        "generated_at": index["generated_at"],
        "entity_groups": sorted(index["entities"].keys()),
        "index_path": str(store.observability_index_path),
    }


def command_observe_serve(args: argparse.Namespace) -> dict[str, Any]:
    store = build_store(
        args.workspace,
        memory_dir=args.memory_dir,
        compat_mode=args.compat_mode,
    )
    if not store.is_initialized():
        store.initialize(store_kind="project", compat_mode=args.compat_mode)
    index_observability(store, now=args.now)
    server = build_server(store, host=args.host, port=args.port)
    host = str(server.server_address[0])
    port = int(server.server_address[1])
    print(json_dumps({"status": "serving", "host": host, "port": port, "url": f"http://{host}:{port}"}))
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return {"status": "stopped", "host": host, "port": port}


def build_parser() -> argparse.ArgumentParser:
    parser = OpenDreamArgumentParser(
        prog="opendream",
        description="Local-first memory runtime for coding agents.",
        epilog=TOP_LEVEL_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"opendream {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True, title="commands")

    init_parser = subparsers.add_parser("init", help="Create the memory layout in a workspace")
    init_parser.add_argument("--workspace", required=True)
    init_parser.add_argument("--store-kind", choices=sorted(VALID_STORE_KINDS), default="project")
    add_layout_arguments(init_parser)
    init_parser.set_defaults(func=command_init)

    append_parser = subparsers.add_parser("append-event")
    append_parser.add_argument("--workspace", required=True)
    append_parser.add_argument("--events", required=True, help="JSON, JSON array, or JSONL file")
    add_layout_arguments(append_parser)
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
    add_layout_arguments(emit_parser)
    emit_parser.set_defaults(func=command_emit_event)

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("--workspace", required=True)
    extract_parser.add_argument("--events", help="Optional JSON, JSON array, or JSONL file")
    extract_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    add_layout_arguments(extract_parser)
    extract_parser.set_defaults(func=command_extract)

    bootstrap_parser = subparsers.add_parser("bootstrap-index")
    bootstrap_parser.add_argument("--workspace", required=True)
    bootstrap_parser.add_argument("--events", required=True)
    bootstrap_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    add_layout_arguments(bootstrap_parser)
    bootstrap_parser.set_defaults(func=command_bootstrap_index)

    consolidate_parser = subparsers.add_parser("consolidate", help="Apply planned durable-memory consolidation")
    consolidate_parser.add_argument("--workspace", required=True)
    consolidate_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    consolidate_parser.add_argument("--sleep-before-write", type=float, default=0.0, help=argparse.SUPPRESS)
    add_layout_arguments(consolidate_parser)
    consolidate_parser.set_defaults(func=command_consolidate)

    maintain_parser = subparsers.add_parser("maintain", help="Run extract plus consolidate when policy allows")
    maintain_parser.add_argument("--workspace", required=True)
    maintain_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    maintain_parser.add_argument("--min-new-events", type=int)
    maintain_parser.add_argument("--min-interval-seconds", type=int)
    add_layout_arguments(maintain_parser)
    add_store_group_arguments(maintain_parser)
    maintain_parser.set_defaults(func=command_maintain)

    retrieve_parser = subparsers.add_parser("retrieve", help="Retrieve relevant durable memory records")
    retrieve_parser.add_argument("--workspace", required=True)
    retrieve_parser.add_argument("--query", required=True)
    retrieve_parser.add_argument("--limit", type=int, default=5)
    retrieve_parser.add_argument("--include-contested", action="store_true")
    retrieve_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    add_layout_arguments(retrieve_parser)
    retrieve_parser.set_defaults(func=command_retrieve)

    prepare_context_parser = subparsers.add_parser("prepare-context", help="Assemble prompt-ready memory context")
    prepare_context_parser.add_argument("--workspace", required=True)
    prepare_context_parser.add_argument("--query", required=True)
    prepare_context_parser.add_argument("--limit", type=int, default=5)
    prepare_context_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    add_layout_arguments(prepare_context_parser)
    add_store_group_arguments(prepare_context_parser)
    prepare_context_parser.set_defaults(func=command_prepare_context)

    status_parser = subparsers.add_parser("status", help="Inspect scheduler, lock, and dream state")
    status_parser.add_argument("--workspace", required=True)
    status_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    status_parser.add_argument("--min-new-events", type=int)
    status_parser.add_argument("--min-interval-seconds", type=int)
    add_layout_arguments(status_parser)
    add_store_group_arguments(status_parser)
    status_parser.set_defaults(func=command_status)

    tick_parser = subparsers.add_parser("tick", help="Run one scheduler-safe maintenance poll")
    tick_parser.add_argument("--workspace", required=True)
    tick_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    tick_parser.add_argument("--min-new-events", type=int)
    tick_parser.add_argument("--min-interval-seconds", type=int)
    add_layout_arguments(tick_parser)
    add_store_group_arguments(tick_parser)
    tick_parser.set_defaults(func=command_tick)

    demo_parser = subparsers.add_parser("demo", help="Seed a deterministic demo workspace")
    demo_parser.add_argument("--workspace", required=True)
    demo_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    add_layout_arguments(demo_parser)
    demo_parser.set_defaults(func=command_demo)

    dream_parser = subparsers.add_parser("dream", help="Transcript-native dream commands")
    dream_subparsers = dream_parser.add_subparsers(dest="dream_command", required=True)
    dream_run_parser = dream_subparsers.add_parser(
        "run",
        help="Run a single dream pass from explicit episodes or transcript files",
    )
    dream_run_parser.add_argument("--workspace", required=True)
    dream_run_parser.add_argument("--episodes", nargs="*")
    dream_run_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    dream_run_parser.add_argument("--max-recent-episodes", type=int)
    dream_run_parser.add_argument("--min-episode-signals", type=int)
    add_layout_arguments(dream_run_parser)
    dream_run_parser.set_defaults(func=command_dream_run)
    dream_status_parser = dream_subparsers.add_parser("status", help="Inspect dream, queue, and worker state")
    dream_status_parser.add_argument("--workspace", required=True)
    dream_status_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    add_layout_arguments(dream_status_parser)
    dream_status_parser.set_defaults(func=command_dream_status)
    dream_tick_parser = dream_subparsers.add_parser("tick", help="Run one scheduler-safe transcript backlog poll")
    dream_tick_parser.add_argument("--workspace", required=True)
    dream_tick_parser.add_argument("--episodes", nargs="*")
    dream_tick_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    dream_tick_parser.add_argument("--max-recent-episodes", type=int)
    dream_tick_parser.add_argument("--min-episode-signals", type=int)
    dream_tick_parser.add_argument("--min-interval-seconds", type=int, default=0)
    add_layout_arguments(dream_tick_parser)
    dream_tick_parser.set_defaults(func=command_dream_tick)
    dream_enqueue_parser = dream_subparsers.add_parser(
        "enqueue",
        help="Queue dream work for later worker or daemon processing",
    )
    dream_enqueue_parser.add_argument("--workspace", required=True)
    dream_enqueue_parser.add_argument("--episodes", nargs="*")
    dream_enqueue_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    dream_enqueue_parser.add_argument("--max-recent-episodes", type=int)
    dream_enqueue_parser.add_argument("--min-episode-signals", type=int)
    dream_enqueue_parser.add_argument("--trigger-class", default="queued-manual")
    add_layout_arguments(dream_enqueue_parser)
    dream_enqueue_parser.set_defaults(func=command_dream_enqueue)
    dream_worker_parser = dream_subparsers.add_parser(
        "worker",
        help="Drain queued jobs in a one-shot or bounded worker poll",
        description=(
            "Drain queued dream jobs. Use `--once` for a single poll. "
            "Use `dream daemon` for a supervisor-style loop."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    dream_worker_parser.add_argument("--workspace", required=True)
    dream_worker_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    dream_worker_parser.add_argument("--interval-seconds", type=float, default=0.0)
    dream_worker_parser.add_argument("--max-polls", type=int, default=1)
    dream_worker_parser.add_argument("--max-jobs-per-poll", type=int)
    dream_worker_parser.add_argument("--idle-exit", action="store_true", default=False)
    dream_worker_parser.add_argument("--once", action="store_true")
    dream_worker_parser.add_argument("--no-backlog", action="store_true")
    add_layout_arguments(dream_worker_parser)
    dream_worker_parser.set_defaults(func=command_dream_worker)
    dream_daemon_parser = dream_subparsers.add_parser(
        "daemon",
        help="Run the dream worker in a supervisor-friendly looping mode",
        description=(
            "Alias over the worker loop for longer-running supervision. "
            "Use `worker --once` for single-poll automation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    dream_daemon_parser.add_argument("--workspace", required=True)
    dream_daemon_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    dream_daemon_parser.add_argument("--interval-seconds", type=float, default=30.0)
    dream_daemon_parser.add_argument("--max-polls", type=int, default=1)
    dream_daemon_parser.add_argument("--max-jobs-per-poll", type=int)
    dream_daemon_parser.add_argument("--idle-exit", action="store_true", default=False)
    dream_daemon_parser.add_argument("--once", action="store_true")
    dream_daemon_parser.add_argument("--no-backlog", action="store_true")
    add_layout_arguments(dream_daemon_parser)
    dream_daemon_parser.set_defaults(func=command_dream_worker)

    eval_parser = subparsers.add_parser(
        "eval",
        help="Run machine-readable quality and fidelity evaluations",
    )
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command", required=True)
    eval_memory_parser = eval_subparsers.add_parser(
        "memory-quality",
        help="Run retrieval and contradiction quality checks",
    )
    eval_memory_parser.add_argument("--workspace", required=True)
    eval_memory_parser.add_argument("--fixture")
    eval_memory_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    add_layout_arguments(eval_memory_parser)
    eval_memory_parser.set_defaults(func=command_eval_memory_quality, result_failure_statuses=("failed",))
    eval_dream_parser = eval_subparsers.add_parser("dream-fidelity", help="Run transcript-native dream fidelity checks")
    eval_dream_parser.add_argument("--workspace", required=True)
    eval_dream_parser.add_argument("--fixture")
    eval_dream_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    add_layout_arguments(eval_dream_parser)
    eval_dream_parser.set_defaults(func=command_eval_dream_fidelity, result_failure_statuses=("failed",))

    observe_parser = subparsers.add_parser("observe")
    observe_subparsers = observe_parser.add_subparsers(dest="observe_command", required=True)

    observe_index_parser = observe_subparsers.add_parser("index")
    observe_index_parser.add_argument("--workspace", required=True)
    observe_index_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    add_layout_arguments(observe_index_parser)
    observe_index_parser.set_defaults(func=command_index_observability)

    observe_serve_parser = observe_subparsers.add_parser("serve")
    observe_serve_parser.add_argument("--workspace", required=True)
    observe_serve_parser.add_argument("--host", default="127.0.0.1")
    observe_serve_parser.add_argument("--port", type=int, default=8000)
    observe_serve_parser.add_argument("--now", help="Fixed ISO timestamp for deterministic runs")
    add_layout_arguments(observe_serve_parser)
    observe_serve_parser.set_defaults(func=command_observe_serve)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    print(json_dumps(result))
    if isinstance(result, dict):
        failure_statuses = set(getattr(args, "result_failure_statuses", ()))
        if failure_statuses and str(result.get("status", "")) in failure_statuses:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
