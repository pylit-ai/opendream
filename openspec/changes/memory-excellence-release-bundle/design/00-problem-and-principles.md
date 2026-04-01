# 00-problem-and-principles.md

## Problem
Compact memory alone is not enough. A memory system can be compact and still be wrong, stale, or operationally unsafe.

## Design principles
1. **Truth before convenience** — concrete claims need provenance or verification.
2. **Bandwidth discipline** — startup context stays tiny; transcript access is probe-first.
3. **Canonical typed state** — markdown is a view, not the database.
4. **Relations matter** — contradiction and supersession are central, not decorative metadata.
5. **Maintenance is constrained** — background memory workers are limited maintenance agents, not general planners.
6. **Everything is auditable** — every write, repair, downgrade, or promotion can be inspected.
7. **Evaluation decides** — release claims require scorecards, not vibes.

## Product posture
This phase does not imitate note-oriented memory systems. It turns OpenDream into a verified, bounded, relation-aware memory runtime.
