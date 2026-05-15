# Claims Matrix

This matrix maps prominent public claims to evidence and public wording.

| Claim | Allowed wording | Evidence | Limit |
| --- | --- | --- | --- |
| Local-first memory | "OpenDream stores runtime memory in the selected local workspace by default." | `opendream/storage.py`, `tests/test_memory_cli.py`, `tests/test_no_network_defaults.py` | Provider integrations are explicit setup paths. |
| Coding-agent activation | "OpenDream can activate managed instruction surfaces for supported coding agents." | `opendream/activation.py`, `tests/test_agent_ready_guidance.py` | Users remain responsible for reviewing generated files. |
| Observability UI | "The observe UI renders local workspace state and graph views from public static assets." | `opendream/webapp.py`, `tests/test_webapp_static.py`, `tests/test_webapp_graph_route.py` | It is a local development UI, not a hosted service. |
| Benchmark scorecards | "Release checks include fixture-driven scorecards." | `docs/benchmarks/methodology.md`, `scripts/release_check.py` | Fixture results are not external benchmark leadership claims. |
| Semantic mode | "Semantic mode reports ready, degraded, or setup-required state." | `docs/benchmarks/semantic-mode.md`, `tests/test_release_check_semantic.py` | Direct-provider execution needs operator configuration. |
| Clean-room posture | "Public code is maintained with explicit clean-room and vendored-asset provenance." | `CLEAN_ROOM.md`, `THIRD_PARTY_NOTICES.md`, `scripts/check_provenance_risk.py` | This is release hygiene, not legal advice. |

## Forbidden Public Wording

Do not add these terms to public docs unless the surrounding text is explicitly
negative or scoped as a limitation:

- state-of-the-art
- guaranteed
- best
- first
- leak-derived
- undisclosed provider/account details
- non-public URL
- proprietary-system superiority claims unless backed by live, cited,
  independently reproducible evidence

Run:

```bash
python scripts/check_provenance_risk.py
```
