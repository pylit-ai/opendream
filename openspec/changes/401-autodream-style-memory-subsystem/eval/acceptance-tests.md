# Acceptance Tests

## AT-01: Compact startup index
Given 100+ durable memory items
When consolidation runs
Then `memory/MEMORY.md` stays within configured max lines
And contains only concise entries with pointers

## AT-02: Lazy topic loading
Given semantic and procedural topic files exist
When a fresh session starts
Then only startup index is loaded
And topic files load on demand

## AT-03: Preference retention
Given "always use pnpm, not npm"
When a future session needs package commands
Then pnpm preference is retrieved and used

## AT-04: Project decision supersession
Given an old project decision and a later explicit replacement
When consolidation runs
Then old record becomes superseded
And new record becomes active
And startup index shows only active record

## AT-05: Contested fact handling
Given conflicting weak evidence
When consolidation runs
Then contested record is created
And contested record is excluded from startup index

## AT-06: Environment gotcha reuse
Given durable memory says local Redis is required for tests
When tests are run later
Then that requirement is retrieved before failure

## AT-07: Procedural workflow induction
Given three repeated successful task sequences
When consolidation runs
Then a procedural_workflow record is created
And future similar tasks retrieve it

## AT-08: Bootstrap category indexing
Given messy historical memory corpus
When bootstrap mode runs
Then category groupings are produced before apply
And low-confidence items are not promoted directly

## AT-09: Background non-blocking behavior
Given foreground agent work is active
When scheduled consolidation triggers
Then foreground latency budget is not materially exceeded
And consolidation runs asynchronously

## AT-10: Single-writer safety
Given two consolidation triggers fire concurrently
When both attempt writes
Then only one acquires lock
And the other retries or exits cleanly
And no malformed files are produced

## AT-11: Auditability
Given any durable mutation occurs
When it completes
Then an audit diff and run summary exist
And source event ids are present

## AT-12: No code writes
Given consolidation run occurs
When run completes
Then only memory store paths changed

## AT-13: Decay of stale noise
Given stale never-retrieved low-confidence pending items
When decay sweep runs
Then they are quarantined or removed from startup index

## AT-14: License-clean implementation
Given the implementation repository
When scanned for third-party imports/snippets/prompts from the reviewed repos
Then no copied code or prompt text is required for correctness
