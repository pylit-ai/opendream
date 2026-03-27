# Eval Plan: AutoDream-Style Memory Subsystem

## Objective
Measure whether the subsystem improves long-horizon coding-agent performance without causing stale-memory failures, memory corruption, contradiction pollution, or startup-context bloat.

## Evaluation dimensions
1. write precision
2. retrieval precision
3. contradiction handling
4. startup budget compliance
5. latency overhead
6. procedural reuse benefit
7. concurrency safety
8. audit completeness
9. bootstrap migration quality

## Scenarios

### Scenario A: Preference retention
Inject durable preferences:
- package manager
- formatter
- test command
- branch habits

Measure:
- durable write precision
- future retrieval correctness

### Scenario B: Project decision supersession
Inject:
- original architecture decision
- later superseding decision
- temporary contested rollback

Measure:
- active vs superseded state correctness
- contested exclusion from startup index

### Scenario C: Environment gotchas
Inject:
- required local Redis
- specific env var
- language/runtime version caveat
- flaky test workaround

Measure:
- future task success rate
- retrieval ordering

### Scenario D: Workflow induction
Repeat similar task sequence across sessions:
- update schema
- regenerate client
- run migration
- run tests
- verify formatting

Measure:
- emergence of procedural_workflow record
- repeated-task improvement

### Scenario E: Bootstrap migration
Start with a large messy historical memory corpus.

Measure:
- category inventory quality
- high-confidence apply precision
- raw evidence preservation
- startup index cleanliness

### Scenario F: Concurrency
Run:
- two foreground remember flows
- one background consolidation run

Measure:
- no corruption
- no silent overwrite
- lock fairness
- recovery after stale lock

## Baselines
1. no persistent memory
2. append-only memory
3. consolidated semantic-only memory
4. full system (semantic + procedural + decay + supersession)

## Metrics
- candidate acceptance precision
- durable write precision
- duplicate merge correctness
- top-k retrieval precision
- irrelevant recall rate
- contested-memory startup exposure
- startup index token/line count
- p50 / p95 retrieval latency
- step reduction on recurring tasks
- task success delta
- corruption count
- silent overwrite count
- audit coverage rate

## Success thresholds
- durable write precision >= 0.90
- top-5 retrieval precision >= 0.85
- contested startup exposure = 0
- startup index <= configured max lines
- no silent overwrite events
- no corruption events
- repeated-task success improvement >= 10% over append-only baseline
- workflow-enabled step reduction >= 10%

## Human review loop
Review:
- 100 candidate writes
- 100 retrievals
- all contested records
- all superseded records
- all bootstrap apply actions
