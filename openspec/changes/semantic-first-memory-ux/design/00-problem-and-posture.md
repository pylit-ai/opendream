# 00-problem-and-posture.md

## Problem

Semantic mode currently reads as a capability flag more than a product posture. That is too weak.

The differentiated promise is not "OpenDream can call a model." The promise is:
1. more useful memory under repeated coding work,
2. less prompt bloat through consolidation and pruning,
3. explicit evidence for why a memory item is present or absent,
4. truthful degraded behavior when semantic execution is unavailable.

If those properties are not visible in setup, status, and context assembly, operators will rationally treat semantic mode as branding layered on top of deterministic capture.

## Product posture

Semantic mode is the default posture because it is the differentiated path. Deterministic mode remains important, but as:
- an explicit operator choice,
- a safe degraded fallback,
- and a debugging/control surface.

The default user story is therefore:
- OpenDream tries to make semantic execution real.
- If it cannot, it says so plainly.
- It still captures safely while showing the operator what is missing.

## Design principles

1. **Truth before aspiration** — semantic-first does not mean lying about readiness.
2. **Progressive disclosure wins on context budget** — semantic memory should compress what enters the prompt and expand only when relevance is strong.
3. **Pruning is a product feature** — semantic dreaming is valuable partly because it deletes, suppresses, and downgrades the right things.
4. **One high-signal answer** — the normal path must be understandable from `status`, `doctor`, `/overview`, and `/settings`.
5. **Evidence stays visible** — operators can always inspect raw records, reports, and reasons.
6. **Release claims require proof** — semantic mode is not complete unless it demonstrates context-efficiency and repeated-task benefit.
