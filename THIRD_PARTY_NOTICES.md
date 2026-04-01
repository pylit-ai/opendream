# Third-Party Notices

This file documents third-party works referenced, adapted, or reused in OpenDream's semantic sleep-time mode and benchmark suite.

## Sleep-time Compute

- **Source**: Google DeepMind — Sleep-time Compute (2025)
- **License**: MIT
- **What we use**: Concepts and selective code patterns for offline semantic anticipation, query-family planning, and learned-context synthesis.
- **How we use it**: Direct reuse with attribution where applicable. MIT license terms are satisfied by this notice and in-code comments referencing the origin.

## MemoryAgentBench

- **Source**: MemoryAgentBench benchmark suite
- **License**: No clear open-source license at time of integration (2026-03)
- **What we use**: Competency definitions (Accurate Retrieval, Test-Time Learning, Long-Range Understanding, Conflict Resolution) as evaluation dimensions.
- **How we use it**: **Clean-room adapters only.** No code, fixtures, datasets, or prompts are vendored from the original repository. Our adapters (`opendream/benchmark_adapters.py`) implement the competency measurements independently using OpenDream's own retrieval and storage APIs. If an explicit permissive license is published, this policy may be revised.

## Meta-Harness

- **Source**: Meta-Harness environment bootstrap and optimization framework
- **License**: No clear open-source license at time of integration (2026-03)
- **What we use**: The concept of environment bootstrap capture and harness parameter optimization for coding-agent contexts.
- **How we use it**: **Clean-room adapters only.** No code is vendored. Our implementation (`opendream/harness_optimizer.py`) captures environment context and runs optimization independently. If an explicit permissive license is published, this policy may be revised.

---

## Policy

- **MIT-licensed sources**: Selective reuse with attribution is permitted. Attribution appears in this file and in relevant source comments.
- **Unlicensed or ambiguously-licensed sources**: Clean-room adapter policy applies. We implement the same competency measurements or concepts but write all code independently, using only publicly documented APIs and definitions. No vendored code, fixtures, or prompts.
- **Updates**: If license status changes for any listed project, update this file and re-evaluate the adapter policy.
