# 04-automation-engine-registry.md

## Goal
Make `skill_ref` real without allowing arbitrary unattended execution.

## Design
### Engine registry
Every automation job resolves through:
- built-in engine id (`builtin://...`)
- packaged engine id (`plugin://publisher/name@version`)
- disabled / unknown engine => reject

### Engine contract
Each engine declares:
- engine id
- title
- version
- category
- accepted input selector shapes
- output record schema
- side-effect class (`read_only`, `proposal_only`, `code_mutation`)
- execution requirements
- review policy
- approval policy
- package or local source

### Built-ins in this slice
- `builtin://projection-engine`
- `builtin://guidance-drift`
- `builtin://release-scan`
- `builtin://bug-radar`
- `builtin://feature-backlog`

### New CLI
- `opendream engine list`
- `opendream engine inspect <id>`
- `opendream engine validate <manifest>`
- `opendream engine install <path-or-package>`
- `opendream engine disable <id>`

## Why
This keeps automation composable and extensible while preventing “just run some SKILL.md on cron” from becoming the operational model.
