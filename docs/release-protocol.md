# Release Protocol

This public protocol describes evidence required before a release candidate is
advertised. Private operator notes and account-specific steps stay outside the
public repository.

## Agent Handoff

- Work on a branch named for the ticket or milestone, such as
  `launch/odl-020-provenance` or `codex/opendream-public-launch-code-readiness`.
- Keep public changes limited to code, tests, docs, CI, release metadata, and
  public-safe assets.
- Record ticket evidence in the private completion ledger before marking an
  `ODL-*` item done.
- Do not commit generated local agent state, private overlay paths, secrets,
  private provider/account names, or non-public URLs.

## Local Gates

```bash
make setup
make verify
python scripts/release_check.py --timeout-seconds 300
python -m json.tool .tmp/release-check/release_manifest.json >/dev/null
```

## Release Evidence

Release evidence must include:

- public branch and commit SHA
- dirty-state check
- boundary, package, provenance, vendor, and public-artifact scans
- test and eval status
- built artifact hashes
- unresolved risks and waivers
- post-publish rollback/yank plan

Use `RELEASE_EVIDENCE_TEMPLATE.md` for the public-safe shape. Private
writeback, Linear notes, and operator account checks belong in the private
overlay.
