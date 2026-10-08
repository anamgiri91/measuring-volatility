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
# third-party inputs placed locally and never packaged (gitignored; pinned by SHA-256 in
# src/nepsevol/frontier.py and documented in data/external/README.md)
SKIP_PREFIXES = ("data/external/frontier/",)


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
        if str(rel).startswith(SKIP_PREFIXES):
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
    "revision": "14 (round 14: the M14 instrumented calibration and the M15 opening-price "
                "analysis, both under frozen plans, moved into the manuscript; earlier rounds "
                "answered the referee report of 2026-09-02 and the audits that followed it)",
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
        "regenerated_by": "paper/apply_referee_revisions.py, then paper/apply_round3_revisions.py "
                          "through paper/apply_round14_revisions.py, in order",
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
        "paper_facing_pipeline": "run_paper_analysis.sh completed successfully in the reference "
                                 "environment (earlier rounds)",
        "round_14_rerun": "Every producer step of run_paper_analysis.sh except 30 (which rewrites "
                          "the build manifest's provenance) was rerun in a clean copy on Python "
                          "3.13.16 / numpy 2.5.3 / x86-64 Linux on 2026-10-08. Every manuscript-"
                          "facing table (output/tables/paper_table*.csv), PAPER_RESULTS_CHECK.csv "
                          "and every M14 and M15 table (table74-97) reproduced byte-for-byte. 36 "
                          "earlier intermediate tables and the two processed samples differed "
                          "only in floating-point rounding (largest relative difference 9e-13; "
                          "one Spearman correlation by 1e-7 through the ordering of near-ties), "
                          "consistent with the newer numpy build; the committed files are the "
                          "reference-environment outputs and were not replaced.",
        "verified_on": ["Python 3.14 / macOS arm64 (reference)",
                        "Python 3.13.16 / numpy 2.5.3 / x86-64 Linux (round 14 rerun; see "
                        "round_14_rerun)"],
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
    "revision_14_changes": {
        "M14_instrumented_calibration": {
            "plan": "M14_CALIBRATION_ANALYSIS_PLAN.md (frozen before any slope was computed)",
            "results": "M14_CALIBRATION_RESULTS.md; output/tables/table74-88; manuscript Section 6.6, "
                       "Table 29, Figure 7",
            "result": "Range estimators' near-unit ratios are calibration (Parkinson slope 0.919 "
                      "[0.760, 1.056]); AddRS and the VWAP estimator are amplified; the "
                      "liquidity-gradient, closing-rule and band-slope predictions were not detected.",
        },
        "M15_opening_price": {
            "plan": "M15_OPENING_PRICE_ANALYSIS_PLAN.md (frozen before any outcome statistic was "
                    "computed; simulation checks committed next)",
            "results": "M15_OPENING_PRICE_RESULTS.md; output/tables/table89-97; manuscript Section 6.7, "
                       "Tables 30-32, Figure 8, Appendix A",
            "result": "The session undoes 64-87% of NEPSE's overnight move, an error inside each "
                      "security's auction (post hoc X6: the market-wide move shows no detectable "
                      "reversal); the 20 April 2026 rule package, which widened the pre-open band, "
                      "is a sharp break, unique against 77 placebo dates; "
                      "band-pinned opens were reversed, not continued; three-quarters of "
                      "Yang-Zhang's excess over close-to-close variance is the opening covariance. "
                      "The dose-response leg and the inversion rule were not established.",
        },
        "M16_anam_estimator": {
            "status": "package only; not part of the manuscript",
            "estimator": "src/nepsevol/estimators/anam.py",
            "plan": "M16_ANAM_ESTIMATOR_PLAN.md (frozen in commit dc41f1e, after design on NEPSE "
                    "regimes A1 and B and before any holdout observation was read)",
            "results": "M16_ANAM_ESTIMATOR_RESULTS.md; output/tables/table98-106b",
            "result": "No range-based estimator beats Anam's estimator on the NEPSE holdout, NIFTY 50 "
                      "or the S&P 500; it ranks first on NIFTY 50 and its calibrated level is within "
                      "1.2% of close-to-close variance where rules were stable. Close-to-close beats it "
                      "in the 90 sessions after NEPSE's band reform, and the plan's three NEPSE "
                      "predictions (H1-H3) failed.",
        },
        "M17_anam_frontier": {
            "status": "package only; not part of the manuscript",
            "panels": "src/nepsevol/frontier.py (Dhaka Stock Exchange 2023-2026 and 2009-2021, Vietnam "
                      "2007-2020; third-party inputs pinned by SHA-256, not packaged)",
            "plan": "M17_ANAM_FRONTIER_PLAN.md (frozen in commit db417ac, before any estimator was "
                    "computed on these data)",
            "results": "M17_ANAM_FRONTIER_RESULTS.md; output/tables/table107-111",
            "result": "Anam's estimator beats every classical range-based estimator in all three panels at "
                      "both horizons and its calibrated level is within 1% of close-to-close variance; it "
                      "does not beat close-to-close at 5 sessions in either primary panel and loses to it in "
                      "Vietnam at 21 sessions, so the summary claim G fails. Its open-free special case had "
                      "the lowest loss at 5 sessions in every panel (post hoc reading of a reported variant).",
        },
        "corrections": "AUDIT-REGISTER.md M-007 to M-016",
        "new_scripts": ["scripts/37_opening_price.py", "scripts/38_opening_price_exploratory.py",
                        "paper/apply_round14_revisions.py", "scripts/39_anam_development.py",
                        "scripts/40_anam_holdout.py", "scripts/41_anam_posthoc.py", "scripts/42_anam_frontier.py"],
        "new_modules": ["src/nepsevol/opening.py", "src/nepsevol/estimators/anam.py",
                        "src/nepsevol/volforecast.py", "src/nepsevol/frontier.py"],
        "new_tests": ["tests/test_opening_price.py", "tests/test_round14_revisions.py",
                      "tests/test_anam_estimator.py", "tests/test_anam_results.py",
                      "tests/test_frontier_panels.py", "tests/test_anam_frontier_results.py"],
        "retitled": "When the Open Overreacts: Measuring Daily Volatility in a Frontier Market "
                    "without Options -- Evidence from a Pre-Open Band Reform on the Nepal Stock "
                    "Exchange",
        "submission_set": "Cover letters now lead with Journal of Financial Markets, Journal of "
                          "Empirical Finance and Journal of Financial Econometrics, then the "
                          "referee's three recommendations.",
    },
    "manifest_note": "SHA-256 hashes cover every packaged file except this manifest itself.",
    "files": list(files()),
}

path = ROOT / "SUBMISSION_MANIFEST.json"
path.write_text(json.dumps(manifest, indent=2) + "\n")
print(f"wrote {path.name}: {len(manifest['files'])} files, "
      f"tests: {manifest['validation']['pytest']}")
