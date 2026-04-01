# 09-meta-harness-optimization.md

## Goal
Use Meta-Harness ideas in two ways:

1. immediate environment bootstrap for coding tasks
2. offline search over harness variants for memory injection, retrieval policy, and dream prompts

## Licensing stance
The attached Meta-Harness artifact also does not expose an obvious license file in the uploaded root. Treat it as conceptual/reference material unless an explicit redistributable license is confirmed and recorded.

## Feature A — Environment bootstrap
Before agent loops start, capture:
- working directory
- repo tree sketch
- tool/language availability
- package managers
- memory mode / health / queue depth
- semantic provider health

Inject this into initial prompts or agent context to save early exploration turns.

## Feature B — Harness optimization
Search over:
- semantic dream prompt variants
- query-family selection policy
- retrieval fusion weights
- learned-context injection formatting
- gating thresholds
- memory-hurt penalties

## Safety rules
- optimization runs must use isolated workspaces / temp dirs
- search outputs are proposals until promoted
- release does not require a long search job in CI, but does require:
  - command surfaces
  - schemas
  - smoke tests
  - ablation docs
  - one validated toy optimization workflow
