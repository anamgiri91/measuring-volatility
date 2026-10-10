#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p output/tables output/figures

# Every analysis that runs, and every one that is skipped, is recorded in output/run_status.json, which
# build_manifest.py copies into the manifest. A run without the third-party frontier inputs is a PARTIAL
# reproduction: the analyses that need them are skipped and their committed tables are reused, not
# regenerated (audit item A10, 9 October 2026).
RAN=()
SKIPPED=()

# Order matters. 27 validates the instrument classification against the external security
# master and must run BEFORE 03, because 03 writes the analysis and equity samples and the
# classification decides which securities are in the ordinary-equity universe. 25 runs last:
# it reformats artifacts the other scripts produce and computes nothing of its own.
# 30 runs first and depends on nothing: it repairs the build manifest's provenance fields, and
# a reader who opens the package should not find a stale manifest even if the run stops early.
# 28 and 29 run after 03 (they read the equity sample) and before 25 (which reformats them).
# 34-38 are the two analyses run under frozen plans (M14, M15; see the *_ANALYSIS_PLAN.md
# files): 34 before 36 and 37 (which import its data build), 37 before 38 (which imports
# 37's), and all of them before 25, which builds manuscript Tables 29-32 from their outputs.
# 34 and 35 are the slow steps (about ten minutes each).
for script in \
  30_repair_build_manifest.py \
  27_classification_audit.py \
  03_descriptive.py \
  09_cross_market_control.py \
  12_benchmark_diagnosis.py \
  13_opening_auction.py \
  17_addrs_benchmark.py \
  19_addrs_premise.py \
  22_universe_composition.py \
  24_duplicate_key_reconciliation.py \
  26_robustness.py \
  28_panel_balance.py \
  29_calendar_validation.py \
  31_lagged_thinness_screen.py \
  32_vix_forward_validation.py \
  33_nepal_literature_matrix.py \
  34_instrumented_calibration.py \
  35_calibration_simulation.py \
  36_calibration_exploratory.py \
  37_opening_price.py \
  38_opening_price_exploratory.py \
  39_anam_development.py \
  40_anam_holdout.py \
  41_anam_posthoc.py \
  25_submission_tables.py
do
  echo "===== scripts/${script} ====="
  python "scripts/${script}"
  RAN+=("${script}")
  if [ "${script}" = "41_anam_posthoc.py" ]; then
    # M17 and M18, the post hoc recheck of M16-M18 (script 44), the theory checks (script 45, whose
    # Part C reads the frontier panels), the corrected evaluation of plan M20 (script 47, four of whose
    # seven samples are frontier panels), the checks of Proposition 7 (script 48, whose Part C reads
    # the frontier panels), the M21 parameter freeze (script 50, which never overwrites the frozen
    # table: it reports whether it reproduces it), the post hoc residue check of the frozen tables
    # (script 51), plan M22's evaluation of Anam II (script 52, whose unseen market is Pakistan) and its
    # weight freeze (script 53, which never overwrites either), and the checks of Proposition 8 (script
    # 54, whose data part reads every panel's training span) read third-party inputs that are not
    # packaged (data/external/README.md). Script 54 runs before script 46, which reads its ledger.
    # Their committed tables are shipped, so the run continues without them, as a partial reproduction.
    OPTIONAL=(42_anam_frontier.py 43_anam_morocco.py 44_anam_recheck.py 45_theory_checks.py
              47_corrected_evaluation.py 48_kernel_theory.py 50_m21_freeze.py 51_frozen_residue_check.py
              52_m22_evaluation.py 53_m22_freeze.py 54_market_open_theory.py)
    if [ -d data/external/frontier ]; then
      for optional in \
        42_anam_frontier.py \
        43_anam_morocco.py \
        44_anam_recheck.py \
        45_theory_checks.py \
        47_corrected_evaluation.py \
        48_kernel_theory.py \
        50_m21_freeze.py \
        51_frozen_residue_check.py \
        52_m22_evaluation.py \
        53_m22_freeze.py \
        54_market_open_theory.py
      do
        echo "===== scripts/${optional} ====="
        python "scripts/${optional}"
        RAN+=("${optional}")
      done
    else
      echo "===== SKIPPED (data/external/frontier/ not present): ${OPTIONAL[*]} ====="
      SKIPPED+=("${OPTIONAL[@]}")
    fi
    # the step-by-step verification of the theory's proofs reads the committed outputs of scripts 45, 48
    # and 54 and the NEPSE sample only, and the audit sensitivities read the NEPSE sample only, so both always run
    for always in \
      46_theory_proofs.py \
      49_audit_sensitivities.py
    do
      echo "===== scripts/${always} ====="
      python "scripts/${always}"
      RAN+=("${always}")
    done
  fi
done

echo "===== tests ====="
pytest -q

echo "===== record what ran ====="
python - "${#SKIPPED[@]}" "${RAN[@]}" -- ${SKIPPED[@]+"${SKIPPED[@]}"} <<'PY'
import json, subprocess, sys
from datetime import datetime, timezone
n_skipped = int(sys.argv[1])
rest = sys.argv[2:]
cut = rest.index("--")
ran, skipped = rest[:cut], [x for x in rest[cut + 1:] if x]
try:
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or None
except Exception:
    head = None
status = {"finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_head": head,
          "python": sys.version.split()[0], "status": "complete" if not skipped else "partial",
          "ran": ran, "skipped": skipped,
          "skipped_reason": "data/external/frontier/ not present" if skipped else None,
          "note": ("Skipped analyses were not regenerated: their committed tables are reused as shipped."
                   if skipped else "Every producer script ran.")}
open("output/run_status.json", "w").write(json.dumps(status, indent=2) + "\n")
print(f"output/run_status.json: {status['status']}; {len(ran)} ran, {len(skipped)} skipped")
PY

echo "===== refresh submission manifest ====="
# FORENSIC-AUDIT FOLLOW-UP (2026-09-03). Every step above can change a hashed artifact
# (BUILD-MANIFEST.json via script 30, every output/tables/*.csv and output/figures/* file,
# PAPER_RESULTS_CHECK.csv). A run that stops before this step leaves SUBMISSION_MANIFEST.json
# describing a package state that no longer exists on disk -- which is not a corrupt archive,
# but it does mean the manifest integrity check a recipient runs next would fail for reasons
# that have nothing to do with data integrity. This must be the LAST write of the run.
python build_manifest.py

if [ "${#SKIPPED[@]}" -gt 0 ]; then
  echo "PARTIAL reproduction: ${#SKIPPED[@]} analyses were skipped for want of data/external/frontier/ (${SKIPPED[*]}); their committed tables were reused, not regenerated."
else
  echo "Paper-facing reproduction completed: every producer script ran."
fi
