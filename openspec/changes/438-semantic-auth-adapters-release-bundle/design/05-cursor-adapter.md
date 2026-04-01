# 05-cursor-adapter.md

## Goal
Support a no-extra-key semantic path using Cursor Automations where the operator is already using Cursor.

## Model
A Cursor Automation runs a background cloud agent on a schedule or event trigger.
The automation writes a bounded semantic envelope artifact into the repository (or a dedicated inbox path in the working tree), which OpenDream ingests on the next run.

## Why artifact-in-repo
This avoids assuming direct access from Cursor cloud agents into an operator’s local OpenDream process while keeping provenance inspectable.

## Adapter responsibilities
- scaffold automation prompt/instructions
- scaffold return-path artifact layout
- scaffold validation rules for the envelope
- expose status and docs for UI/account-backed use
- optionally document API-key programmatic mode separately, but do not make it the default recommendation

## Key rule
The no-extra-key default for Cursor is the **account-backed automation UI path**, not the API.
