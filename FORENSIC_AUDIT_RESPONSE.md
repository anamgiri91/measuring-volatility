# Response to the forensic packaging/provenance audit

This document answers the third-round audit, which found the underlying empirical work sound but
identified release-engineering defects: a stale top-level PDF, a reproduction workflow that could
invalidate its own submission manifest, an undocumented historical-vs-current hash distinction,
and two overstated claims in prose. Six items were listed as non-negotiable before submission;
four are fixed and verified below, one is disclosed as blocked in this environment, and one
requires a decision only the package owner can make.

## Fixed and verified

### 1. The reproduction workflow can invalidate its own manifest — FIXED

Confirmed the defect exactly as reported: running `run_paper_analysis.sh` on a manifest-clean
tree left **8 files mismatched** against `SUBMISSION_MANIFEST.json` (`BUILD-MANIFEST.json` plus
seven regenerated figure PDFs), because the workflow never re-ran `build_manifest.py` afterward.

**Fix:** `run_paper_analysis.sh` now runs `python build_manifest.py` as its last step, always.
Verified by running the full pipeline **twice in succession** — 0 manifest mismatches after each
run (`SUBMISSION_MANIFEST.json` is regenerated fresh every time, so it always describes the tree
it was just written next to).

### 2. `scripts/30_repair_build_manifest.py` rewrote a timestamp on every run — FIXED

`provenance_repair.repaired_utc` previously updated even when nothing tracked (code identifier,
git commit, raw-data status) had actually changed, which is exactly the kind of content churn
that makes a "reproduction" run un-reproduce its own frozen hash. The script now compares the new
state to the old one before writing and is a genuine no-op — `BUILD-MANIFEST.json` byte-identical,
`repaired_utc` untouched — when nothing changed. Verified: second consecutive run prints
`(no-op: already up to date, repaired_utc left untouched)`.

### 3. `cleaning_code_sha256` vs. `code_identifier` — undocumented distinction, now documented

Confirmed: the shipped `cleaning_code_sha256` (`30d26f26...`) does not match a fresh hash of the
current `src/nepsevol/clean/*.py` (`6a4f0c3f...` in the audit; independently recomputed here as a
different but likewise-non-matching value, confirming the underlying claim — the two are not
equal). This is not a data-integrity defect: `cleaning_code_sha256` is *supposed* to be a
snapshot of the code that actually built the frozen panel, and the panel cannot be rebuilt in this
environment (raw downloads not redistributed) even after the cleaning code was later edited for
unrelated bug fixes across two review rounds. But nothing said so.

**Fix:** both `src/nepsevol/provenance.py::write_manifest` (for a future genuine rebuild) and
`scripts/30_repair_build_manifest.py` (patching the current, frozen manifest) now write a sibling
`cleaning_code_sha256_note` field stating this explicitly — using close to the audit's own
suggested wording. Verified present in the shipped `data/processed/BUILD-MANIFEST.json`.

### 4. Two overstated claims in prose — FIXED

- `src/nepsevol/estimators/range_.py` and `AUDIT-REGISTER.md` claimed a non-negativity property
  test would make "a transcription error... surface as a proof that fails." Correct as stated for
  *some* errors (e.g. a sign flip), not all — a wrong coefficient can easily preserve
  non-negativity while still being wrong. Both now say these are *necessary-condition sanity
  checks*, not sufficient verification of coefficients, and not a substitute for reading the
  primary text.
- The "79 tests" / "seventy-nine" figures in `REFEREE_RESPONSE.md` (a historical document, dated
  to the 2 September response) predate this round's 29 additional tests (108 now). Rather than
  rewrite history, an editorial note was added at the top pointing to the current count in
  `SUBMISSION_MANIFEST.json`, and the one place it appeared as a literal reproduction instruction
  (a `bash` comment) was reworded to not hardcode a number that will go stale again.

**Verification for all four:** `pytest -q` → 108 passed (no regressions); the full pipeline run
twice in a row → 0 manifest mismatches both times.

## Disclosed as blocked in this environment

### 5. Regenerate the final-manuscript PDF — cannot be done here

I confirmed the finding: `NEPSE_Volatility_Final_Manuscript.pdf` (inside `paper/`) still carried
the pre-revision title and 291/143,149 sample counts, while the current `.docx` carries the new
title and 292/143,718. This is now clearly disclosed rather than silently accurate-by-luck:

- The file is **renamed** to `paper/manuscript_as_reviewed_pre_revision.pdf`, so its name no
  longer claims to be current.
- `README.md` and `build_manifest.py`'s `manuscript.as_reviewed_note` field now say explicitly,
  in the manifest a recipient would actually check, that this PDF is pre-revision and that **no
  PDF of the current manuscript exists in this package**.
- What I could not do: actually render a new PDF from the revised `.docx`. This environment has
  no Word, LibreOffice, `unoconv`, or `pandoc` available (checked and confirmed absent). A
  from-scratch PDF built by another route (e.g. reflowing the text through a different renderer)
  would not be the camera-ready document a journal expects and could introduce its own
  formatting defects, so I did not attempt one.

**This needs you**, outside this session: open `paper/NEPSE_Volatility_Manuscript_Revised_2026-09.docx`
in Word (or LibreOffice) and export it to PDF, replacing whatever file the package points reviewers
to as the current manuscript.

## Needs a decision — not attempted

### 6. Clean submission archive (remove the old package + stray review PDFs)

The audit is correct that the outer folder still contains `NEPSE_Volatility_Submission_Package/`
(the pre-`_rev3` package), and that `Peer Review Evaluation.pdf` / `Verdict.pdf` sit at the top
level alongside it — internal review material that shouldn't travel with a journal submission, and
a second, superseded "authoritative-looking" package that could be opened by mistake.

I have not deleted or moved anything here. These live outside the `_rev3` package I've been
editing, in your top-level `Downloads/final version/` folder, and removing them is a destructive
action on files I did not create — that's a call for you to make, not one I should make silently.
Let me know if you'd like me to remove the old package folder and the two review PDFs (or archive
them elsewhere instead of deleting).
