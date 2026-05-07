from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "opendream"
MANIFEST_PATH = PACKAGE_ROOT / "package_boundaries.json"


def load_manifest() -> dict[str, Any]:
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    manifest = cast(dict[str, Any], manifest)
    if manifest.get("schema_version") != 1:
        raise ValueError("package boundary manifest schema_version must be 1")
    return manifest


def module_names() -> set[str]:
    return {path.stem for path in PACKAGE_ROOT.glob("*.py") if path.name != "__init__.py"}


def public_package_names() -> set[str]:
    return {
        path.name
        for path in PACKAGE_ROOT.iterdir()
        if path.is_dir() and (path / "__init__.py").exists() and path.name not in {"__pycache__"}
    }


def manifest_surfaces(manifest: dict[str, Any]) -> dict[str, str]:
    owners: dict[str, str] = {}
    for surface, modules in manifest.get("surfaces", {}).items():
        for module in modules:
            if module in owners:
                raise ValueError(f"module listed in multiple surfaces: {module}")
            owners[module] = surface
    return owners


def imported_opendream_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("opendream."):
                    imports.add(alias.name.split(".")[1])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("opendream."):
                imports.add(node.module.split(".")[1])
            elif node.level == 1 and node.module:
                imports.add(node.module.split(".")[0])
    return imports


def check_manifest_coverage(owners: dict[str, str]) -> list[str]:
    problems: list[str] = []
    actual = module_names() | public_package_names()
    missing = sorted(actual - set(owners))
    extra = sorted(set(owners) - actual)
    if missing:
        problems.append("modules missing from package boundary manifest: " + ", ".join(missing))
    if extra:
        problems.append("manifest lists missing modules: " + ", ".join(extra))
    return problems


def check_public_contract_imports(manifest: dict[str, Any], owners: dict[str, str]) -> list[str]:
    problems: list[str] = []
    allowed = set(manifest.get("allowed_imports", {}).get("public_contract", ["public_contract"]))
    for module, surface in sorted(owners.items()):
        if surface != "public_contract":
            continue
        imports = imported_opendream_modules(PACKAGE_ROOT / f"{module}.py")
        for imported in sorted(imports):
            imported_surface = owners.get(imported)
            if imported_surface and imported_surface not in allowed:
                problems.append(
                    f"public_contract module {module} imports {imported} "
                    f"from forbidden surface {imported_surface}"
                )
    return problems


def check_facade_packages(manifest: dict[str, Any], owners: dict[str, str]) -> list[str]:
    problems: list[str] = []
    facades = set(manifest.get("surfaces", {}).get("public_facades", []))
    for package in sorted(facades):
        if package not in public_package_names():
            problems.append(f"public facade package missing: {package}")
        if owners.get(package) != "public_facades":
            problems.append(f"public facade package not owned by public_facades: {package}")
    return problems


def check_private_markers(manifest: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    forbidden = [
        "opendream-" + "private",
        "archived-public-agent-" + "artifacts",
        "/" + "Users/" + "reynard/src/pylit-ai/" + "opendream-" + "private",
        "customer/" + "provider-specific",
        "provider-specific " + "private",
        "internal " + "URL",
    ]
    candidates = [
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / "MANIFEST.in",
        REPO_ROOT / "README.md",
        MANIFEST_PATH,
    ]
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in forbidden:
            if marker in text and path != MANIFEST_PATH:
                problems.append(f"private marker {marker!r} found in {path.relative_to(REPO_ROOT)}")
    return problems


def main() -> int:
    try:
        manifest = load_manifest()
        owners = manifest_surfaces(manifest)
        problems = [
            *check_manifest_coverage(owners),
            *check_public_contract_imports(manifest, owners),
            *check_facade_packages(manifest, owners),
            *check_private_markers(manifest),
        ]
    except Exception as exc:
        print(f"package boundary check failed: {exc}", file=sys.stderr)
        return 1
    if problems:
        print("package boundary check failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("package boundary check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
