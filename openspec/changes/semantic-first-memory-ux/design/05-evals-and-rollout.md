# 05-evals-and-rollout.md

## Goal

Make semantic-first differentiation provable through context-efficiency and repeated-task evidence.

## Required measurements

Release evidence SHOULD include:
- startup-context token estimate
- task-context token estimate by profile
- raw candidate count vs injected count
- learned-context inclusion rate
- pruning savings by workspace fixture
- irrelevant-recall and stale-recall rates
- repeated-task outcome comparison across:
  - deterministic-only
  - semantic-first degraded
  - semantic-ready progressive mode

## Minimum release gate

Release should fail if:
- semantic-ready mode cannot demonstrate a pruning advantage over an unpruned baseline on benchmark fixtures
- semantic-first degraded mode is not clearly labeled in status/UI/docs
- the homogeneous-memory fixture is reported as healthy
- context assembly regresses into large undifferentiated startup memory

## Rollout order

1. contract and doctor fields
2. progressive context profiles and pruning metadata
3. web UI readiness/quality/context-preview surfaces
4. docs and playbooks
5. benchmark and release gates
