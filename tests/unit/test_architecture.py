"""Enforces the layering rules from the blueprint (section 10.4) without extra tooling.

Rules checked now (more are added as packages appear):
 - schemas imports nothing else inside meridian.
 - core imports nothing else inside meridian.
 - verification and evidence are pure logic: they may import only schemas, core and each other.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "meridian"

ALLOWED: dict[str, set[str]] = {
    "schemas": {"schemas"},
    "core": {"core"},
    "verification": {"verification", "schemas", "core"},
    "evidence": {"evidence", "schemas", "core"},
}


def _imported_meridian_packages(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("meridian."):
            found.add(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("meridian."):
                    found.add(alias.name.split(".")[1])
    return found


@pytest.mark.parametrize("package", sorted(ALLOWED))
def test_package_respects_layering(package: str) -> None:
    violations: list[str] = []
    for py_file in (SRC / package).rglob("*.py"):
        imported = _imported_meridian_packages(py_file)
        bad = imported - ALLOWED[package]
        if bad:
            violations.append(f"{py_file.relative_to(SRC)} imports {sorted(bad)}")
    assert not violations, "\n".join(violations)


def test_verification_never_imports_llm_layer() -> None:
    for py_file in (SRC / "verification").rglob("*.py"):
        assert "meridian.models" not in py_file.read_text(encoding="utf-8")
