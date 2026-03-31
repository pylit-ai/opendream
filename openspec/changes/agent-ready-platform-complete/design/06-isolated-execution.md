# 06-isolated-execution.md

## Goal
Allow future or bounded code-writing automation without permitting unattended mutation of the primary workspace.

## Rule
Any automation engine whose side-effect class is `code_mutation` MUST run in isolated worktree mode.

## Design
### Worktree manager
- create temp worktree from configured base ref
- run engine inside isolated worktree
- capture diff summary, checks, and cleanup result
- optionally preserve failed worktrees for debugging

### Job fields
- `execution_mode`
- `base_ref`
- `allow_primary_workspace_mutation` (must stay false for unattended jobs)
- `worktree_policy`
- `cleanup_policy`

### New CLI
- `opendream worktree create`
- `opendream worktree list`
- `opendream worktree cleanup`
- `opendream automation run --isolated`
- `opendream automation diff <run-id>`

### Approval
- code-mutation engines require explicit approval policy at registration time
- unattended runs without approval-capable policy are rejected
