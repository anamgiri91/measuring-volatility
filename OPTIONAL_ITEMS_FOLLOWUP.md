# Follow-up on the optional items

Five items sat in earlier rounds' "optional" or "useful but not non-negotiable" lists and had not
been actioned. This note records what was done about each.

## Item H (literature integration) — confirmed already complete

The previous status was "partial" based on a spot check. A full surname-by-surname audit —
every reference in the list checked against the manuscript body, using narrative-citation-safe
matching (e.g. "Lo and MacKinlay (1990)", not only the reference-list form "Lo, A. W., &
MacKinlay") — found that **all 30 references already have at least one in-text citation**. No
further splicing was needed; `REFEREE_RESPONSE_ROUND3.md`'s item H section is updated to reflect
this.

## Abstract length — fixed

The abstract was 698 words in a single paragraph. It is now a **245-word structured abstract**
(Purpose / Design-methodology-approach / Findings / Originality-value), the format Emerald
journals — including the Asian Journal of Economics and Banking, the recommended first
submission target — require, under the 250-word cap.

## Master-coverage sensitivity — built

`scripts/27_classification_audit.py` now recomputes the headline ordinary-equity statistics
(securities, stock-days, zero-range rate, Parkinson SD ratio to the matched proxy) with and
without the ten securities absent from the external security master:

| Specification | Securities | Stock-days | Zero-range | Parkinson ratio |
|---|---|---|---|---|
| Including all ten | 292 | 143,718 | 0.278% | 1.0005 |
| Excluding all ten | 282 | 142,391 | 0.279% | 1.0008 |

The ratio moves by **0.0003**. This is manuscript Table 17, cross-referenced from §3's
classification paragraph, converting "unreconciled" into demonstrably non-influential.

## JEL codes, data availability, funding, conflict of interest — added

- **JEL Classification:** C58, G12, G14, G15, O16 — added after the Keywords line.
- **Declarations** section (new, before References): a data-availability statement consistent
  with what the package actually ships (processed data + code included; raw downloads not
  redistributed, rebuild independently verified to reproduce the frozen panel exactly), a funding
  statement, and a conflict-of-interest statement.
- **The funding and conflict-of-interest text uses the standard default** ("no specific grant...",
  "declares no conflict of interest") because I was not given the actual facts to disclose.
  **Verify these are accurate before submission** — if there was funding or a conflict, this text
  is wrong and must be corrected in `paper/apply_round4_revisions.py` (search for `"Funding"` and
  `"Conflict of interest"`) before the next rebuild, or edited directly in the `.docx`.

## Table pagination and decimal precision — both addressed, differently than first proposed

- **Repeated column headers on page breaks**, the concrete part of the pagination complaint, turns
  out not to need a PDF renderer: `w:tblHeader` is a `.docx` property that Word, LibreOffice and
  any PDF export built from either respects automatically. It is now set on **all 17 tables**.
- **Splitting Tables 6/7 to an appendix** was not done. Restructuring the manuscript into a
  numbered appendix is a bigger, riskier edit than the readability problem strictly requires, and
  the header-repeat fix above addresses the specific readability complaint the first review
  raised ("their current page breaks lack repeated column headers"). If you still want the
  full tables moved to an appendix with abbreviated versions left in the body, say so and I will
  do it as its own pass.
- **The decimal-precision issue** ("Table 6 displays one interval as [0.907, 1.000] while the
  code counts it as excluding one because the unrounded upper bound is 0.99953") is fixed
  generally, not just for that one cell: every displayed confidence-interval bound now falls back
  to 4 decimals whenever 3 would round it to a whole number it is not actually equal to
  (`scripts/25_submission_tables.py::_fmt_ci_bound`). This also caught and fixed a second instance
  of the same defect the forensic audit separately flagged in Table 15 (Rogers-Satchell's
  block-date lower bound, 0.99997, was displaying as "1.000" next to a coded "excludes one =
  False" — now displays as "1.0000").

## Verification

`pytest -q` → 108 passed (no new tests were needed; these are prose/formatting/table-content
changes covered by the existing map and stale-text checks). Full pipeline run twice in a row →
`SUBMISSION_MANIFEST.json` self-consistent (0/147 mismatches) both times. Anonymized submission
set rebuilt and re-verified free of the author's name.
