# OpenDream UI demos

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../../frontend/assets/logo/wordmark/vector/opendream_wordmark_primary_ink_dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="../../frontend/assets/logo/wordmark/vector/opendream_wordmark_primary_ink_light.svg">
    <img alt="OpenDream" src="../../frontend/assets/logo/wordmark/vector/opendream_wordmark_primary_ink_light.svg" width="420">
  </picture>
</p>

These short recordings are the best first look at OpenDream's product surface. They use a disposable sample workspace and show the browser UI that sits on top of the local memory store.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../assets/demos/ui/opendream-ui-overview-dark.gif">
  <source media="(prefers-color-scheme: light)" srcset="../assets/demos/ui/opendream-ui-overview.gif">
  <img alt="OpenDream UI overview" src="../assets/demos/ui/opendream-ui-overview.gif">
</picture>

## Product tour

| Demo | Light | Dark | What it shows |
|------|-------|------|---------------|
| Current workspace overview | [MP4](../assets/demos/ui/light-current-overview.mp4) | [MP4](../assets/demos/ui/dark-current-overview.mp4) | Recent activity, Dream run results, prepared context, and reusable memory in one product loop. |
| Dream import and run | [MP4](../assets/demos/ui/light-dream-import-and-run.mp4) | [MP4](../assets/demos/ui/dark-dream-import-and-run.mp4) | The Dreams page with transcript import controls, created records, and a step-by-step run timeline. |
| Context and review | [MP4](../assets/demos/ui/light-context-and-review-proof.mp4) / [WebM](../assets/demos/ui/light-context-and-review-proof.webm) | [MP4](../assets/demos/ui/dark-context-and-review-proof.mp4) / [WebM](../assets/demos/ui/dark-context-and-review-proof.webm) | Prepared context, source links, and review decisions with populated current data. |
| Shared agent memory | [MP4](../assets/demos/ui/light-sessions-and-diff.mp4) / [WebM](../assets/demos/ui/light-sessions-and-diff.webm) | [MP4](../assets/demos/ui/dark-sessions-and-diff.mp4) / [WebM](../assets/demos/ui/dark-sessions-and-diff.webm) | Agent-attributed sessions from Codex, Claude Code, and Cursor, followed by the run diff that shows what changed. |

## Multiple agents, one memory plane

OpenDream can collect attributable events and prepared contexts from different
coding agents across sessions in the same workspace. Each agent keeps its own
runtime and built-in memory; OpenDream supplies the shared, local, reviewable
project memory layer between them.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../assets/demos/ui/dark-shared-memory-sessions.png">
  <source media="(prefers-color-scheme: light)" srcset="../assets/demos/ui/light-shared-memory-sessions.png">
  <img alt="OpenDream Sessions view showing Codex, Claude Code, and Cursor contributions" src="../assets/demos/ui/light-shared-memory-sessions.png">
</picture>

## Companion CLI clips

The CLI recordings remain useful as documentation accompaniments when a reader needs exact command shape or terminal behavior: [`cli-demos.md`](./cli-demos.md).

## Source media

The README embeds light and dark GIF previews for broad compatibility. Full current MP4 cuts live under `docs/assets/demos/ui/`; the context and review cut also includes WebM alternatives for docs and social reuse.
