"""Shared bootstrap for every pipeline script.

Puts src/ on the path and fails with an actionable message rather than a raw
ImportError when the environment is not set up. A replication package is run by
people who did not build it; "ModuleNotFoundError: numpy" tells them nothing.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIRED = ["numpy", "pandas", "scipy", "matplotlib"]


def _script_path() -> str:
    """Path of the running script relative to the project root, for a copy-pasteable hint."""
    try:
        return str(pathlib.Path(sys.argv[0]).resolve().relative_to(ROOT))
    except (ValueError, OSError):
        return pathlib.Path(sys.argv[0]).name


def bootstrap(extra: list[str] | None = None) -> pathlib.Path:
    sys.path.insert(0, str(ROOT / "src"))

    missing = [m for m in REQUIRED + (extra or []) if importlib.util.find_spec(m) is None]
    if not missing:
        return ROOT

    venv = ROOT / ".venv" / "bin" / "python"
    running_venv = pathlib.Path(sys.prefix) != pathlib.Path(sys.base_prefix)

    lines = [
        "",
        "  Environment not ready.",
        f"  Missing package(s): {', '.join(missing)}",
        f"  Running under:      {sys.executable}",
        "",
    ]
    if venv.exists() and not running_venv:
        lines += [
            "  A project virtualenv exists but is not the interpreter in use.",
            "  Run the pipeline with it:",
            "",
            f"      {venv.relative_to(ROOT)} {_script_path()}",
            "",
            "  or activate it first:",
            "",
            "      source .venv/bin/activate",
            "",
        ]
    else:
        lines += [
            "  Create the environment first:",
            "",
            "      python3 -m venv .venv",
            "      source .venv/bin/activate",
            "      pip install -r requirements.txt",
            "",
        ]
    print("\n".join(lines), file=sys.stderr)
    raise SystemExit(1)
