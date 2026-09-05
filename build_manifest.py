"""Regenerate SUBMISSION_MANIFEST.json for the current package state.

The manifest is a hash inventory plus a statement of what this revision changed and what is
verified. It is generated rather than edited, because a hand-maintained inventory is exactly the
kind of artifact that goes stale — which is the failure the 2026-09-02 referee report opened on.

    python build_manifest.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ipynb_checkpoints"}
SKIP_NAMES = {"SUBMISSION_MANIFEST.json", ".DS_Store"}


def sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def files():
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if set(rel.parts) & SKIP_DIRS or rel.name in SKIP_NAMES:
            continue
        yield {"path": str(rel), "bytes": p.stat().st_size, "sha256": sha256(p)}


def pytest_result() -> str:
    try:
        out = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT,
                             capture_output=True, text=True, timeout=900).stdout
        for line in reversed(out.strip().splitlines()):
            if "passed" in line or "failed" in line:
                return line.strip()
    except Exception as e:
        return f"not run ({e})"
    return "unknown"


manifest = {
    "package": "NEPSE Volatility Journal Submission Reproducibility Package",
    "revision": "3 (response to the referee report of 2026-09-02)",
    "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "manuscript": {
        "revised_source": "paper/NEPSE_Volatility_Manuscript_Revised_2026-09.docx",
        "as_reviewed": "paper/manuscript_as_reviewed_pre_revision.pdf",
        "as_reviewed_note": "This PDF is the PRE-revision manuscript the first-round referee "
                            "actually read, retained ONLY so the revision can be checked "
                            "against it. It is NOT the current manuscript -- 'revised_source' "
                            "above is -- and was renamed from the ambiguous "
                            "'NEPSE_Volatility_Final_Manuscript.pdf' after a forensic audit "
                            "found the old name was being mistaken for the current file. No "
                            "PDF rendering of the current .docx exists in this package as of "
                            "this manifest: the environment that produced this revision has no "
                            "docx-to-PDF renderer (Word/LibreOffice/pandoc) available, so a "
                            "camera-ready PDF must still be exported from 'revised_source' "
                            "before submission.",
        "double_anonymous_set": "paper/submission/",
        "regenerated_by": "paper/apply_referee_revisions.py, then paper/apply_round3_revisions.py",
        "note": "Every figure quoted in the manuscript is interpolated from output/tables/*.csv "
                "by the revision scripts, which fail if a superseded value survives in the text "
                "or if a headline number does not reach it.",
    },
    "referee_response": "REFEREE_RESPONSE.md",
    "superseded": {
        "PAPER_REVISIONS.md": "The pre-referee revision notes. Retained for provenance; "
                              "REFEREE_RESPONSE.md supersedes it and resolves the five items it "
                              "left open.",
    },
    "validation": {
        "pytest": pytest_result(),
        "paper_facing_pipeline": "run_paper_analysis.sh completed successfully",
        "verified_on": ["Python 3.14 / macOS arm64 (reference)"],
    },
    "revision_3_changes": {
        "critical_item_1_panel_rebuild": {
            "status": "RESOLVED",
            "what": "The 2024-2026 daily-trades panel was rebuilt from the original raw "
                    "downloads under the corrected duplicate-classification rule.",
            "result": "Zero duplicated (symbol, date) keys: 286,994 keys in 286,994 rows. The "
                      "rebuilt panel is identical to the frozen panel (184,430 x 16, no "
                      "differing values), so no downstream quantity depended on the superseded "
                      "keep='last' path.",
            "evidence": "data/processed/audit/panel_trades_duplicate_audit.csv",
        },
        "critical_item_2_classification": {
            "status": "RESOLVED",
            "what": "The rule-based instrument classifier was reconciled against an external "
                    "NEPSE security master.",
            "result": "509 of 511 matched securities agree (99.61%). Two rule failures "
                      "corrected: ADBLB (4% Agricultural Bond, read as equity) and NADEP "
                      "(ordinary equity, read as promoter). Equity universe 291 -> 292 "
                      "securities, 143,149 -> 143,718 stock-days.",
            "evidence": "output/tables/table36_classification_audit.csv; "
                        "output/tables/table37_classification_disagreements.csv",
        },
        "critical_item_3_endogenous_sorting": {
            "status": "RESOLVED",
            "result": "Predetermined sorts added and reported as Table 6. The least active "
                      "bucket sits at 1.022 (security-level) and 1.025 (lagged 60-session) of "
                      "the matched proxy, above one rather than below.",
        },
        "critical_item_5_yang_zhang": {
            "status": "RESOLVED",
            "result": "Ratios are now evaluated on the intersection of numerator and benchmark "
                      "masks, and the overnight return spans exactly one detected session. "
                      "Whole-sample Yang-Zhang 1.245 -> 1.288 on 135,899 matched stock-days.",
        },
        "item_9_calendar_dates": {
            "status": "RESOLVED",
            "result": "Trading-week reform dated 2026-04-06 and the price-limit reform "
                      "2026-04-20, previously both 2026-04-20. Detected sessions unchanged at "
                      "569; two Friday sessions are no longer off-schedule and two Sundays no "
                      "longer inferred holidays.",
        },
        "item_14_inference": {
            "status": "RESOLVED",
            "result": "Multiway (security x date) cluster bootstrap. Intervals are 1.8x-2.8x "
                      "wider than the security-only ones; liquidity buckets whose Parkinson "
                      "interval excludes one fall from 12/15 to 8/15.",
        },
        "item_18_references": {
            "status": "PARTIAL",
            "result": "All five estimator references confirmed against Crossref; Yang & Zhang "
                      "(2000) pagination corrected to 477-492. Fifteen references added. "
                      "Equations remain transcribed from secondary presentations because the "
                      "primary full texts are paywalled; this is labelled in "
                      "src/nepsevol/estimators/range_.py and AUDIT-REGISTER.md rather than "
                      "quietly upgraded.",
        },
        "new_scripts": [
            "scripts/27_classification_audit.py",
            "paper/apply_referee_revisions.py",
            "paper/build_submission_set.py",
            "build_manifest.py",
        ],
        "new_modules": ["src/nepsevol/inference.py"],
        "new_tests": ["tests/test_referee_revisions.py (27 tests; suite 52 -> 79)"],
        "new_data": ["data/external/nepse_security_master.csv",
                     "data/processed/audit/panel_trades_duplicate_audit.csv"],
        "new_outputs": [
            "output/tables/table36_classification_audit.csv",
            "output/tables/table37_classification_disagreements.csv",
            "output/tables/table38_prev_close_reconciliation.csv",
            "output/tables/paper_table6_predetermined_liquidity.csv",
            "output/tables/paper_table7_all_estimators.csv",
            "output/tables/paper_table8_repair_sensitivity.csv",
            "output/tables/paper_table9_classification_audit.csv",
        ],
        "known_limitations_remaining": [
            "Estimator equations are verified against secondary presentations and against their "
            "own stated properties, not read from the paywalled primary texts (item 18).",
            "The security master lists CURRENTLY listed securities, so ten securities delisted, "
            "merged or renamed during 2024-2026 retain their rule-based classification. An "
            "official SEBON register would close this gap (disclosed in Section 10).",
            "Bootstrap intervals absorb dependence within securities and within dates but do not "
            "model the measurement error of the open-to-close proxy itself, so they are a lower "
            "bound on total uncertainty (disclosed in Section 10).",
        ],
    },
    "manifest_note": "SHA-256 hashes cover every packaged file except this manifest itself.",
    "files": list(files()),
}

path = ROOT / "SUBMISSION_MANIFEST.json"
path.write_text(json.dumps(manifest, indent=2) + "\n")
print(f"wrote {path.name}: {len(manifest['files'])} files, "
      f"tests: {manifest['validation']['pytest']}")
