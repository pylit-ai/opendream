# spec.md — 404-framework-adapter-pack

## Title
Add framework adapter packs and operator setup docs for Claude Code, Codex, and OpenClaw

## Why
OpenDream has a working local memory runtime plus a thin integration layer, but real operators still need framework-specific glue to use it with Claude Code, Codex, and OpenClaw. Governance already requires those artifacts to stay thin adapters rather than new policy surfaces.

## In scope
- adapter payloads under `.meta/spec-adapters/claude-code/`
- adapter payloads under `.meta/spec-adapters/codex/`
- adapter payloads under `.meta/spec-adapters/openclaw/`
- operator READMEs and runnable setup examples
- framework-specific event-mapping guidance
- framework-specific context-injection guidance
- adapter verification that examples are syntactically valid and reference real CLI commands

## Out of scope
- changing canonical memory semantics
- adding framework-specific policy not already present in canonical docs
- hosted control plane or remote service integration
- rewriting the core runtime

## User-visible behavior
- A Claude Code operator can install a thin skill and hook pack that calls `prepare-context`, `emit-event`, and `tick`.
- A Codex operator can use global and project `AGENTS.md` plus optional skill or wrapper integration to call the same OpenDream commands.
- An OpenClaw operator can wire planner and worker events into OpenDream and inject prompt-ready memory before tasks.
- Adapter docs are runnable and stay consistent with the canonical CLI surface.

## Acceptance criteria
- [x] AC-1: `.meta/spec-adapters/claude-code/README.md` exists with a runnable setup path using Claude hooks and skills
- [x] AC-2: `.meta/spec-adapters/codex/README.md` exists with runnable setup using AGENTS layering and optional skill or wrapper integration
- [x] AC-3: `.meta/spec-adapters/openclaw/README.md` exists with runnable event emission and context injection examples
- [x] AC-4: each adapter pack includes at least one example payload or script that calls real `opendream` commands
- [x] AC-5: adapter files remain non-normative and point back to canonical sources rather than redefining policy
- [x] AC-6: `make verify` includes adapter smoke checks

## Edge cases
- framework not installed locally
- hooks firing when workspace path is missing
- multiple repos open at once
- maintenance called repeatedly with no work pending
- prompt context excluding contested memory by default

## Required verifiers
- unit tests: no
- integration tests: yes, adapter smoke tests that validate file presence and example command integrity
- evals / scenario checks: no
- manual verification: yes, run the Claude Code and Codex wrapper scripts in temp workspaces

## Risks
- adapter docs drift from canonical CLI behavior
- adapter files become accidental policy surfaces
- too much framework-specific complexity leaks into the core runtime

## Links
- `../../docs/adr/ADR-001-canonical-spec-surface.md`
- `../../specs/403-runtime-integration-layer/spec.md`
- `../../README.md`
