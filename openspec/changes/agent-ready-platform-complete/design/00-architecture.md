# 00-architecture.md

## Architecture decision
Treat “agent readiness” as a control-plane layer above the existing OpenDream runtime.

### Core decomposition
1. **Canonical governance layer**
   - `AGENTS.md`
   - `CONSTITUTION.md`
   - `docs/governance/*`
   - canonical specs and ADRs

2. **Contract layer**
   - schemas
   - contract export
   - fixture examples
   - version map

3. **Distribution layer**
   - package/plugin generators
   - vendor package manifests
   - thin installable shims
   - marketplace metadata

4. **Execution layer**
   - engine registry
   - built-in engines
   - plugin-backed engines
   - worktree isolation
   - approval gates

5. **Improvement layer**
   - guidance-drift analyzers
   - proposal emitters
   - promotion/rejection review flows

### Key rule
Distribution surfaces are generated from canonical inputs.
They are never independent policy roots.

### Why this design
This keeps the repo’s current strengths:
- one canonical home per concept
- thin adapters
- local-first inspectability
- explicit contracts
- auditable background execution
