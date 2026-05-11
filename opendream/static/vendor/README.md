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

- `sigma.min.js`: `a3fbc2f48d30a85f32cca5e17447bc290bc7d696358b5b28432c8dde783aa635`
- `graphology.umd.min.js`: `065a8594599f61ffad22eac4b6dc23e20bd1a9b824281944434ffe74bacbbc70`
- `graphology-layout-forceatlas2.min.js`: `80cf971abed8df07d732b37bebda38c67d42286087e915ad7d33d5232fc2041f`

These are on-disk checksums, including the provenance header comments committed
with the vendored files. Upstream/source checksums are tracked in the source
rows above when available.

## Refresh procedure

1. Look up the desired version on cdnjs.com / jsdelivr.com.
2. Download the pinned files from the source URLs above into this directory.
3. For `graphology-layout-forceatlas2`, re-run the esbuild step shown above.
4. Update the version cells in this README and the `version` line in each
   file's header comment.
5. Recompute sha256 for each file (`shasum -a 256 *.js`) and update this README.
6. Run the manual verification checklist at `docs/runbooks/graph-explorer-verify.md`.
7. Update `THIRD_PARTY_NOTICES.md` if any license text changed.

## License notes

All files are MIT-licensed. See `THIRD_PARTY_NOTICES.md` at the repo root for
the verbatim license texts.
