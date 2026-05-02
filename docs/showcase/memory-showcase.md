# OpenDream Memory Showcase

This walkthrough creates a disposable, synthetic coding-agent history and then demonstrates the full memory loop on the next task: objective → prompt context → selected memories → source evidence → dream/maintenance effects. It is meant for first-run demos, skeptical evaluation, and release checks.

## 90-second path

```bash
rm -rf .tmp/opendream-showcase
.venv/bin/python -m opendream.cli demo \
  --scenario coding-agent-showcase \
  --workspace .tmp/opendream-showcase
```

Expected signal:

- `scenario` is `coding-agent-showcase`
- `objective.title` explains what the demo is trying to prove
- `evaluation_case.user_prompt` is the coding-agent task that requires prior memory
- `context.prompt_context` shows the exact context OpenDream would inject
- `context.links` connects selected prompt memories to memory IDs and source events
- `before.selected_memory_ids` is empty
- `after.selected_memory_ids` is non-empty
- `agent_snippet` starts with `OpenDream found prior memory:`
- `retrieval_rationale` explains why each memory was selected
- `dream_effectiveness` shows extraction, consolidation, stale-memory handling, decoy rejection, and prompt-context assembly
- `report_path` points at `.tmp/opendream-showcase/.opendream/memory/state/showcase_report.json`

## Skeptic validation

Run the hermetic eval. It uses an isolated store, so existing workspace memory does not affect the verdict.

```bash
.venv/bin/python -m opendream.cli eval showcase \
  --scenario coding-agent-showcase \
  --workspace .tmp/opendream-showcase
```

Use `--now 2026-03-26T12:00:00Z` only when you need deterministic test output for snapshots or release evidence. For an interactive demo, omit `--now` so OpenDream uses the current clock.

Expected checks:

- `baseline_empty`: the empty store does not invent prior memory
- `recall`: the seeded store recalls package-manager and Redis requirements
- `stale_update`: the pnpm correction wins over the stale npm prototype decision
- `decoy_rejection`: unrelated GraphQL billing sandbox memory is not selected
- `provenance`: selected memories include source event refs
- `snippet`: the agent-facing recall phrase is generated

## What the proof is proving

The objective is not merely that a memory ID appears. The showcase tests whether OpenDream can help a coding agent answer this task correctly:

> You are about to update the OpenDream Observe UI for the memory showcase. Before editing, identify the repo-specific package manager, local service prerequisites, known failed approach, successful UI build step, and verification workflow.

A correct memory system should surface the current pnpm decision, Redis prerequisite, npm lockfile-drift anti-pattern, Observe UI rebuild workaround, and memory-showcase verification workflow. It should not use the stale npm prototype decision as current guidance, and it should not pull in the unrelated GraphQL billing decoy.

The report makes that inspectable:

- `evaluation_case`: task prompt, expected answer shape, and likely stateless failure
- `context.prompt_context`: exact prompt context that would be sent to the agent
- `context.links`: selected prompt memories linked to source event IDs
- `retrieval_rationale`: score, matched evidence, inclusion reason, and status for each selected memory
- `dream_effectiveness`: the maintenance pipeline from raw events to durable memory to prompt context

## Dream effectiveness

The showcase uses `opendream demo` to seed raw events and run the maintenance/dream path. The report records whether the system:

- extracted candidates from raw coding-agent events
- consolidated those candidates into durable memories
- marked stale npm guidance as contested instead of treating it as current truth
- kept unrelated decoy memory out of the task prompt
- preserved source provenance for selected memory
- assembled compact prompt context from durable memory instead of dumping raw history

This mirrors current memory research practice: evaluate not only retrieval, but also update handling, noise rejection, temporal/current-state behavior, and whether consolidated memory improves the prompt context available to the agent.

## UI proof

```bash
.venv/bin/python -m opendream.cli observe serve --workspace .tmp/opendream-showcase
```

Open `/showcase`. The page reads the persisted showcase report and shows the objective, task prompt, exact injected prompt context, selected memories, retrieval rationale, source event evidence, dream/maintenance pipeline, and eval-style checks.

## Fixture

The synthetic fixture lives at `opendream/fixtures/showcase_coding_agent_memory.jsonl`.

It covers:

- package manager preference
- environment requirement
- failed approach / anti-pattern
- successful workaround
- workflow step
- stale decision plus correction
- unrelated decoy memory

## Research anchors

Comparable memory systems make value visible through seeded recall, inspectable memory, or benchmark-style proof:

- [MemoryArena](https://digitaleconomy.stanford.edu/publication/memoryarena-benchmarking-agent-memory-in-interdependent-multi-session-agentic-tasks/) argues memory should be evaluated by whether earlier experience guides later action, not isolated memorization.
- [Memory for Autonomous LLM Agents](https://arxiv.org/abs/2603.07670) frames memory as a write-manage-read loop and calls out consolidation, causally grounded retrieval, contradiction handling, and trustworthy reflection as open challenges.
- [ByteRover](https://arxiv.org/abs/2604.01599) emphasizes agent-native context, explicit provenance, hierarchical context, lifecycle scoring, and local-first storage.
- [Observational Memory](https://mastra.ai/research/observational-memory) demonstrates value by showing stable prompt context built from event-like observations and reflection, with compression rather than raw transcript stuffing.
- [Supermemory Research](https://supermemory.ai/research/) highlights LongMemEval categories that matter for real memory systems: preference, multi-session reasoning, knowledge updates, temporal reasoning, and noise filtering; it also discloses prompts/code for reproducibility.
- [ChatGPT Memory FAQ](https://help.openai.com/en/articles/8590148-memory-in-chatgpt)
- [Mem0 interactive memory demo](https://docs.mem0.ai/examples/mem0-demo)
- [Zep LangGraph memory example](https://help.getzep.com/ecosystem/langgraph-memory)
- [Letta archival memory panel](https://docs.letta.com/guides/ade/archival-memory)
- [Letta memory leaderboard](https://www.letta.com/blog/letta-leaderboard)
- [LongMemEval](https://arxiv.org/abs/2410.10813)
- [LoCoMo](https://arxiv.org/abs/2402.17753)
