# 04-web-ui-and-review-flows.md

## Goal

Make the observe web UI the primary operator surface for semantic readiness, memory quality, and context preview.

## Header contract

The raw `Dream pipeline` selector should no longer be the primary control. The header should instead lead with:
- semantic readiness state
- active execution owner
- degraded reason when present
- one next action

Advanced raw mode controls MAY remain, but behind progressive disclosure.

## `/overview`

Overview SHOULD add:
- semantic readiness card
- memory-quality warning card
- pruning/context-budget card
- last semantic run evidence
- links to raw health, overview, and relevant artifacts

## `/settings`

Settings SHOULD become the setup and control center for:
- semantic-first vs deterministic-by-choice posture
- current execution strategy and trust notes
- blocked/rejected strategies with reasons
- remediation actions or generated next steps
- expandable raw configuration and JSON

## Context preview

Operators SHOULD be able to see, without reading logs:
- which profile is active
- what the raw candidate set looked like
- what was injected
- what was suppressed
- how much prompt budget was saved by pruning

## UX rules

- high-signal cards first, raw JSON second
- degraded states must be explicit and accessible, not implied by color alone
- every UI summary must link back to inspectable evidence
- the web app must not imply that semantic mode is running merely because a config value was written
