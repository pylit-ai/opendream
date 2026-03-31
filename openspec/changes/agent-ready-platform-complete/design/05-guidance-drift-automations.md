# 05-guidance-drift-automations.md

## Goal
Turn repeated friction into reviewable improvements for repo instructions and skills.

## Inputs
- task outcomes
- user corrections
- verification failures
- repeated review comments
- repeated shell commands / loops
- failed or manually corrected automations

## Pipeline
1. collect candidate friction signals
2. cluster repeats by signature
3. score severity + recurrence + leverage
4. map each cluster to a target surface:
   - root guidance
   - path-scoped guidance
   - skill description
   - hook rule
   - package generation metadata
   - verification runbook
5. emit a reviewable proposal record with:
   - summary
   - evidence refs
   - proposed patch target
   - confidence
   - risk
   - suggested reviewer

## Promotion model
- proposals remain automation records by default
- promotion command can write an OpenSpec proposal bundle or patch suggestion
- direct mutation of canonical docs is not allowed without promotion
