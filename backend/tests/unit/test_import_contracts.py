"""Spec 3.3 dependency rules, enforced by import-linter."""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]


def test_import_contracts_hold() -> None:
    exe = Path(sys.executable).with_name(
        "lint-imports.exe" if sys.platform == "win32" else "lint-imports"
    )
    result = subprocess.run([str(exe)], cwd=BACKEND, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
