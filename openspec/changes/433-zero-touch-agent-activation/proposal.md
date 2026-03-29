# 433-zero-touch-agent-activation

## Why
OpenDream has durable memory, queued dream work, and explicit service lifecycle controls, but operators still have to mentally compile those pieces into live agent integration. The product contract should move from "here are commands and examples" to "supported configured agents activate from one command."

## Goal
Make configured repo-local agents work automatically after `init --activate-configured` or `activate`.

## What Changes
- add an activation surface for supported agents
- persist detection and activation state under `.opendream/`
- install managed native surfaces where available and a repo-local wrapper where native hooks are insufficient
- add doctor and repair flows plus machine-readable reports
- update verification to fail if supported targets still require manual glue

## Non-goals
- hidden privileged installs
- cloud orchestration
- destructive overwrite of unrelated config

## Success criteria
- supported configured agents are detected and activated
- managed surfaces are idempotent and reversible
- drift is diagnosable and repairable
- release verification covers activation end to end
