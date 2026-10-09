# M21 — frozen plan: the prospective test

**Frozen** on 9 October 2026, in the same commit as its parameter table, before any session dated after the
freeze has been obtained or read. Its parameters are in `output/tables/table136_m21_frozen_parameters.csv`
(SHA-256 `b73efe7fa43f8551f9e689e289786bb90c9aa3623329e9bef075387b054508c4`), written by
`scripts/50_m21_freeze.py`.

**Recommendation to the author.** Lodge this file and that digest with an external registry (OSF Registries or
AsPredicted) before any new data is read. A git commit is timestamped only by a history that its author controls
(`M-017`, `M-020`). An external registration is the only timestamp a referee can check.

## Why a prospective test

Every forecast comparison so far was made on data that existed when the estimator was designed:

* M16–M18 (frozen plans, with the defects the 9 October 2026 audit found);
* M20 (the corrected evaluation).

Section 6.7's whole-sample NEPSE findings informed the design (`M-020`). M20 itself was frozen after the audit
had reported some of its effects. Only sessions that did not exist when the parameters were fixed are free of
that history.

M20's evidence, which this plan turns into predictions:

* the open-free form beats close-to-close at 5 sessions after Holm's adjustment in six of seven samples, NEPSE
  excepted;
* the best range-based forecast beats the best return-only forecast in Dhaka 2009–2021 and Morocco, loses in
  Dhaka 2023–2026, and is indistinguishable elsewhere;
* the open-free form is never beaten by the full form in a frontier panel and beats it in four of five at 5
  sessions;
* the HAR forecast on the open-free kernel is in every 90% model confidence set.

## What is frozen

1. **The seventeen forecasts of M20**, exactly as defined in `M20_CORRECTED_EVALUATION_PLAN.md` and implemented
   in:
   * `scripts/47_corrected_evaluation.py` (the classes `Kernel`, `HAR`, `Recursion` and the combination);
   * `nepsevol.forecast_baselines`;
   * `nepsevol.estimators.anam`;
   * `anam_estimator.evaluation`.
2. **Their parameters**: φ, the HAR weights, EWMA's λ, and GARCH's and GJR-GARCH's (α, β, γ). Each was chosen
   by M20's rule, the mean canonical QLIKE, on every origin of the current data whose outcome is observed (table
   136: 14 sample-horizon cells × 17 forecasts). They are never refitted.
3. **The rolling quantities keep updating causally** as sessions arrive:
   * the open's coefficient b;
   * the calibration κ;
   * the long-run levels;
   * the recent means;
   * the HAR components;
   * the GARCH and EWMA recursions.

   They are part of each forecast rule, not parameters. A forecast made at the close of session t uses bars
   through t only.
4. **The evaluation design of M20, unchanged:**
   * the calendar target over h consecutive exchange sessions;
   * canonical QLIKE, with zero targets scored;
   * the eligibility rule (κ > 0, long-run level > 0, recent mean defined);
   * the exact-zero rule for squared quantities (`ZERO_SQUARE` = 1e-18);
   * the stock-day mean with its date-linearised standard error and a Bartlett bandwidth of 2h;
   * the model confidence set of Hansen, Lunde and Nason (T_max, stationary bootstrap of dates, mean block
     max(2h, 10), 1,999 resamples). Its seed is 20271010 + 100 × (market index) + h, with the market index 0
     for NEPSE, 1 for Dhaka, 2 for Casablanca, 3 for Vietnam, 4 for the NIFTY 50 and 5 for the S&P 500.

## Data

| Market | Continues | New sessions | Source, to be pinned by SHA-256 on acquisition |
|---|---|---|---|
| NEPSE | the ordinary-equity panel (`data/processed/equity_sample.csv`) | after 2026-08-26 | the same stock-level downloads, through `scripts/02_build_panel.py` and the same classification, cleaning and calendar detection |
| Dhaka | the 2023–2026 panel | after 2026-10-08 | the same public mirror (`nifty1303/dse-data`), at a later commit |
| Casablanca | the 2012–2026 panel | after 2026-03-27 | the source of the author's `archive_2.zip`, which the author must document first |
| Vietnam | the 2007–2020 panel | after 2020-03-18 | only if a documented source with the same adjustment exists; otherwise Vietnam is not part of M21 |
| NIFTY 50 | `data/external/nifty50.csv` | after its last row | a documented public source |
| S&P 500 | the `arch` package series | after its last row (2018) | a documented public source |

**Rules for the new data:**

* **Pinned before use.** Every new file is pinned by SHA-256 in a manifest committed before any forecast is
  computed on it.
* **Checked against the old data.** A new download must reproduce the existing data on the sessions they
  share. A disagreement is reported, and the existing data are kept for those sessions.
* **Securities listed after the freeze** enter when their rolling quantities are defined, as in M20.
* **Corporate actions** are handled as in each panel's existing build. Casablanca's prices remain unadjusted
  for dividends, as its panel's are.

## Windows

* **Primary window: sessions dated after 9 October 2026.** These did not exist at the freeze. Every hypothesis
  below is decided on this window.
* **Unseen-past window:** sessions between a panel's last bar and 9 October 2026 (about six weeks for NEPSE, six
  months for Casablanca, and the S&P 500 from 2019). They existed at the freeze but have not been read by this
  project. They are reported separately and decide nothing.
* **One evaluation.** It happens at the first month end at which every primary market (NEPSE, Dhaka and
  Casablanca) has at least 250 sessions in the primary window, or on 31 December 2027, whichever comes first.
  * A market with fewer than 120 primary-window sessions at that date is reported descriptively, without
    verdicts.
  * There is no interim look at any loss. A data-integrity check (counts, digests, the calendar) is allowed.
* **Training never happens again.** The first test origin is the first primary-window session at which a
  forecast is defined. The target must lie inside the window.

## Hypotheses

The forecasts are named as in M20:

* **CC:** close-to-close;
* **full:** Anam's estimator;
* **open-free:** its b = 0 form;
* **HAR-open-free;**
* **r\*** and **g\*:** the best return-only and range-based forecasts by the training loss in table 136:

  | Market | h = 5 | h = 21 |
  |---|---|---|
  | NEPSE | r\* = GJR; g\* = HAR-open-free | r\* = GJR; g\* = HAR-open-free |
  | Dhaka | r\* = GJR; g\* = HAR-open-free | r\* = GJR; g\* = HAR-open-free |
  | Casablanca | r\* = GJR; g\* = HAR-open-free | r\* = GARCH; g\* = HAR-open-free |
  | Vietnam | r\* = GARCH; g\* = HAR-open-free | r\* = GARCH; g\* = HAR-open-free |
  | NIFTY 50 | r\* = GJR; g\* = HAR-open-free | r\* = GJR; g\* = HAR-open-free |
  | S&P 500 | r\* = GJR; g\* = overnight² + Garman–Klass | r\* = GJR; g\* = HAR-open-free |

A "beats" verdict needs a one-sided p = Φ(t) below 0.025 after Holm's adjustment within the family, unless a
hypothesis says otherwise.

**Primary (decided at 5 sessions):**

* **P1. The open-free form beats close-to-close in Dhaka and in Casablanca** (Holm over the two). M20: after
  Holm in both panels (adjusted p 0.013 each). No prediction for NEPSE, where M20 found no difference
  (t = +0.63). NEPSE is reported.
* **P2. In Casablanca, g\* beats r\*.** This is the range adding information beyond returns. M20: "range adds
  information" at both horizons, but fragile to the weighting (Part E). One-sided, alone in its family,
  p < 0.025.
* **P3. In Dhaka, g\* does not beat r\*.** M20 found "returns suffice" at both horizons in the 2023–2026 panel.
  This prediction fails if g\* beats r\* at the two-sided 5% level. It is confirmed in the strong sense only if
  r\* beats g\*, and the results will say which.
* **P4. The open-free form beats the full form in Dhaka and in Casablanca** (Holm over the two). M20: t = −11.03
  and −4.45.

**Secondary (reported with the same tests, not decided):**

* **S1.** P1–P4 at 21 sessions.
* **S2.** P1 and P4 in NEPSE, two-sided.
* **S3.** HAR-open-free is in the 90% model confidence set of the seventeen in every market and horizon (M20:
  14 of 14).
* **S4.** The count of classical range estimators that beat each form (M20: 1 of 84 for the full form, 0 for
  the open-free form).
* **S5.** In NEPSE, g\* against r\*, two-sided (M20: no significant difference).
* **S6.** The same comparisons in the unseen-past window, and on the indices and Vietnam if their data exist.
* **S7.** Part E of M20 for every primary verdict: bandwidths, equal-date and equal-security means,
  non-overlapping origins.

## What the results can and cannot say

* **If P1, P2 and P4 hold**, the corrected claims hold out of time in the two frontier markets with the most
  evidence. The paper may then say that a calibrated open-free range measure forecasts better than plain
  close-to-close, and adds information beyond returns in Casablanca, on data that did not exist when it was
  fixed.
* **If P2 fails**, the claim that the range adds information beyond strong return-only forecasts rests on Dhaka
  2009–2021 alone, a historical panel with repaired dates.
* **No outcome identifies latent variance or the band's effect.** These are forecasts of observed returns'
  second moment (`ESTIMAND_NOTE.md`).

## Outputs (when the data arrive)

* **`scripts/52_m21_prospective.py`**, written when the data arrive. It reads table 136 and asserts that the
  digest above matches. It must not call a selection routine.
* **Tables 138 onward.**
* **`M21_PROSPECTIVE_RESULTS.md`**, with every deviation from this plan disclosed.
