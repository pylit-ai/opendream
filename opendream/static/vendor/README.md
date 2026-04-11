# Vendored third-party JS

This directory holds pinned third-party JavaScript used by the `/graph`
explorer. Files are committed verbatim so the observability dashboard works
offline and behind air-gapped networks.

## Contents

| File | Version | License | Source |
|------|---------|---------|--------|
| `sigma.min.js` | 3.0.2 | MIT | https://cdnjs.cloudflare.com/ajax/libs/sigma.js/3.0.2/sigma.min.js |
| `graphology.umd.min.js` | 0.25.4 | MIT | https://cdnjs.cloudflare.com/ajax/libs/graphology/0.25.4/graphology.umd.min.js |
| `graphology-layout-forceatlas2.min.js` | 0.10.1 | MIT | built from `npm:graphology-layout-forceatlas2@0.10.1` using esbuild (package has no pre-built UMD/dist; global: `GraphologyLayoutForceAtlas2`) |

**Note on graphology-layout-forceatlas2:** The original plan referenced
`https://cdn.jsdelivr.net/npm/graphology-layout-forceatlas2@0.10.1/dist/graphology-layout-forceatlas2.min.js`
but that path 404s — the package ships only CJS source files with no `dist/`
directory. The bundle was produced locally:
`esbuild node_modules/graphology-layout-forceatlas2/index.js --bundle --minify --format=iife --global-name=GraphologyLayoutForceAtlas2`

## sha256 checksums (verify with `shasum -a 256 *.js`)

- `sigma.min.js`: `be6f790da9c1856765b1c430de3b1aac50433223361870edb3097a9868218a88`
- `graphology.umd.min.js`: `641ea047e2f414dead999769d62567ce3c6f1ddc334f1e728bd5edb19d337977`
- `graphology-layout-forceatlas2.min.js`: `03cee0f88c84726f8d27e31772676feec3a5adb665f5a604e3758b449dd84f4a`

Note: checksums above are for the bare downloaded/built files before the
provenance header comment was prepended. The header adds ~150 bytes; the
sha256 of the file on disk will differ slightly from the upstream sha256.

## Refresh procedure

1. Look up the desired version on cdnjs.com / jsdelivr.com.
2. Re-run the `curl -fsSL -o ...` commands with the new URLs (see the
   `opendream/static/vendor/` section of `docs/superpowers/plans/2026-04-10-graph-explorer.md`
   Task 10 for exact commands).
3. For `graphology-layout-forceatlas2`, re-run the esbuild step (see note above).
4. Update the version cells in this README and the `version` line in each
   file's header comment.
5. Recompute sha256 for each file (`shasum -a 256 *.js`) and update this README.
6. Run the manual verification checklist at `docs/runbooks/graph-explorer-verify.md`.
7. Update `THIRD_PARTY_NOTICES.md` if any license text changed.

## License notes

All files are MIT-licensed. See `THIRD_PARTY_NOTICES.md` at the repo root for
the verbatim license texts.
