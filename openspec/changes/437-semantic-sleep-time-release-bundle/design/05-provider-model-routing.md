# 05-provider-model-routing.md

## Goal
Keep semantic mode model-backed but vendor-agnostic.

## Provider abstraction
Each provider entry declares:
- provider id
- transport
- model id
- context window
- cost hints
- rate-limit hints
- supports structured output?
- supports reasoning effort?
- supports tool use?
- supports local/offline use?

## Model roles
At minimum support separate model slots for:
- anticipation planner
- semantic synthesizer
- semantic verifier
- optional benchmark judge
- optional harness optimizer proposer

## Fallback policy
- provider health check on startup and before semantic runs
- explicit fail-fast vs fallback-to-deterministic policy
- benchmark harness may require specific provider classes for reproducibility

## Release requirement
Semantic mode is not considered implemented if the code only compiles but there is no working provider registry, health check, and contract-tested structured output path.
