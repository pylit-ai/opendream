# 05-privacy-and-safety.md

## Privacy rules
- do not scan arbitrary disks or `$HOME` by default
- do not upload catalog contents
- do not include secrets, tokens, or raw durable memory content in catalog entries

## Safety rules
- forgetting a workspace removes only the catalog entry, not the repo-local state
- scans must never mutate workspace-local memory
- dashboard actions that call repair/activate/service commands must use explicit existing commands, not hidden mutations

## Why this matters
A “global dashboard” becomes creepy very quickly if it starts acting like spyware instead of a boring local index.
