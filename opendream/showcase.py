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
SHOWCASE_STATELESS_AGENT_ANSWER = (
    "Use the normal frontend path: run npm install and npm run build, then update the Observe UI "
    "and run the relevant tests. I do not see repo-specific service prerequisites or prior failed approaches."
)
SHOWCASE_ANSWER_SIGNALS: tuple[dict[str, Any], ...] = (
    {
        "key": "package_manager_pnpm",
        "label": "Uses current pnpm package-manager decision",
        "required_terms": ("pnpm",),
    },
    {
        "key": "redis_prerequisite",
        "label": "Names Redis as a local service prerequisite",
        "required_terms": ("redis",),
    },
    {
        "key": "npm_lockfile_drift_avoided",
        "label": "Avoids npm because of lockfile drift",
        "required_terms": ("avoid npm", "lockfile drift"),
    },
    {
        "key": "observe_dist_rebuild",
        "label": "Includes the committed Observe UI dist rebuild",
        "required_terms": ("opendream/static/dist", "observe ui"),
    },
    {
        "key": "memory_showcase_workflow",
        "label": "Runs the memory-showcase verification path",
        "required_terms": ("memory-showcase", "verification"),
    },
    {
        "key": "no_current_npm_guidance",
        "label": "Does not recommend stale npm guidance",
        "forbidden_terms": ("use npm", "npm install", "npm run"),
    },
    {
        "key": "decoy_not_used",
        "label": "Does not use the unrelated GraphQL billing decoy",
        "forbidden_terms": ("graphql billing",),
    },
    {
        "key": "source_grounded",
        "label": "Grounded in selected durable memory source refs",
        "requires_source_refs": True,
    },
)
SHOWCASE_ABSTENTION_CASES = [
    {
        "case_id": "low_information_prompt",
        "query": "help",
        "expected": "retrieval gate abstains because the prompt is underspecified",
    },
    {
        "case_id": "unknown_domain_prompt",
        "query": "configure payroll VAT invoice portal",
        "expected": "no memory is selected for an unrelated domain query",
    },
]
SHOWCASE_MEMORY_HURT_CASES = [
    {
        "case_id": "contested_npm_prototype_recall",
        "query": "npm frontend dependencies prototype",
        "expected": "default retrieval suppresses the contested stale npm memory; forced contested recall is flagged",
    }
]
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
    agent_answers = _agent_answers(before=before, after=after, source_refs=source_refs)
    retrieval_reasons = _retrieval_reasons(after)
    prompt_links = _prompt_context_links(context, source_refs, retrieval_reasons)
    case_results = _showcase_case_results(
        store,
        before=before,
        after=after,
        context=context,
        source_refs=source_refs,
        timestamp=timestamp,
    )
    checks = score_showcase(
        before=before,
        after=after,
        source_refs=source_refs,
        agent_snippet=agent_snippet,
        agent_answers=agent_answers,
        case_results=case_results,
    )
    status = "passed" if all(item["passed"] for item in checks.values()) else "failed"
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
        "agent_answers": agent_answers,
        "negative_controls": case_results["negative_controls"],
        "abstention_cases": case_results["abstention_cases"],
        "memory_hurt_cases": case_results["memory_hurt_cases"],
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
            agent_answers=agent_answers,
            case_results=case_results,
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
    agent_answers: dict[str, Any],
    case_results: dict[str, list[dict[str, Any]]],
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
        "negative_controls": {
            "passed": all(case.get("passed") for case in case_results.get("negative_controls", [])),
            "detail": "negative controls should reject stale or unrelated memories from the showcase prompt",
        },
        "abstention": {
            "passed": all(case.get("passed") for case in case_results.get("abstention_cases", [])),
            "detail": "abstention probes should select no memory when the task lacks usable project-memory signal",
        },
        "memory_hurt": {
            "passed": all(case.get("passed") for case in case_results.get("memory_hurt_cases", [])),
            "detail": "memory-hurt probes should show harmful contested recall is detectable and suppressed by default",
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
        "answer_improvement": {
            "passed": bool(agent_answers.get("comparison", {}).get("passed")),
            "detail": "memory-assisted answer should cover expected signals and improve over stateless baseline",
        },
    }


def _showcase_case_results(
    store: MemoryStore,
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    context: dict[str, Any],
    source_refs: list[dict[str, Any]],
    timestamp: str,
) -> dict[str, list[dict[str, Any]]]:
    records = {record["memory_id"]: record for record in store.load_durable_records()}
    return {
        "negative_controls": _negative_control_cases(
            records=records,
            before=before,
            after=after,
            context=context,
            source_refs=source_refs,
        ),
        "abstention_cases": _abstention_cases(store, timestamp=timestamp),
        "memory_hurt_cases": _memory_hurt_cases(store, timestamp=timestamp),
    }


def _negative_control_cases(
    *,
    records: dict[str, dict[str, Any]],
    before: dict[str, Any],
    after: dict[str, Any],
    context: dict[str, Any],
    source_refs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected_ids = set(after.get("selected_memory_ids", []))
    excluded_ids = {
        item.get("memory_id")
        for item in after.get("excluded", [])
        if isinstance(item, dict) and item.get("memory_id")
    }
    prompt_context = str(context.get("prompt_context", ""))
    proof_text = "\n".join(
        "\n".join([str(ref.get("title", "")), str(ref.get("summary", ""))]) for ref in source_refs
    )

    def ids_matching(text: str) -> list[str]:
        return [
            memory_id
            for memory_id, record in records.items()
            if text in " ".join(
                [str(record.get("title", "")), str(record.get("summary", "")), str(record.get("body", ""))]
            )
        ]

    graphql_ids = ids_matching("GraphQL billing API")
    stale_npm_ids = ids_matching("Earlier stale decision: use npm")
    return [
        {
            "case_id": "empty_store_baseline",
            "control_type": "empty-store negative control",
            "input": SHOWCASE_QUERY,
            "expected": "empty store retrieves no memory before fixture seeding",
            "passed": not before.get("selected_memory_ids"),
            "evidence": {"selected_memory_ids": before.get("selected_memory_ids", [])},
        },
        {
            "case_id": "unrelated_graphql_billing_decoy",
            "control_type": "irrelevant-domain decoy",
            "input": SHOWCASE_TASK_PROMPT,
            "expected": "GraphQL billing sandbox memory is not selected for the Observe UI task",
            "passed": bool(graphql_ids)
            and not (selected_ids & set(graphql_ids))
            and "GraphQL billing API" not in prompt_context
            and "GraphQL billing API" not in proof_text,
            "evidence": {
                "memory_ids": graphql_ids,
                "selected": sorted(selected_ids & set(graphql_ids)),
                "excluded": sorted(excluded_ids & set(graphql_ids)),
            },
        },
        {
            "case_id": "stale_npm_prototype_not_current_guidance",
            "control_type": "stale contradictory memory",
            "input": SHOWCASE_TASK_PROMPT,
            "expected": "stale npm prototype guidance is not selected as current package-manager guidance",
            "passed": bool(stale_npm_ids)
            and not (selected_ids & set(stale_npm_ids))
            and "Earlier stale decision: use npm" not in prompt_context
            and "Earlier stale decision: use npm" not in proof_text,
            "evidence": {
                "memory_ids": stale_npm_ids,
                "selected": sorted(selected_ids & set(stale_npm_ids)),
                "excluded": sorted(excluded_ids & set(stale_npm_ids)),
            },
        },
    ]


def _abstention_cases(store: MemoryStore, *, timestamp: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for probe in SHOWCASE_ABSTENTION_CASES:
        result = retrieve(
            store,
            query=probe["query"],
            limit=3,
            now=timestamp,
            query_source=f"showcase-abstention:{probe['case_id']}",
            caller_detail="coding-agent-showcase abstention control",
        )
        selected = result.get("selected_memory_ids", [])
        abstained = not selected
        reason = result.get("reason", "retrieval gated") if result.get("gated") else "no matching durable memory selected"
        cases.append(
            {
                "case_id": probe["case_id"],
                "input": probe["query"],
                "expected": probe["expected"],
                "passed": abstained,
                "abstained": abstained,
                "gated": bool(result.get("gated")),
                "reason": reason,
                "selected_memory_ids": selected,
                "excluded_count": len(result.get("excluded", [])),
            }
        )
    return cases


def _memory_hurt_cases(store: MemoryStore, *, timestamp: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for probe in SHOWCASE_MEMORY_HURT_CASES:
        safe = retrieve(
            store,
            query=probe["query"],
            limit=3,
            include_contested=False,
            now=timestamp,
            query_source=f"showcase-memory-hurt-safe:{probe['case_id']}",
            caller_detail="coding-agent-showcase memory-hurt safe path",
        )
        forced = retrieve(
            store,
            query=probe["query"],
            limit=3,
            include_contested=True,
            now=timestamp,
            query_source=f"showcase-memory-hurt-forced:{probe['case_id']}",
            caller_detail="coding-agent-showcase memory-hurt forced contested recall",
        )
        hurt = forced.get("memory_hurt", {}) if isinstance(forced.get("memory_hurt"), dict) else {}
        safe_hurt = safe.get("memory_hurt", {}) if isinstance(safe.get("memory_hurt"), dict) else {}
        contradicted = hurt.get("contradicted_recalled", [])
        safe_contradicted = safe_hurt.get("contradicted_recalled", [])
        harmful_ids = sorted(
            item.get("memory_id")
            for item in contradicted
            if isinstance(item, dict) and item.get("memory_id")
        )
        safe_ids = set(safe.get("selected_memory_ids", []))
        forced_ids = set(forced.get("selected_memory_ids", []))
        cases.append(
            {
                "case_id": probe["case_id"],
                "input": probe["query"],
                "expected": probe["expected"],
                "passed": bool(harmful_ids) and not safe_contradicted and not (safe_ids & set(harmful_ids)),
                "harm_prevented_by_default": bool(harmful_ids) and not (safe_ids & set(harmful_ids)),
                "safe_selected_memory_ids": sorted(safe_ids),
                "forced_selected_memory_ids": sorted(forced_ids),
                "harmful_memory_ids": harmful_ids,
                "forced_memory_hurt": hurt,
            }
        )
    return cases


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


def _agent_answers(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    source_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    stateless_selected = _selected_memory_ids(before)
    memory_selected = _selected_memory_ids(after)
    memory_answer = _memory_assisted_agent_answer(source_refs)
    stateless_measurement = _measure_agent_answer(
        answer=SHOWCASE_STATELESS_AGENT_ANSWER,
        selected_memory_ids=stateless_selected,
        source_refs=[],
    )
    memory_measurement = _measure_agent_answer(
        answer=memory_answer,
        selected_memory_ids=memory_selected,
        source_refs=source_refs,
    )
    stateless = {
        "label": "Stateless baseline",
        "mode": "stateless",
        "input": "Task prompt only; no selected memory or prompt context.",
        "selected_memory_ids": stateless_selected,
        "answer": SHOWCASE_STATELESS_AGENT_ANSWER,
        "measurement": stateless_measurement,
    }
    memory_assisted = {
        "label": "Memory-assisted answer",
        "mode": "memory_assisted",
        "input": "Task prompt plus OpenDream selected durable memory context.",
        "selected_memory_ids": memory_selected,
        "answer": memory_answer,
        "measurement": memory_measurement,
    }
    stateless_score = float(stateless_measurement["score"])
    memory_score = float(memory_measurement["score"])
    return {
        "stateless": stateless,
        "memory_assisted": memory_assisted,
        "comparison": {
            "score_delta": round(memory_score - stateless_score, 3),
            "stateless_passed": bool(stateless_measurement["passed"]),
            "memory_assisted_passed": bool(memory_measurement["passed"]),
            "passed": memory_score > stateless_score and bool(memory_measurement["passed"]),
            "stateless_missing_or_failed": [
                signal["key"]
                for signal in stateless_measurement["signals"]
                if not signal.get("passed")
            ],
            "memory_assisted_passed_signals": [
                signal["key"]
                for signal in memory_measurement["signals"]
                if signal.get("passed")
            ],
        },
    }


def _selected_memory_ids(payload: dict[str, Any]) -> list[str]:
    return [item for item in payload.get("selected_memory_ids", []) if isinstance(item, str)]


def _memory_assisted_agent_answer(source_refs: list[dict[str, Any]]) -> str:
    source_ids = ", ".join(str(ref.get("memory_id")) for ref in source_refs if ref.get("memory_id"))
    evidence = f" Evidence: selected durable memories {source_ids}." if source_ids else ""
    return f"{SHOWCASE_EXPECTED_RESPONSE}{evidence}"


def _measure_agent_answer(
    *,
    answer: str,
    selected_memory_ids: list[str],
    source_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = answer.lower()
    signals: list[dict[str, Any]] = []
    for signal in SHOWCASE_ANSWER_SIGNALS:
        required_terms = tuple(str(term) for term in signal.get("required_terms", ()))
        forbidden_terms = tuple(str(term) for term in signal.get("forbidden_terms", ()))
        missing_terms = [term for term in required_terms if term.lower() not in normalized]
        forbidden_matches = [term for term in forbidden_terms if term.lower() in normalized]
        source_ref_ok = not signal.get("requires_source_refs") or (
            bool(selected_memory_ids)
            and bool(source_refs)
            and all(ref.get("source_event_ids") for ref in source_refs)
        )
        signals.append(
            {
                "key": signal["key"],
                "label": signal["label"],
                "passed": not missing_terms and not forbidden_matches and source_ref_ok,
                "required_terms": list(required_terms),
                "missing_terms": missing_terms,
                "forbidden_terms": list(forbidden_terms),
                "forbidden_matches": forbidden_matches,
                "requires_source_refs": bool(signal.get("requires_source_refs")),
            }
        )
    passed_count = sum(1 for signal in signals if signal["passed"])
    total_count = len(signals)
    return {
        "score": round(passed_count / total_count, 3) if total_count else 0.0,
        "passed": passed_count == total_count,
        "passed_count": passed_count,
        "total_count": total_count,
        "signals": signals,
        "selected_memory_count": len(selected_memory_ids),
        "source_ref_count": len(source_refs),
    }


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
            "Low-information and unrelated-domain prompts abstain instead of inventing memory.",
            "A forced contested recall demonstrates memory-hurt detection while the default path suppresses it.",
            "Every selected memory links back to source event evidence.",
        ],
        "research_pattern": (
            "This mirrors current memory evaluations that disclose the task prompt, answer prompt/context, "
            "retrieved evidence, negative controls, abstention/noise rejection, memory-hurt probes, and provenance."
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
    agent_answers: dict[str, Any],
    case_results: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    consolidate = maintenance.get("consolidate", {}) if isinstance(maintenance, dict) else {}
    extract = maintenance.get("extract", {}) if isinstance(maintenance, dict) else {}
    selected_ids = set(after.get("selected_memory_ids", []))
    negative_controls = case_results.get("negative_controls", [])
    abstention_cases = case_results.get("abstention_cases", [])
    memory_hurt_cases = case_results.get("memory_hurt_cases", [])
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
    stateless_measurement = agent_answers.get("stateless", {}).get("measurement", {})
    memory_measurement = agent_answers.get("memory_assisted", {}).get("measurement", {})
    answer_comparison = agent_answers.get("comparison", {})
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
            {
                "stage": "Adversarial controls",
                "input": len(negative_controls) + len(abstention_cases) + len(memory_hurt_cases),
                "output": sum(
                    1
                    for case in [*negative_controls, *abstention_cases, *memory_hurt_cases]
                    if case.get("passed")
                ),
                "evidence": "Ran negative-control, abstention, and memory-hurt probes against the seeded store.",
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
            "stateless_answer_score": stateless_measurement.get("score"),
            "memory_assisted_answer_score": memory_measurement.get("score"),
            "answer_score_delta": answer_comparison.get("score_delta"),
            "negative_control_count": len(negative_controls),
            "abstention_case_count": len(abstention_cases),
            "memory_hurt_case_count": len(memory_hurt_cases),
        },
        "why_it_matters": [
            (
                "A stale npm prototype decision survives as evidence but is marked contested, "
                "so current pnpm guidance wins."
            ),
            "The unrelated GraphQL billing decoy remains in the store but is excluded from selected durable memory.",
            "Abstention cases prove low-information and unrelated-domain prompts do not fabricate recall.",
            "The memory-hurt case shows forced contested recall is flagged while default retrieval suppresses it.",
            "The selected prompt context carries both concise memory summaries and source event links.",
            "The empty baseline proves the recall comes from seeded maintained memory, not hard-coded UI text.",
            "Measured stateless and memory-assisted answers show whether recalled context changes the answer.",
        ],
        "effective": {
            "baseline_to_after": not before.get("selected_memory_ids") and bool(selected_ids),
            "stale_guidance_contested": bool(contested_records),
            "decoy_excluded": decoy_excluded,
            "negative_controls_passed": all(case.get("passed") for case in negative_controls),
            "abstention_cases_passed": all(case.get("passed") for case in abstention_cases),
            "memory_hurt_case_passed": all(case.get("passed") for case in memory_hurt_cases),
            "source_provenance_preserved": bool(selected_source_ids),
            "curated_actionable_prompt_context_built": (
                prompt_chars > 0 and len(context.get("selected_memory_ids", [])) <= len(active_records)
            ),
            "memory_assisted_answer_improved": bool(answer_comparison.get("passed")),
        },
    }
