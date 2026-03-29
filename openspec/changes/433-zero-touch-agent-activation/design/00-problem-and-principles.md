# Problem and principles

## Problem
OpenDream still presents integration as CLI glue plus examples. That leaves activation success to operator memory instead of product behavior.

## Product contract
If a supported agent is configured in the workspace, OpenDream should be able to activate it, verify it, and repair it without manual copying from `.meta/`.

## Principles
1. Native surface first.
2. Wrapper only where native lifecycle hooks are insufficient.
3. Managed blocks, never blind overwrite.
4. Idempotent activation and one-command repair.
5. Release fails if configured agents still require manual glue.
