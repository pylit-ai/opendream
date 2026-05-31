# OpenDream CLI demos

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../../frontend/assets/logo/wordmark/vector/opendream_wordmark_primary_ink_dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="../../frontend/assets/logo/wordmark/vector/opendream_wordmark_primary_ink_light.svg">
    <img alt="OpenDream" src="../../frontend/assets/logo/wordmark/vector/opendream_wordmark_primary_ink_light.svg" width="420">
  </picture>
</p>

Short recorded demos for command reference pages, docs, launch notes, and walkthroughs. For a first product look, start with the browser UI recordings in [`ui-demos.md`](./ui-demos.md). Each CLI demo is rendered from the same deterministic fixture path used by the CLI tests and showcase docs.

## First-run path

![OpenDream CLI quick start](../assets/demos/01-first-run-local-memory.gif)

Creates a local OpenDream workspace, lets `init` activate configured agent surfaces by default, and checks human-readable status.

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

Imports local transcript sessions, runs a transcript-backed dream pass, then refreshes the read-only observability index.

![Agent contract export](../assets/demos/06-agent-contract.gif)

Shows the versioned machine-readable CLI contract for agents that need stable command inventory.

![Automation radar scaffold](../assets/demos/07-automation-radar.gif)

Scaffolds a recurring feature-radar dream job while keeping projections separate from canonical durable memory.

## Brand motion

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../../frontend/assets/animation/video/opendream_splash_wordmark_dark_preview.gif">
    <source media="(prefers-color-scheme: light)" srcset="../../frontend/assets/animation/video/opendream_splash_wordmark_light_preview.gif">
    <img alt="OpenDream crescent-D wordmark reveal" src="../../frontend/assets/animation/video/opendream_splash_wordmark_light_preview.gif" width="720">
  </picture>
</p>

The rolling-wave SVG loop is used in the web app loading state. The full-resolution crescent-`D` splash files are available for launch videos, release notes, and social cuts:
[`dark MP4`](../../frontend/assets/animation/video/opendream_splash_wordmark_dark_1920x1080.mp4),
[`light MP4`](../../frontend/assets/animation/video/opendream_splash_wordmark_light_1920x1080.mp4).

## Source media

GIFs are embedded above for broad README/docs compatibility. MP4 and WebM variants for CLI demos live beside them under `docs/assets/demos/` for websites and release assets. Browser UI recordings live under `docs/assets/demos/ui/`. Brand motion sources live under `frontend/assets/animation/`.
