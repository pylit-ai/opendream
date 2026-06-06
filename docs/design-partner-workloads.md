# Design Partner Workloads

OpenDream needs real, long-running workflows to test where agent memory helps, goes stale, conflicts, or makes an agent worse. Fixture-based release checks are useful, but they are not evidence of broad real-world superiority.

Useful workloads include:

- an agent forgot a build or deployment constraint;
- an agent reused a stale migration note;
- an agent contradicted the current project convention;
- retrieval added irrelevant context to a task;
- multiple agents produced conflicting memory;
- memory belonged at a personal, project, team, path, or global boundary;
- a memory update should have required review before later use;
- the same context needed to move between different agent runtimes.

## What To Capture

For each workload, record:

1. the task and agent runtime;
2. the source events available to OpenDream;
3. the context selected and excluded;
4. the boundary or scope applied;
5. whether memory improved or degraded the result;
6. stale, conflicting, or unsupported records;
7. the review decision and expected correction.

Do not include secrets, customer data, or private repository content in public reports. Sanitized fixtures should preserve the failure shape without preserving sensitive content.
