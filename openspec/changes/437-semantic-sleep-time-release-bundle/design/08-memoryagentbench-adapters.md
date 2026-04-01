# 08-memoryagentbench-adapters.md

## Licensing stance
The attached MemoryAgentBench archive does not show an obvious redistributable license grant in the uploaded root. Unless a redistributable upstream license is confirmed and recorded, do not vendor its code into the release artifact.

## Clean-room integration plan
- implement dataset/task adapters from public paper/task descriptions and user-provided local copies
- support loading user-supplied datasets or repo-local fixtures shaped like the benchmark
- implement scoring contracts that measure AR / TTL / LRU / CR using OpenDream-native reports

## Required commands
- `opendream eval memory-agent-bench --config <path>`
- `opendream eval memory-agent-bench --mode deterministic|semantic|hybrid`
- `opendream eval memory-agent-bench --export <dir>`

## Required outputs
- per-competency scores
- aggregate weighted score
- confusion / failure taxonomy
- traces linking failures to retrieval, memory writing, conflict handling, or reasoning layer
