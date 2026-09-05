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

__all__ = ["write_manifest", "file_sha256", "git_commit", "code_identifier", "raw_data_status"]

#: Source subtrees whose content defines the CODE IDENTIFIER. Everything that can change a
#: number must be in here; nothing that cannot should be, or the identifier churns for free.
CODE_ROOTS = ("src/nepsevol", "scripts")

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


def code_identifier(root: pathlib.Path) -> dict:
    """An IMMUTABLE identifier for the code that produced a build.

    MANDATORY ITEM 7. ``git_commit`` reads ``UNKNOWN`` in the shipped manifest, because the
    distributed package is not a git checkout -- and a reviewer holding the zip has no way to
    recover which code produced the frozen tables. A commit hash is the right identifier for a
    working repository and no identifier at all for an archive.

    This is a content hash over the shipped source itself: order-independent over
    :data:`CODE_ROOTS`, so it is reproducible by anyone holding the package, with no repository,
    no network and no trust in the author required. Recomputing it and comparing against the
    manifest is a complete check that the code in hand is the code that ran.

    The git commit is still recorded when one is available, because it is strictly more
    informative in a working tree. The two are reported side by side and neither is presented
    as the other.
    """
    root = pathlib.Path(root)
    files = []
    for rel in CODE_ROOTS:
        d = root / rel
        if d.exists():
            files += [p for p in sorted(d.rglob("*.py")) if "__pycache__" not in p.parts]
    return {
        "algorithm": "sha256 over sha256 of each .py file in " + ", ".join(CODE_ROOTS)
                     + ", sorted, excluding __pycache__",
        "n_files": len(files),
        "sha256": _dir_sha256(files) if files else None,
        "recompute": "python -c \"import pathlib,sys; "
                     "sys.path.insert(0,'src'); "
                     "from nepsevol.provenance import code_identifier; "
                     "print(code_identifier('.')['sha256'])\"",
    }


def raw_data_status(root: pathlib.Path) -> dict:
    """State of the raw-data vault, distinguishing ABSENT from EMPTY from HASHED.

    MANDATORY ITEM 7 / PEER-REVIEW ITEM F. The shipped manifest carried

        "raw_data": {"n_files": 0, "aggregate_sha256": null}

    which flatly contradicted Section 9 and the README, both of which claimed the manifest
    records an aggregate raw-data hash. It did not, and could not: the raw NEPSE downloads are
    deliberately not redistributed in this package, so on a reviewer's machine there is nothing
    to hash. The old shape was ambiguous in the worst direction -- a bare zero and a null read
    as "the hash was attempted and failed", rather than "the inputs are not present here by
    design".

    The status is therefore named rather than implied, and ``claim`` states in words what the
    manifest does and does not assert, so that no document can claim more than the artifact
    supports.
    """
    vault = pathlib.Path(root) / "data" / "raw"
    raw_files = sorted(vault.rglob("*.csv")) if vault.exists() else []
    if raw_files:
        return {
            "status": "PRESENT_AND_HASHED",
            "n_files": len(raw_files),
            "aggregate_sha256": _dir_sha256(raw_files),
            "claim": "The raw source files were present at build time and are hashed here.",
        }
    return {
        "status": "NOT_REDISTRIBUTED",
        "n_files": 0,
        "aggregate_sha256": None,
        "claim": "The raw NEPSE downloads are not redistributed in this package (their "
                 "redistribution terms are unresolved), so no aggregate raw-data hash is "
                 "asserted. This manifest makes NO claim about raw-data provenance. The "
                 "paper-facing pipeline starts from the frozen processed panel in "
                 "data/processed/, whose own hashes are recorded in SUBMISSION_MANIFEST.json.",
    }


def write_manifest(root: pathlib.Path, out_dir: pathlib.Path,
                   artifacts: dict[str, pd.DataFrame]) -> pathlib.Path:
    """Write ``BUILD-MANIFEST.json`` describing this build."""
    root = pathlib.Path(root)
    clean_src = sorted((root / "src" / "nepsevol" / "clean").glob("*.py"))
    _commit = git_commit(root)

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_identifier": code_identifier(root),
        "git_commit": _commit,
        "git_commit_note": ("Not a git checkout; use code_identifier.sha256, which any holder "
                            "of this package can recompute."
                            if _commit == "UNKNOWN" else
                            "Working-tree commit at build time."),
        "python": sys.version.split()[0],
        "packages": {m: __import__(m).__version__ for m in ("numpy", "pandas")},
        "raw_data": raw_data_status(root),
        "cleaning_code_sha256": _dir_sha256(clean_src) if clean_src else None,
        "cleaning_code_sha256_note": (
            "Historical snapshot: the state of src/nepsevol/clean/*.py at the time THIS build "
            "ran. If src/nepsevol/clean/*.py is edited after this manifest is written without "
            "rerunning the build, this hash will no longer match a fresh hash of the current "
            "source -- that is expected, and 'code_identifier' above (recomputed on every "
            "package run, not only on a rebuild) is what tracks current source instead."),
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
    _code = manifest["code_identifier"]["sha256"]
    print(f"  manifest                     {path.name} "
          f"(code {_code[:12] if _code else 'n/a'}, "
          f"raw data {manifest['raw_data']['status']})")
    return path
