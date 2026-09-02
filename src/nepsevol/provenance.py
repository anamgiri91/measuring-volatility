"""Versioned build manifests.

An artifact that cannot say which code and which raw data produced it is not evidence.
This project already lost one confirmatory result to exactly that gap: the recorded HO-2
numbers were computed on a panel build that was silently replaced hours later, and
reconstructing them required checking out an old commit and rebuilding from the vault.

Every rebuild therefore writes a manifest recording the git commit, the raw-data hash,
hashes of the cleaning code, the rule versions in force, and the shape of each artifact.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

import pandas as pd

__all__ = ["write_manifest", "file_sha256", "git_commit"]

# Bump when the corresponding rule changes; a manifest is only comparable within a version.
RULE_VERSIONS = {
    "ohlc_repair": "PAP-v4 §3.1 envelope repair, v1 (2026-08-28)",
    "duplicate_resolution": "classify; collapse EXACT_DUPLICATE, exclude all conflicting classes, v1 (2026-08-28)",
    "instrument_classification": "ticker convention validated against par value, v1 (2026-08-27)",
    "calendar": "staleness-detected sessions + documented special-session allowlist, v1 (2026-08-28)",
}


def file_sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _dir_sha256(paths) -> str:
    """Order-independent hash over a set of files."""
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(file_sha256(p).encode())
    return h.hexdigest()


def git_commit(root: pathlib.Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                               capture_output=True, text=True, timeout=10)
        sha = out.stdout.strip() or "UNKNOWN"
        return sha + ("-dirty" if dirty.stdout.strip() else "")
    except Exception:
        return "UNKNOWN"


def write_manifest(root: pathlib.Path, out_dir: pathlib.Path,
                   artifacts: dict[str, pd.DataFrame]) -> pathlib.Path:
    """Write ``BUILD-MANIFEST.json`` describing this build."""
    root = pathlib.Path(root)
    vault = root.parent / "private" / "data-vault" / "raw"
    raw_files = list(vault.rglob("*.csv")) if vault.exists() else []
    clean_src = sorted((root / "src" / "nepsevol" / "clean").glob("*.py"))

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": git_commit(root),
        "python": sys.version.split()[0],
        "packages": {m: __import__(m).__version__ for m in ("numpy", "pandas")},
        "raw_data": {"n_files": len(raw_files), "aggregate_sha256": _dir_sha256(raw_files) if raw_files else None},
        "cleaning_code_sha256": _dir_sha256(clean_src) if clean_src else None,
        "rule_versions": RULE_VERSIONS,
        "artifacts": {},
    }
    for name, df in artifacts.items():
        entry = {"rows": int(len(df))}
        if "symbol" in df.columns:
            entry["securities"] = int(df["symbol"].nunique())
        if "date" in df.columns:
            entry["date_min"] = str(df["date"].min().date())
            entry["date_max"] = str(df["date"].max().date())
            entry["sessions"] = int(df["date"].nunique())
        if "ohlc_repaired" in df.columns:
            entry["rows_repaired"] = int(df["ohlc_repaired"].sum())
        manifest["artifacts"][name] = entry

    path = pathlib.Path(out_dir) / "BUILD-MANIFEST.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"  manifest                     {path.name} "
          f"(commit {manifest['git_commit'][:12]})")
    return path
