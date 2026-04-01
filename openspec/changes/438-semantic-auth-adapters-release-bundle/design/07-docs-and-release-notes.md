# 07-docs-and-release-notes.md

## Goal
Remove misleading wording from operator docs and release communication.

## Required doc changes
- README: replace vague “requires provider configuration” language with execution/auth matrix
- FAQ: answer “do I need extra API keys?” with a table, not a shrug
- coding-agents docs: add setup quickstarts and adapter matrix
- automation playbook: clearly separate Layer C local direct-provider vs delegated adapters
- benchmark/comparison docs: ensure claims match actual supported execution modes
- CHANGELOG / release notes: describe what shipped and what is delegated

## Required release-note principle
Never describe a vendor-delegated run as if OpenDream itself acquired or reused the vendor’s OAuth session directly.

## Wording checks
Add automated wording checks for phrases that imply:
- universal OAuth reuse
- provider-backed local execution when only delegated mode exists
- magic “just works” setup where manual vendor-side scheduling is still required
