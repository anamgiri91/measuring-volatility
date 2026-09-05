"""Repair data/processed/BUILD-MANIFEST.json so it claims exactly what it can support.

MANDATORY ITEM 7 / PEER-REVIEW ITEM F. The shipped manifest said:

    "raw_data": {"n_files": 0, "aggregate_sha256": null}
    "git_commit": "UNKNOWN"

while Section 9 and the README both told the reader that the manifest records an aggregate
raw-data hash and an immutable code identifier. It records neither. That is the most damaging
class of reproducibility defect in the package, because it is not a gap -- a gap is honest --
but a DOCUMENTED CLAIM CONTRADICTED BY THE ARTIFACT it points at. A reviewer who opens the file
to check one claim and finds it false has no reason to trust the others.

Two things were wrong, and they need opposite fixes:

  RAW DATA -- the claim was too strong and is WITHDRAWN. The raw NEPSE downloads are
  deliberately not redistributed here, so no aggregate raw hash can exist on a reviewer's
  machine. ``nepsevol.provenance.raw_data_status`` now emits a named status,
  ``NOT_REDISTRIBUTED``, and a ``claim`` field saying in words that the manifest asserts nothing
  about raw provenance. A bare ``0``/``null`` read as a hash that was attempted and failed; the
  named status cannot be misread that way. README and Section 9 are corrected to match.

  CODE IDENTITY -- the claim was right and the ARTIFACT was missing, so the artifact is
  supplied. ``git_commit`` is the wrong identifier for a distributed archive: the package is not
  a checkout, so the field can only ever say ``UNKNOWN``.
  ``nepsevol.provenance.code_identifier`` hashes the shipped source itself, which any holder of
  the package can recompute with no repository and no network. That is what "immutable code
  identifier" has to mean for an artifact that travels.

WHY THIS SCRIPT AND NOT A REBUILD. The ``artifacts`` block records the SHAPES of the panels the
original build produced, including two (``panel_long``, ``panel_trades``) that are intermediate
and are not redistributed. Regenerating the manifest from the shipped files alone would silently
drop them and rewrite ``generated_utc`` to today, which would misdate a build that happened
earlier. This script therefore PRESERVES the original build record verbatim and repairs only
the provenance fields, recording that it did so and when. Every field that describes the
original build still describes the original build.

    python scripts/30_repair_build_manifest.py
"""
import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from _env import bootstrap
bootstrap()

sys.path.insert(0, str(ROOT / "src"))
from nepsevol.provenance import code_identifier, raw_data_status, git_commit

PATH = ROOT / "data" / "processed" / "BUILD-MANIFEST.json"

m = json.loads(PATH.read_text())

_before_raw = dict(m.get("raw_data", {}))
_before_commit = m.get("git_commit")

# FORENSIC-AUDIT FOLLOW-UP (2026-09-03). This script previously rewrote
# provenance_repair.repaired_utc on every run, even when nothing substantive changed --
# which meant running the paper-facing pipeline twice in a row left BUILD-MANIFEST.json
# byte-different from itself, and therefore mismatched against SUBMISSION_MANIFEST.json's
# frozen hash for it. A repair timestamp is only informative if it means "something was
# repaired"; a timestamp that updates on every no-op run means nothing. The new state is
# now compared against the old one BEFORE writing, and the file (and its repaired_utc) is
# touched only when a tracked field actually changed.
new_code_identifier = code_identifier(ROOT)
new_commit = git_commit(ROOT)
new_raw = raw_data_status(ROOT)
new_note = ("Historical snapshot: the state of src/nepsevol/clean/*.py at the time the "
           "processed panel referenced by 'artifacts' below was actually built. Source "
           "files below may have been edited since (bug fixes, added checks, documentation) "
           "without the panel being rebuilt, so this hash is not expected to match a fresh "
           "hash of the CURRENT clean/*.py -- that comparison is what 'code_identifier' "
           "above is for, and it IS recomputed on every run. A rebuild that regenerates "
           "'cleaning_code_sha256' itself requires the raw NEPSE downloads, which this "
           "package does not redistribute (see 'raw_data').")

tracked_before = {
    "code_identifier": m.get("code_identifier"),
    "git_commit": m.get("git_commit"),
    "raw_data": m.get("raw_data"),
    "cleaning_code_sha256_note": m.get("cleaning_code_sha256_note"),
}
tracked_after = {
    "code_identifier": new_code_identifier,
    "git_commit": new_commit,
    "raw_data": new_raw,
    "cleaning_code_sha256_note": new_note,
}

if tracked_before == tracked_after and "provenance_repair" in m:
    print("Repaired data/processed/BUILD-MANIFEST.json  (no-op: already up to date, "
          "repaired_utc left untouched)")
    print(f"  code_identifier  sha256={m['code_identifier']['sha256']}")
    raise SystemExit(0)

m["code_identifier"] = new_code_identifier
m["git_commit"] = new_commit
m["git_commit_note"] = ("Not a git checkout; use code_identifier.sha256, which any holder of "
                        "this package can recompute." if new_commit == "UNKNOWN"
                        else "Working-tree commit at build time.")
m["raw_data"] = new_raw
m["cleaning_code_sha256_note"] = new_note
m["provenance_repair"] = {
    "repaired_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "reason": "Mandatory item 7 of the peer-review evaluation: the manifest asserted a "
              "raw-data hash it did not carry, and offered no code identifier a package "
              "holder could use.",
    "fields_repaired": ["raw_data", "git_commit", "code_identifier",
                        "cleaning_code_sha256_note"],
    "fields_preserved": ["generated_utc", "python", "packages", "cleaning_code_sha256",
                         "rule_versions", "artifacts"],
    "note": "The build record itself is unchanged. 'generated_utc' still names the original "
            "build, and 'artifacts' still records the panels that build produced, including "
            "intermediates not redistributed here.",
}

# Key order matters for a file people read by eye: identity first, then the build it describes.
_order = ["generated_utc", "code_identifier", "git_commit", "git_commit_note", "python",
          "packages", "raw_data", "cleaning_code_sha256", "cleaning_code_sha256_note",
          "rule_versions", "artifacts", "provenance_repair"]
m = {k: m[k] for k in _order if k in m} | {k: v for k, v in m.items() if k not in _order}

PATH.write_text(json.dumps(m, indent=2) + "\n")

print("Repaired data/processed/BUILD-MANIFEST.json")
print("=" * 90)
print(f"  raw_data   {_before_raw.get('n_files')!r}/{_before_raw.get('aggregate_sha256')!r}"
      f"  ->  status={m['raw_data']['status']}")
print(f"             {m['raw_data']['claim']}")
print(f"  git_commit {_before_commit!r}  ->  {m['git_commit']!r}  ({m['git_commit_note']})")
print(f"  code_identifier  sha256={m['code_identifier']['sha256']}")
print(f"                   over {m['code_identifier']['n_files']} source files")
print("\n  recompute it with:")
print(f"    {m['code_identifier']['recompute']}")
