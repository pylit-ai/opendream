# NORTHSTAR

## Mission
Build OpenDream for developers and platform teams building coding agents so they can give those agents durable, auditable project memory with radically less repetition, context loss, and silent drift.

## Why this should exist
The status quo fails because:
1. transcript-only agents forget important project constraints and force users to restate them every session.
2. append-only notes and ad hoc scratchpads accumulate noise, contradictions, and stale instructions.
3. current memory systems are often opaque, hard to audit, and too risky to trust in production coding workflows.

## Who it is for
- Primary user: developers operating long-lived coding agents on real repositories
- Secondary user: platform teams building or embedding agent runtimes and needing a clean-room memory layer
- Explicitly not for: general-purpose consumer chat history, social memory products, or cloud-first knowledge-management suites

## What winning looks like in 24 months
- repeated-task success measurably improves because agents reuse correct procedural and project memory
- operators can inspect, diff, and verify every durable memory mutation without reading prompts
- OpenDream is the default local-first memory substrate for coding-agent workflows across multiple repos and runtimes

## Product thesis
We believe:
- durable agent memory should be typed, provenance-preserving, and explicitly resistant to contradiction and staleness
- local-first, auditable storage earns more operator trust than hidden remote memory systems
- compact startup memory plus lazy topic loading is the right shape for long-running coding agents

## Strategic pillars
1. Trustworthy memory
2. Operator control
3. Portable clean-room implementation

## Non-goals
- We are not building a full autonomous software engineer that edits product code without operator control.
- We will not optimize for multi-tenant cloud sync in v1.
- We will not support hidden, unaudited durable memory mutation without explicit re-evaluation.

## Quality bar
The product must feel:
- deterministic
- inspectable
- boringly safe

## Durable constraints
- Protect user trust over short-term velocity.
- Prefer reversible architecture early.
- Optimize for clear operator control and observability.
- Do not hide complexity; encapsulate it.

## Canonical tradeoff policy
When tradeoffs conflict:
1. Safety / correctness
2. User trust
3. Operability
4. Simplicity
5. Speed of shipping

## Kill criteria
We should reconsider the project if:
- durable memory does not produce a meaningful improvement over append-only notes on repeated coding tasks
- operators still do not trust the system because contradiction, staleness, or auditability failures remain common
- the local-first approach cannot meet the product’s ergonomics without forcing an unwanted remote control plane
