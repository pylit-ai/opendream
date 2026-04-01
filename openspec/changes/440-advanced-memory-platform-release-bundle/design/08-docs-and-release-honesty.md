# 08-docs-and-release-honesty.md

## Goal
Make the docs match the runtime exactly.

## Required changes
- README semantic section becomes an execution/auth matrix
- FAQ answers “Do I need extra API keys?” precisely
- coding-agents docs add direct-provider vs delegated quickstarts
- automation playbook shows delegated Layer C variants
- benchmark docs describe official/public evidence and OpenDream’s own scorecards without depending on unofficial implementation claims
- release notes distinguish:
  - what OpenDream directly does
  - what vendor runtimes do on OpenDream’s behalf
  - what is unsupported

## Wording gate
Fail release if wording implies:
- universal OAuth reuse
- hidden direct-provider execution when only delegated mode exists
- unsupported auth shortcuts
