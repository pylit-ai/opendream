from __future__ import annotations

from pathlib import Path
from typing import Any

from .integration import maintain, prepare_context
from .models import MemoryEvent
from .retriever import retrieve
from .storage import MemoryStore
from .util import FIXTURE_ROOT, read_json, to_iso, utc_now, write_json
from .validation import validate_document

SHOWCASE_SCENARIO = "coding-agent-showcase"
DEFAULT_DEMO_SCENARIO = "default"
SHOWCASE_FIXTURE = FIXTURE_ROOT / "showcase_coding_agent_memory.jsonl"
SHOWCASE_QUERY = "pnpm Redis build memory-showcase workflow"
SHOWCASE_TASK_PROMPT = (
    "You are about to update the OpenDream Observe UI for the memory showcase. "
    "Before editing, identify the repo-specific package manager, local service prerequisites, "
    "known failed approach, successful UI build step, and verification workflow."
)
SHOWCASE_EXPECTED_RESPONSE = (
    "Use pnpm for frontend commands, make sure Redis is available before queue-backed worker tests, "
    "avoid npm because it caused lockfile drift, rebuild opendream/static/dist after Observe UI type changes, "
    "and run the memory-showcase verification path."
)
SHOWCASE_REPORT_PATH = Path("state") / "showcase_report.json"


def showcase_report_path(store: MemoryStore) -> Path:
    return store.memory_root / SHOWCASE_REPORT_PATH


def load_showcase_report(store: MemoryStore) -> dict[str, Any]:
    path = showcase_report_path(store)
    if not path.exists():
        return {
            "available": False,
            "report": None,
            "report_path": str(path),
            "command": f"opendream demo --scenario {SHOWCASE_SCENARIO} --workspace {store.workspace}",
        }
    return {
        "available": True,
        "report": read_json(path, {}),
        "report_path": str(path),
    }


def load_showcase_events(path: Path = SHOWCASE_FIXTURE) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [read_json_line(line) for line in text.splitlines() if line.strip()]


def read_json_line(line: str) -> dict[str, Any]:
    import json

    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("showcase fixture rows must be JSON objects")
    return value


def run_showcase_demo(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    store.ensure_layout()
    before = retrieve(
        store,
        query=SHOWCASE_QUERY,
        limit=5,
        now=timestamp,
        query_source="showcase-before",
        caller_detail="coding-agent-showcase baseline",
    )

    events = load_showcase_events()
    for event in events:
        validate_document("memory-event.schema.json", event)
        store.append_event(MemoryEvent(**event))

    maintenance = maintain(store, now=timestamp, min_new_events=0, min_interval_seconds=0)
    after = retrieve(
        store,
        query=SHOWCASE_QUERY,
        limit=5,
        now=timestamp,
        query_source="showcase-after",
        caller_detail="coding-agent-showcase seeded recall",
    )
    context = prepare_context(store, query=SHOWCASE_QUERY, limit=5, now=timestamp)
    report = build_showcase_report(
        store,
        events=events,
        before=before,
        after=after,
        context=context,
        maintenance=maintenance,
        timestamp=timestamp,
    )
    report_path = showcase_report_path(store)
    report["report_path"] = str(report_path)
    write_json(report_path, report)
    return report


def build_showcase_report(
    store: MemoryStore,
    *,
    events: list[dict[str, Any]],
    before: dict[str, Any],
    after: dict[str, Any],
    context: dict[str, Any],
    maintenance: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    records = {record["memory_id"]: record for record in store.load_durable_records()}
    events_by_id = {event["event_id"]: event for event in events}
    source_refs = [
        _source_ref(memory_id, records.get(memory_id), events_by_id)
        for memory_id in after.get("selected_memory_ids", [])
        if records.get(memory_id)
    ]
    agent_snippet = _agent_snippet(source_refs)
    checks = score_showcase(before=before, after=after, source_refs=source_refs, agent_snippet=agent_snippet)
    status = "passed" if all(item["passed"] for item in checks.values()) else "failed"
    retrieval_reasons = _retrieval_reasons(after)
    prompt_links = _prompt_context_links(context, source_refs, retrieval_reasons)
    objective = _showcase_objective()
    return {
        "scenario": SHOWCASE_SCENARIO,
        "status": status,
        "generated_at": timestamp,
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "fixture": SHOWCASE_FIXTURE.name,
        "events_appended": len(events),
        "before": before,
        "after": after,
        "context": {
            "context_id": context.get("context_id"),
            "selected_memory_ids": context.get("selected_memory_ids", []),
            "prompt_context": context.get("prompt_context", ""),
            "visibility": context.get("prompt_context_visibility", {}),
            "selection": context.get("selection", {}),
            "context_pruning": context.get("context_pruning", {}),
            "links": prompt_links,
        },
        "objective": objective,
        "evaluation_case": {
            "user_prompt": SHOWCASE_TASK_PROMPT,
            "retrieval_query": SHOWCASE_QUERY,
            "expected_response": SHOWCASE_EXPECTED_RESPONSE,
            "why_this_tests_memory": (
                "The prompt needs knowledge from several earlier synthetic sessions: a corrected package-manager "
                "decision, an environment requirement, a failed approach, a successful workaround, and a workflow "
                "step. It should also ignore unrelated GraphQL billing memory and avoid the stale npm decision."
            ),
            "failure_without_memory": (
                "A stateless agent would likely guess npm or omit Redis, repeat the lockfile-drift failure, "
                "or skip the committed Observe UI dist rebuild."
            ),
        },
        "selected_memory_ids": after.get("selected_memory_ids", []),
        "agent_snippet": agent_snippet,
        "proof": {
            "query": SHOWCASE_QUERY,
            "source_refs": source_refs,
            "expected_signals": ["pnpm", "Redis", "frontend build", "memory-showcase workflow"],
        },
        "retrieval_rationale": retrieval_reasons,
        "dream_effectiveness": _dream_effectiveness(
            events=events,
            records=records,
            source_refs=source_refs,
            maintenance=maintenance,
            before=before,
            after=after,
            context=context,
        ),
        "checks": checks,
        "maintenance": maintenance,
    }


def score_showcase(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    source_refs: list[dict[str, Any]],
    agent_snippet: str,
) -> dict[str, dict[str, Any]]:
    joined = "\n".join(
        " ".join(
            [
                str(ref.get("title", "")),
                str(ref.get("summary", "")),
                " ".join(str(event.get("content", "")) for event in ref.get("source_events", [])),
            ]
        )
        for ref in source_refs
    )
    selected_ids = after.get("selected_memory_ids", [])
    return {
        "baseline_empty": {
            "passed": not before.get("selected_memory_ids"),
            "detail": "before probe should not retrieve memory from an empty store",
        },
        "recall": {
            "passed": bool(selected_ids) and "pnpm" in joined and "Redis" in joined,
            "detail": "after probe should recall package manager and Redis requirements",
        },
        "stale_update": {
            "passed": "pnpm" in joined and "Earlier stale decision: use npm" not in joined,
            "detail": "selected proof should prefer the pnpm correction over the stale npm prototype decision",
        },
        "decoy_rejection": {
            "passed": "GraphQL billing API" not in joined,
            "detail": "unrelated GraphQL billing sandbox memory should be excluded from selected durable memory",
        },
        "provenance": {
            "passed": bool(source_refs)
            and all(ref.get("source_event_ids") and ref.get("source_events") for ref in source_refs),
            "detail": "each selected memory should expose source event evidence",
        },
        "snippet": {
            "passed": "OpenDream found prior memory:" in agent_snippet,
            "detail": "showcase should emit the visible agent-facing recall phrase",
        },
    }


def _source_ref(
    memory_id: str,
    record: dict[str, Any] | None,
    events_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if record is None:
        return {"memory_id": memory_id, "missing": True, "source_event_ids": [], "source_events": []}
    source_event_ids = list(record.get("source_event_ids", []))
    return {
        "memory_id": memory_id,
        "title": record.get("title", ""),
        "type": record.get("type", ""),
        "summary": record.get("summary", ""),
        "status": record.get("status", ""),
        "source_event_ids": source_event_ids,
        "source_events": [
            {
                "event_id": event_id,
                "kind": events_by_id.get(event_id, {}).get("kind"),
                "message_ref": events_by_id.get(event_id, {}).get("source", {}).get("message_ref"),
                "timestamp": events_by_id.get(event_id, {}).get("timestamp"),
                "content": events_by_id.get(event_id, {}).get("content"),
            }
            for event_id in source_event_ids
            if event_id in events_by_id
        ],
    }


def _agent_snippet(source_refs: list[dict[str, Any]]) -> str:
    if not source_refs:
        return "OpenDream found no prior memory for this task yet."
    first = source_refs[0]
    event_ids = ", ".join(first.get("source_event_ids", [])) or "unknown source"
    return (
        "OpenDream found prior memory: "
        f"{first.get('summary', '')} "
        f"(memory {first.get('memory_id')}, source {event_ids})."
    )


def _showcase_objective() -> dict[str, Any]:
    return {
        "title": "Show that OpenDream turns prior coding-agent history into useful prompt context.",
        "description": (
            "A new user should see, in one command, that OpenDream can recall repo-specific decisions, "
            "environment constraints, failed approaches, successful workarounds, and verification workflow "
            "without waiting for weeks of real history."
        ),
        "success_criteria": [
            "The empty baseline retrieves no memory.",
            "After seeded history is maintained, the prompt context includes the current pnpm decision.",
            "The Redis prerequisite, no-npm anti-pattern, frontend build workaround, and workflow memory are selected.",
            "The stale npm prototype memory is not used as current guidance.",
            "The unrelated GraphQL billing decoy is not selected.",
            "Every selected memory links back to source event evidence.",
        ],
        "research_pattern": (
            "This mirrors current memory evaluations that disclose the task prompt, answer prompt/context, "
            "retrieved evidence, update handling, abstention/noise rejection, and provenance."
        ),
    }


def _retrieval_reasons(after: dict[str, Any]) -> list[dict[str, Any]]:
    explanations = after.get("explanations", [])
    if not isinstance(explanations, list):
        return []
    reasons: list[dict[str, Any]] = []
    for item in explanations:
        if not isinstance(item, dict):
            continue
        reasons.append(
            {
                "memory_id": item.get("memory_id"),
                "score": item.get("score"),
                "why_included": item.get("why_included"),
                "why_excluded": item.get("why_excluded"),
                "matched_evidence": item.get("matched_evidence", {}),
                "score_contributions": item.get("score_contributions", {}),
                "provenance_tier": item.get("provenance_tier"),
                "status": item.get("status"),
            }
        )
    return reasons


def _prompt_context_links(
    context: dict[str, Any],
    source_refs: list[dict[str, Any]],
    retrieval_reasons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reasons = {item.get("memory_id"): item for item in retrieval_reasons}
    selected = set(context.get("selected_memory_ids", []))
    links: list[dict[str, Any]] = []
    for ref in source_refs:
        memory_id = ref.get("memory_id")
        if memory_id not in selected:
            continue
        reason = reasons.get(memory_id, {})
        links.append(
            {
                "memory_id": memory_id,
                "memory_href": f"/memories?id={memory_id}",
                "title": ref.get("title"),
                "summary": ref.get("summary"),
                "source_event_ids": ref.get("source_event_ids", []),
                "source_refs": [
                    {
                        "event_id": event.get("event_id"),
                        "message_ref": event.get("message_ref"),
                        "timestamp": event.get("timestamp"),
                    }
                    for event in ref.get("source_events", [])
                ],
                "why_included": reason.get("why_included"),
                "score": reason.get("score"),
            }
        )
    return links


def _dream_effectiveness(
    *,
    events: list[dict[str, Any]],
    records: dict[str, dict[str, Any]],
    source_refs: list[dict[str, Any]],
    maintenance: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    consolidate = maintenance.get("consolidate", {}) if isinstance(maintenance, dict) else {}
    extract = maintenance.get("extract", {}) if isinstance(maintenance, dict) else {}
    selected_ids = set(after.get("selected_memory_ids", []))
    selected_source_ids = {
        event_id
        for ref in source_refs
        for event_id in ref.get("source_event_ids", [])
        if isinstance(event_id, str)
    }
    raw_chars = sum(len(str(event.get("content", ""))) for event in events)
    prompt_chars = len(str(context.get("prompt_context", "")))
    active_records = [record for record in records.values() if record.get("status") == "active"]
    contested_records = [record for record in records.values() if record.get("status") == "contested"]
    excluded = after.get("excluded", []) if isinstance(after.get("excluded"), list) else []
    excluded_ids = {item.get("memory_id") for item in excluded if isinstance(item, dict)}
    decoy_excluded = any(
        memory_id in excluded_ids and "GraphQL billing API" in str(record.get("summary", ""))
        for memory_id, record in records.items()
    )
    return {
        "summary": (
            "The maintenance dream distilled raw session events into durable memories, marked stale guidance "
            "as contested, preserved source provenance, and made the task prompt retrieve curated actionable "
            "memory instead of raw history."
        ),
        "pipeline": [
            {
                "stage": "Seeded prior sessions",
                "input": len(events),
                "output": len(events),
                "evidence": (
                    "Synthetic coding-agent events with preference, environment, failure, fix, "
                    "workflow, update, and decoy."
                ),
            },
            {
                "stage": "Extraction",
                "input": len(events),
                "output": extract.get("created_candidates", 0),
                "evidence": f"Processed {extract.get('processed_events', 0)} events into candidate memories.",
            },
            {
                "stage": "Consolidation dream",
                "input": extract.get("created_candidates", 0),
                "output": consolidate.get("created", 0),
                "evidence": (
                    f"Created {consolidate.get('created', 0)} durable memories, "
                    f"contested {consolidate.get('contested', 0)}, quarantined {consolidate.get('quarantined', 0)}."
                ),
            },
            {
                "stage": "Prompt-context assembly",
                "input": len(active_records),
                "output": len(context.get("selected_memory_ids", [])),
                "evidence": "Selected the memories that should guide the next coding-agent prompt.",
            },
        ],
        "metrics": {
            "raw_event_count": len(events),
            "raw_event_chars": raw_chars,
            "candidate_count": extract.get("created_candidates", 0),
            "durable_memory_count": len(records),
            "active_memory_count": len(active_records),
            "contested_memory_count": len(contested_records),
            "before_selected_count": len(before.get("selected_memory_ids", [])),
            "after_selected_count": len(selected_ids),
            "selected_source_event_count": len(selected_source_ids),
            "prompt_context_chars": prompt_chars,
            "startup_index_entries": consolidate.get("startup_index_entries", 0),
        },
        "why_it_matters": [
            (
                "A stale npm prototype decision survives as evidence but is marked contested, "
                "so current pnpm guidance wins."
            ),
            "The unrelated GraphQL billing decoy remains in the store but is excluded from selected durable memory.",
            "The selected prompt context carries both concise memory summaries and source event links.",
            "The empty baseline proves the recall comes from seeded maintained memory, not hard-coded UI text.",
        ],
        "effective": {
            "baseline_to_after": not before.get("selected_memory_ids") and bool(selected_ids),
            "stale_guidance_contested": bool(contested_records),
            "decoy_excluded": decoy_excluded,
            "source_provenance_preserved": bool(selected_source_ids),
            "curated_actionable_prompt_context_built": (
                prompt_chars > 0 and len(context.get("selected_memory_ids", [])) <= len(active_records)
            ),
        },
    }
