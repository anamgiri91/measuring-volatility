#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p output/tables output/figures

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
  25_submission_tables.py
do
  echo "===== scripts/${script} ====="
  python "scripts/${script}"
done

echo "===== tests ====="
pytest -q

echo "===== refresh submission manifest ====="
# FORENSIC-AUDIT FOLLOW-UP (2026-09-03). Every step above can change a hashed artifact
# (BUILD-MANIFEST.json via script 30, every output/tables/*.csv and output/figures/* file,
# PAPER_RESULTS_CHECK.csv). A run that stops before this step leaves SUBMISSION_MANIFEST.json
# describing a package state that no longer exists on disk -- which is not a corrupt archive,
# but it does mean the manifest integrity check a recipient runs next would fail for reasons
# that have nothing to do with data integrity. This must be the LAST write of the run.
python build_manifest.py

echo "Paper-facing reproduction completed successfully."
