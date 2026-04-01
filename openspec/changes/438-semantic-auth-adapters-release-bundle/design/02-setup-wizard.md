# 02-setup-wizard.md

## Goal
Give operators one command that tells the truth.

## New command
`opendream semantic setup --workspace <ws> [--prefer no-extra-key|direct-provider]`

## Output sections
- detected environments
- candidate strategies
- recommended strategy
- why it was chosen
- what still must be configured
- trust/safety notes
- next commands

## Report shape
The setup wizard writes:
- terminal summary
- machine-readable `semantic-setup-report.json`
- optional generated adapter artifacts

## Rules
- setup must never silently choose a vendor-delegated path that cannot return artifacts into OpenDream
- setup must never claim that a vendor account session can be borrowed directly by OpenDream unless that exact path is implemented and supported
- setup must explain why unsupported strategies were rejected
