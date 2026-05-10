# OpenDream CLI demos

Short recorded demos for README, docs, launch notes, and walkthroughs. Each demo is rendered from the same deterministic fixture path used by the public CLI tests and showcase docs.

## First-run path

![OpenDream CLI quick start](../assets/demos/01-first-run-local-memory.gif)

Creates a local OpenDream workspace, activates configured agent surfaces when present, and checks human-readable status.

## Agent context and safety

![Agent context retrieval](../assets/demos/02-agent-context-retrieval.gif)

Shows `prepare-context` selecting prior repo guidance for the next coding-agent task.

![Memory safety abstention](../assets/demos/03-memory-safety-abstention.gif)

Shows an unrelated query returning a clear no-match instead of injecting irrelevant memory.

## Evaluation proof

![Showcase evaluation proof](../assets/demos/04-eval-proof.gif)

Runs the coding-agent showcase eval and summarizes stateless score, memory-assisted score, lift, and negative controls.

## Advanced runtime paths

![Dream and Observe](../assets/demos/05-dream-observe.gif)

Runs a transcript-backed dream pass, then refreshes the read-only observability index.

![Agent contract export](../assets/demos/06-agent-contract.gif)

Shows the versioned machine-readable CLI contract for agents that need stable command inventory.

![Automation radar scaffold](../assets/demos/07-automation-radar.gif)

Scaffolds a recurring feature-radar dream job while keeping projections separate from canonical durable memory.

## Source media

GIFs are embedded above for broad README/docs compatibility. MP4 and WebM variants live beside them under `docs/assets/demos/` for websites and release assets.
