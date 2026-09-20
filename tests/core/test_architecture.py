"""sd_model_hub.core must not import any web or CLI framework (plan section 2.1)."""

import ast
from pathlib import Path

import sd_model_hub.core

FORBIDDEN = {"fastapi", "starlette", "typer", "click", "socketio", "uvicorn", "rich"}
CORE_DIR = Path(next(iter(sd_model_hub.core.__path__)))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_core_imports_no_framework():
    offenders = {}
    for path in CORE_DIR.rglob("*.py"):
        bad = _imports(path) & FORBIDDEN
        if bad:
            offenders[str(path.relative_to(CORE_DIR))] = sorted(bad)
    assert offenders == {}


def test_core_does_not_import_api_or_cli():
    for path in CORE_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "sd_model_hub.api" not in text and "sd_model_hub.cli" not in text, path
