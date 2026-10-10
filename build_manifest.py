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
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ipynb_checkpoints", "build", "dist"}
SKIP_NAMES = {"SUBMISSION_MANIFEST.json", ".DS_Store"}
# third-party inputs placed locally and never packaged (gitignored; pinned by SHA-256 in
# src/nepsevol/frontier.py and documented in data/external/README.md)
SKIP_PREFIXES = ("data/external/frontier/",)
LATEX_BUILD = {".aux", ".bbl", ".blg", ".fdb_latexmk", ".fls", ".log", ".out", ".toc", ".gz"}


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
        if any(part.endswith(".egg-info") for part in rel.parts):   # local package builds
            continue
        if str(rel).startswith(SKIP_PREFIXES):
            continue
        if str(rel).startswith("paper/theory/") and rel.suffix in LATEX_BUILD:   # LaTeX intermediates
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


def run_status():
    """The status run_paper_analysis.sh recorded on its last complete pass, or a statement that none exists."""
    f = ROOT / "output" / "run_status.json"
    if not f.exists():
        return ("no run of run_paper_analysis.sh has written output/run_status.json; the runner records one "
                "from round 19 on (audit item A10)")
    return json.loads(f.read_text())


manifest = {
    "package": "NEPSE Volatility Journal Submission Reproducibility Package",
    "revision": "20 (round 20: Anam II, the market-implied open, designed on training spans only (ANAM2_DEVELOPMENT.md) and tested under plan M22, frozen before it was computed on any test row, with Pakistan as a market used at no stage of its design (manuscript Section 6.9 and Table 40); its weights frozen for the prospective test; Proposition 8 added to the theory supplement; three overstated statements about the open's two parts corrected (AUDIT-REGISTER M-035 to M-037); "
                "round 19: the independent audit of 9 October 2026 answered point by point "
                "(RESEARCH_AUDIT_RESPONSE.md); the forecast evaluation corrected under plan M20, frozen before it "
                "was run, with return-only forecasts, ablations and a model confidence set (manuscript Table 39); "
                "plan M21's prospective test frozen; Proposition 7 added to the theory supplement; the overstated "
                "claims corrected (AUDIT-REGISTER M-028 to M-034); "
                "round 18: every step of every proof in the theory supplement verified by "
                "scripts/46_theory_proofs.py, symbolically wherever the step is algebra or calculus, with the "
                "precision edits it asked for (AUDIT-REGISTER M-027); round 17: a theory supplement in LaTeX, paper/theory/, with six propositions and their "
                "proofs, each checked by scripts/45_theory_checks.py under plan M19, and the correction of "
                "Appendix A that it forced (AUDIT-REGISTER M-026); round 16: a post hoc recheck of every claim made for Anam's estimator, with the "
                "overstatements it found corrected (AUDIT-REGISTER M-020 to M-025) and the recheck added "
                "as Tables 37-38; round 15 moved Anam's estimator and its out-of-sample tests under plans "
                "M16-M18 into the manuscript as Section 6.8 and Tables 33-36, with a new title; round "
                "14 added the M14 instrumented calibration and the M15 opening-price analysis; "
                "earlier rounds answered the referee report of 2026-09-02 and the audits that "
                "followed it)",
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
                          "through paper/apply_round20_revisions.py, in order",
        "canonical_source": "The .docx above is the canonical editable manuscript. The revision scripts record "
                            "every edit and the checks behind it, starting from a pre-revision draft that is not "
                            "distributed (the --base of paper/apply_referee_revisions.py), so they document the revision rather than "
                            "rebuild "
                            "the file from nothing (audit item A14).",
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
        "paper_facing_pipeline": run_status(),
        "round_20_runs": "Run individually in round 20 on Python 3.13 / x86-64 Linux, with the third-party "
                         "inputs present, Pakistan's included: scripts 52 (plan M22, all eight samples), 53, 54, 46 "
                         "and 25, then paper/apply_round20_revisions.py and paper/build_submission_set.py. Script "
                         "52 asserts that M20's open-free HAR, rebuilt by M20's own code, reproduces table 127 on "
                         "every seen sample before any comparison is made, and that the three frozen files' digests "
                         "equal those in the plan. The full runner was not rerun end to end in round 20.",
        "round_19_runs": "Run individually in round 19 on Python 3.13 / x86-64 Linux, with the third-party "
                         "inputs present: scripts 46, 47 (plan M20, all seven samples), 48, 49, 50, 51 and 25, "
                         "then paper/apply_round19_revisions.py. Script 47 asserts that its step S0 reproduces "
                         "the frozen tables 101, 108 and 113, and script 51 that its frozen run does. The full "
                         "runner was not rerun end to end in round 19; 'paper_facing_pipeline' records the last "
                         "run that wrote output/run_status.json, if any.",
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
    "revision_16_changes": {
        "recheck": {
            "script": "scripts/44_anam_recheck.py (POST HOC, written after every M16-M18 verdict was known; "
                      "not pre-registered)",
            "outputs": "output/tables/table117-120; manuscript Tables 37-38 "
                       "(output/tables/paper_table37_anam_robustness.csv, "
                       "paper_table38_anam_level_same_calibration.csv)",
            "document": "ANAM_RECHECK_POSTHOC.md",
            "result": "Every committed table reproduces byte for byte, and the recheck reproduces every frozen "
                      "t before varying one choice at a time. Under QLIKE no classical range estimator beats "
                      "Anam's estimator under any inference variant. Against close-to-close the verdicts "
                      "depend on the loss function, and Morocco's full-form win does not survive longer lags, "
                      "an MSE loss or a Holm correction across the plans. Given the same calibration every "
                      "classical range estimator is within 2.2% of close-to-close variance, so the level is the "
                      "calibration's doing. The Dhaka date repair, the Moroccan band schedule and the pooling "
                      "of Vietnam's exchanges pass their checks. No frozen verdict changes.",
        },
        "corrections": "AUDIT-REGISTER.md M-020 to M-025: pre-registration stated too broadly; comparisons "
                       "stated without their qualifications; the level credited to the kernel; causal, "
                       "novelty and interpretive wording; the protocol for Nepal; the recheck itself",
        "new_scripts": ["scripts/44_anam_recheck.py", "paper/apply_round16_revisions.py"],
        "new_tests": ["tests/test_round16_revisions.py", "tests/test_anam_recheck.py"],
        "new_documents": ["ANAM_RECHECK_POSTHOC.md"],
    },
    "revision_20_changes": {
        "anam2": {
            "development": "ANAM2_DEVELOPMENT.md; scripts/dev_anam2/; output/dev_anam2/ledger.csv (195 variants, "
                           "training spans only; not evidence)",
            "plan": "M22_ANAM2_PLAN.md (frozen in commit d1d7c0f with src/nepsevol/estimators/anam2.py, "
                    "scripts/52_m22_evaluation.py and the Pakistan reader in src/nepsevol/frontier.py, before Anam II "
                    "was computed on any test row and before any return was computed on the Pakistan data)",
            "script": "scripts/52_m22_evaluation.py; scripts/53_m22_freeze.py (Part C, never overwrites)",
            "outputs": "output/tables/table138-142; manuscript Table 40 (output/tables/paper_table40_m22_anam2.csv)",
            "results": "M22_ANAM2_RESULTS.md",
            "result": "P1 supported: Anam II has lower loss than M20's open-free HAR at 5 sessions in 3 of 6 panels "
                      "(Dhaka 2023-2026, Vietnam and Pakistan, the unseen market) and higher loss in none of 12 "
                      "panel-horizons. It beats the best return-only forecast at 5 sessions in 5 of 6. Most of the "
                      "gain is the factor-HAR dynamics; with the dynamics fixed, the market-implied open helps "
                      "detectably only in Dhaka (2023-2026 at both horizons, 2009-2021 at 21 sessions). P2: 3 of 5 "
                      "predictions held. On the indices every difference lies inside the practical margin.",
            "unseen_market": "Pakistan Stock Exchange: 101 ordinary equities, 225,058 stock-days, 2016-10-13 to "
                             "2026-10-08; third-party file pinned by digest under data/external/frontier/psx/ "
                             "(not packaged; data/external/README.md)",
        },
        "theory": "Proposition 8 (paper/theory/section_theory.tex; proof B.8): the market-implied open; "
                  "scripts/54_market_open_theory.py (35 checks, table143; data on each panel's training span, "
                  "table144); scripts/46_theory_proofs.py now 385 steps, 185 symbolic",
        "corrections": "AUDIT-REGISTER.md M-035 (plan M22 and what it should be judged against), M-036 (three "
                       "overstated statements about the open's two parts), M-037 (the new reference)",
        "new_scripts": ["scripts/52_m22_evaluation.py", "scripts/53_m22_freeze.py", "scripts/54_market_open_theory.py",
                        "scripts/dev_anam2/", "paper/apply_round20_revisions.py"],
        "new_tests": ["tests/test_m22_anam2.py", "tests/test_m22_results.py", "tests/test_anam2_package.py",
                      "tests/test_round20_revisions.py", "anam-estimator/tests/test_market.py"],
        "new_documents": ["ANAM2_DEVELOPMENT.md", "M22_ANAM2_PLAN.md", "M22_ANAM2_RESULTS.md"],
    },
    "revision_19_changes": {
        "audit": "audits/2026-10-09_research_audit.md and audits/2026-10-09_publication_plan.md (as received); "
                 "RESEARCH_AUDIT_RESPONSE.md answers A01-A15: twelve accepted, three accepted in part with the "
                 "disputed part argued (A02 features, A09 parameter uncertainty, A13 importance)",
        "corrected_evaluation": {
            "plan": "M20_CORRECTED_EVALUATION_PLAN.md (frozen in commit 984dfbc before any corrected loss was computed)",
            "script": "scripts/47_corrected_evaluation.py; shared module anam_estimator.evaluation",
            "outputs": "output/tables/table125-132; manuscript Table 39 (output/tables/paper_table39_m20_corrected.csv)",
            "results": "M20_CORRECTED_EVALUATION_RESULTS.md",
            "result": "47 of 288 frozen per-rival verdicts change. A classical range estimator beats the full form "
                      "in 1 of 84 primary comparisons and the open-free form in none. After Holm, the open-free form "
                      "beats close-to-close at 5 sessions in 6 of 7 samples and the full form in 3. The best "
                      "range-based forecast beats the best return-only forecast in Dhaka 2009-2021 and Morocco only; "
                      "returns suffice in Dhaka 2023-2026 and after NEPSE's reform. HAR on the open-free kernel has "
                      "the lowest test loss in 10 of 14 cells and, with GJR-GARCH, is in every 90% model confidence set.",
        },
        "prospective_test": "M21_PROSPECTIVE_PLAN.md; parameters frozen by scripts/50_m21_freeze.py in "
                            "output/tables/table136_m21_frozen_parameters.csv (SHA-256 recorded in the plan)",
        "theory": "Proposition 7 (paper/theory/section_theory.tex; proof B.7): what Anam's kernel does with a noisy "
                  "open; scripts/48_kernel_theory.py (63 checks, table133-134); scripts/46_theory_proofs.py now "
                  "321 steps, 166 symbolic",
        "post_hoc": "scripts/49_audit_sensitivities.py (table135: weight floor, robust first stage, corporate-action "
                    "tolerance, row counts); scripts/51_frozen_residue_check.py (table137: floating-point residues "
                    "in the frozen tables)",
        "corrections": "AUDIT-REGISTER.md M-028 to M-034",
        "new_scripts": ["scripts/47_corrected_evaluation.py", "scripts/48_kernel_theory.py",
                        "scripts/49_audit_sensitivities.py", "scripts/50_m21_freeze.py",
                        "scripts/51_frozen_residue_check.py", "paper/apply_round19_revisions.py"],
        "new_tests": ["anam-estimator/tests/test_evaluation.py", "tests/test_forecast_baselines.py",
                      "tests/test_round19_revisions.py"],
        "new_documents": ["RESEARCH_AUDIT_RESPONSE.md", "ESTIMAND_NOTE.md", "M20_CORRECTED_EVALUATION_PLAN.md",
                          "M20_CORRECTED_EVALUATION_RESULTS.md", "M21_PROSPECTIVE_PLAN.md", "audits/"],
    },
    "revision_18_changes": {
        "proof_steps": {
            "script": "scripts/46_theory_proofs.py",
            "outputs": "output/tables/table124_theory_proof_steps.csv; paper/theory/generated/proofs.tex and tab_proofs.tex "
                       "(the supplement's Table 5 then, Table 6 since Proposition 7 was added in round 19)",
            "result": "251 steps, all passing: every part of every proposition and every step of every proof in the "
                      "theory supplement, and the paper's own mathematical claims (the Yang-Zhang identity, the "
                      "non-negativity of Garman-Klass, the special cases of Anam's kernel, the old and corrected "
                      "Appendix A, the M14 and M15 algebra). 138 steps are verified symbolically with SymPy; the others "
                      "numerically, by simulation, pathwise or on every NEPSE stock-day they apply to.",
        },
        "corrections": "AUDIT-REGISTER.md M-027: precision edits to the supplement's statements and to Appendix A's "
                       "attainment condition; no result changes",
        "new_scripts": ["scripts/46_theory_proofs.py", "paper/apply_round18_revisions.py"],
        "new_tests": ["tests/test_theory_proofs.py"],
    },
    "revision_17_changes": {
        "theory": {
            "document": "paper/theory/theory.tex (section_theory.tex, appendix_proofs.tex, references.bib) and its "
                        "compiled theory.pdf; every number is a macro from paper/theory/generated/numbers.tex",
            "plan": "M19_THEORY_CHECKS_PLAN.md (frozen in its own commit before scripts/45_theory_checks.py existed)",
            "script": "scripts/45_theory_checks.py (POST HOC relative to M14-M18; Part C's prediction fixed in M19)",
            "outputs": "output/tables/table121_theory_checks.csv (every check of Propositions 1-6 against simulation "
                       "or numerical integration), table122_theory_applications.csv (the sharp bound, the error's "
                       "scale, the censoring factor and decomposition, the calibration lag), "
                       "table123_theory_pooling.csv (plan M19's pooling test)",
            "result": "Every check of the six propositions passes. Applications: the sharp bound on the opening "
                      "error is more than twice the published one; about a third of the fall in b at the band "
                      "reform is the end of censoring and almost two thirds the overshoot of large opens; the lag "
                      "path describes the applied calibration after the reform almost exactly but explains only "
                      "a small part of the forecast-loss gap between calibration windows. Plan M19's one test was "
                      "not supported: the open-free form's lower loss always included a level component, but the "
                      "shape component also favoured it in most cases, and the cross-sectional prediction was "
                      "confirmed in four of ten cases and reversed in one.",
        },
        "corrections": "AUDIT-REGISTER.md M-026: Appendix A's bound on the opening error is valid but not sharp, "
                       "and its stated attainment was wrong; the sharp bound replaces the claim",
        "new_scripts": ["scripts/45_theory_checks.py", "paper/apply_round17_revisions.py"],
        "new_tests": ["tests/test_theory_checks.py"],
        "new_documents": ["M19_THEORY_CHECKS_PLAN.md", "M19_THEORY_CHECKS_RESULTS.md", "paper/theory/"],
    },
    "anam_estimator_package": {
        "path": "anam-estimator/ (pyproject.toml, src/anam_estimator, tests, examples, README.md with a model card)",
        "install": "pip install \"anam-estimator @ git+https://github.com/anamgiri91/measuring-volatility.git"
                   "#subdirectory=anam-estimator\"",
        "contents": "anam_estimator() (the estimate on every bar), AnamModel (fit, forecast, backtest, score, "
                    "save/load), a command line, simulate_bars(); depends on numpy and pandas only",
        "tested": "its estimator's arithmetic is a verbatim copy of src/nepsevol/estimators/anam.py, and "
                  "tests/test_anam_package.py checks that it equals the research module on every NEPSE stock-day "
                  "and both indices; since version 0.2.0 its forecasting model uses the corrected evaluation of "
                  "plan M20 (anam_estimator.evaluation), and the same test checks it origin by origin against the "
                  "research code's single-model corrected evaluation; anam-estimator/tests holds the package's "
                  "own tests",
        "anam2": "since version 0.3.0, AnamIIModel (anam_estimator.market; needs the [market] extra, scipy) is "
                 "the second generation for a panel; tests/test_anam2_package.py checks that its kernel, "
                 "calibration, components, weights and losses equal the research module's (plan M22) on NEPSE "
                 "and the NIFTY 50",
    },
    "revision_14_changes": {
        "M14_instrumented_calibration": {
            "plan": "M14_CALIBRATION_ANALYSIS_PLAN.md (frozen before any slope was computed)",
            "results": "M14_CALIBRATION_RESULTS.md; output/tables/table74-88; manuscript Section 6.6, "
                       "Table 29, Figure 7",
            "result": "A unit calibration slope is not rejected for the range estimators (Parkinson 0.919 "
                      "[0.760, 1.056]), under instruments whose validity is assumed (two-way clustered "
                      "effective F 19.4 for the primary instruments, 29.9 for those dated two sessions back; "
                      "post hoc, AUDIT-REGISTER M-030); AddRS and the VWAP estimator are amplified; the "
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
            "status": "manuscript Section 6.8 and Tables 33-36 (round 15)",
            "estimator": "src/nepsevol/estimators/anam.py",
            "plan": "M16_ANAM_ESTIMATOR_PLAN.md (frozen in commit dc41f1e, after design on NEPSE "
                    "regimes A1 and B, with M15's full-sample findings known, and before the estimator "
                    "was computed on the holdout)",
            "results": "M16_ANAM_ESTIMATOR_RESULTS.md; output/tables/table98-106b",
            "result": "No range-based estimator has significantly lower loss than Anam's estimator on "
                      "the NEPSE holdout, NIFTY 50 or the S&P 500 (where it coincides with overnight^2 + "
                      "Parkinson); it ranks first on NIFTY 50 and its calibrated level is within 1.1% of "
                      "close-to-close variance where rules were stable, as any estimator's is under the "
                      "same calibration (post hoc recheck, M-022). Close-to-close beats it "
                      "in the 90 sessions after NEPSE's band reform, and the plan's three NEPSE "
                      "predictions (H1-H3) failed.",
        },
        "M17_anam_frontier": {
            "status": "manuscript Section 6.8 and Tables 33-36 (round 15)",
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
        "M18_anam_morocco": {
            "status": "manuscript Section 6.8 and Tables 33-36 (round 15)",
            "panel": "src/nepsevol/frontier.py (Casablanca Stock Exchange 2012-2026, data supplied by the author, "
                     "pinned by SHA-256, not packaged; daily limits by AMMC regime)",
            "plan": "M18_ANAM_MOROCCO_PLAN.md (frozen in commit b4de86d, before any estimator was computed on "
                    "these data; the open-free form tested as a hypothesis fixed in advance)",
            "results": "M18_ANAM_MOROCCO_RESULTS.md; output/tables/table112-116",
            "result": "Every binding hypothesis holds: the open-free form has the lowest loss at both horizons and "
                      "beats close-to-close and the full estimator at 5 sessions; the full estimator beats "
                      "close-to-close and Parkinson at 5 sessions; both calibrated levels are 1.005.",
        },
        "corrections": "AUDIT-REGISTER.md M-007 to M-019 (round 16 adds M-020 to M-025)",
        "new_scripts": ["scripts/37_opening_price.py", "scripts/38_opening_price_exploratory.py",
                        "paper/apply_round14_revisions.py", "scripts/39_anam_development.py",
                        "scripts/40_anam_holdout.py", "scripts/41_anam_posthoc.py", "scripts/42_anam_frontier.py",
                        "scripts/43_anam_morocco.py",
                        "paper/apply_round15_revisions.py"],
        "new_modules": ["src/nepsevol/opening.py", "src/nepsevol/estimators/anam.py",
                        "src/nepsevol/volforecast.py", "src/nepsevol/frontier.py"],
        "new_tests": ["tests/test_opening_price.py", "tests/test_round14_revisions.py",
                      "tests/test_anam_estimator.py", "tests/test_anam_results.py",
                      "tests/test_frontier_panels.py", "tests/test_anam_frontier_results.py",
                      "tests/test_anam_morocco_results.py",
                      "tests/test_round15_revisions.py"],
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
