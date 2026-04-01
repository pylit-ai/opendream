# 03-codex-account-executor.md

## Goal
Support a low-friction semantic path using Codex account-backed auth where OpenAI officially supports trusted local/private automation.

## Implementation model
- OpenDream shells out to Codex CLI through a narrow wrapper
- Codex manages its own account authentication state
- OpenDream requests structured semantic output and ingests the result through the same validation path used elsewhere

## Requirements
- detect Codex presence and project trust
- detect likely account-backed auth availability without exposing secrets
- warn or reject in public/untrusted contexts
- expose remediation to direct-provider mode when needed

## Non-goals
- manual token extraction
- generic bearer-token reuse outside Codex-managed flows
