# 03-grep-first-transcript-probing.md

## Goal
Make transcript access probe-first and bounded.

## Flow
1. `orient` identifies anchor entities, candidate topics, relation ids, and query families
2. `probe` issues grep/regex/term scans against transcript indexes or files
3. if hits exist, `bounded_read` loads only small windows around the hits
4. only if confidence remains low may semantic/rerank escalation happen
5. full-corpus replay remains disabled by default

## Budgets
- max probe count
- max total transcript bytes
- max hits expanded
- max lines per bounded window

## Reportability
Every dream report records:
- probes run
- hits found
- windows read
- escalations triggered
- why escalation happened

## Why
This preserves bandwidth discipline and forces targeted evidence gathering.
