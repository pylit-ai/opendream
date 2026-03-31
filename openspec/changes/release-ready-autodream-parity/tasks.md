## 1. Integrated Performance Gate

- [x] 1.1 Add `performance-eval` stage to `scripts/verify.py` using hermetic temp workspace
- [x] 1.2 Add `eval-performance` stage to `scripts/release_check.py` in clean-venv environment
- [x] 1.3 Include `performance_scorecard` key in release manifest JSON
- [x] 1.4 Verify `make verify` fails when scorecard threshold not met

## 2. AutoDream Comparison Harness

- [x] 2.1 Create `docs/benchmarks/autodream-comparison.md` with 7-dimension comparison table
- [x] 2.2 Add evidence citations for each AutoDream claim (official docs, GitHub issues, public analysis)
- [x] 2.3 Add code/test references for each OpenDream claim
- [x] 2.4 Add honest limitations section with specific gaps and next steps
- [x] 2.5 Add reproduction instructions referencing `make verify` and `eval performance`

## 3. Benchmark Documentation and FAQ

- [x] 3.1 Create `docs/benchmarks/methodology.md` with evaluation dimensions, weighting, thresholds, and fixture rationale
- [x] 3.2 Create `docs/FAQ.md` covering: what, why, how different from AutoDream, what it doesn't do, privacy, license, limitations, benchmarks
- [x] 3.3 Verify README quickstart path works end-to-end in under 5 minutes

## 4. Release Evidence and Registry Reconciliation

- [x] 4.1 Audit `specs/registry.yaml` — update status fields to match actual implementation state
- [x] 4.2 Create extended performance eval fixture at `opendream/fixtures/performance_eval_extended.json`
- [x] 4.3 Run `make verify` — all stages including new performance-eval pass
- [x] 4.4 Run `make release-check` — manifest includes performance scorecard and all stages pass
