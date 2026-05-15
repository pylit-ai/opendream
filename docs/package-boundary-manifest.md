# OpenDream Package Boundary Manifest

OpenDream ships from the public repository. The runtime, build, install, and release path must be reproducible from the public tree.

The machine-readable manifest is `opendream/package_boundaries.json`. It records:

- the one-install CLI entrypoint
- current public package surfaces
- release inclusion inventory
- non-public local markers that must not enter public artifacts

Public facade packages:

- `opendream.spec`: schema inventory, contract export, and validation entrypoint.
- `opendream.runtime`: default local runtime and deterministic dream entrypoint.
- `opendream.backends`: optional backend descriptors loaded by interface, not by public callers.
- `opendream.adapters`: bundled and workspace adapter manifest helpers.
- `opendream.evals`: public eval and benchmark entrypoints.
- `opendream.ui`: local UI data contract.

`scripts/check_package_boundaries.py` enforces manifest coverage and the first hard boundary: contract modules cannot import runtime, provider, CLI, service, or non-public modules. `scripts/check_public_artifacts.py` rejects stale backup/generated artifacts such as `.orig`, `.bak`, and `.DS_Store`.

Reorg status:

- `ODR-ARCH-01`: manifest and release inclusion inventory added.
- `ODR-ARCH-03`: mechanical import-boundary check added for the public contract surface.
- `ODR-ARCH-04`: spec facade added for schema, contract export, and validation.
- `ODR-ARCH-05`: runtime facade added for default local dream/runtime APIs.
- `ODR-ARCH-06`: backend descriptors added behind an optional interface surface.
- `ODR-ARCH-07`: adapter facade added for bundled and workspace adapters.
- `ODR-ARCH-08`: eval facade added for public eval entrypoints.
- `ODR-ARCH-10`: local UI contract facade added.
- `ODR-ARCH-13`: verify and release gates now run the package-boundary checker.
