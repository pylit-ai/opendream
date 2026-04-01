# 05-cursor-automation-executor.md

## Goal
Support recurring semantic work through Cursor Automations without defaulting users into separate API-key programmatic mode.

## Preferred path
- account-backed automation in Cursor UI / cloud-agent workflow
- bounded artifact-in-repo return path into `.opendream/inbox/semantic/cursor/`

## Secondary path
- document API-key programmatic mode separately for operators who explicitly want it
- do not recommend it first when the account-backed automation path is supported

## Important distinction
Cursor owns execution.
OpenDream owns ingestion, review, memory promotion, and scorecards.
