# 01-runtime-boundaries.md

## Goal
Make “read code / write memory only” an enforced runtime contract.

## Boundary model
Background maintenance agents may:
- read the repo within configured bounds
- read transcripts through probe + bounded-window mechanisms
- write only under:
  - `memory/`
  - bounded audit artifact directories
  - optional delegated semantic inbox paths if already part of canonical design

They may not:
- edit source code
- create files outside the allowed memory/audit paths
- invoke arbitrary mutation tools

## Enforcement
- path allowlist enforcement in worker runtime
- no-code-write diff verifier
- explicit runtime mode in worker reports
- failure on attempted out-of-bounds writes

## Why
Policy and tests are not enough. Maintenance workers need hard edges.
