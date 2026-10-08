# M18 — results: Anam's estimator and its open-free form in Morocco

This file reports what `scripts/43_anam_morocco.py` found when it executed the plan frozen in
`M18_ANAM_MOROCCO_PLAN.md`. That plan was committed and pushed in `b4de86d`, together with the
Casablanca reader and the dated band schedule, before the script existed or any estimator was
computed on these data.

Conventions:

* Numbers are read from the tables named in brackets.
* QLIKE is the forecast loss; lower is better.
* "t" is the Newey–West statistic of the named estimator's loss minus the rival's; a negative t
  favours the named estimator.

## The verdicts, applied mechanically (`table116_anam_morocco_decisions.csv`)

| Rule | Estimator | Verdict | Evidence |
|---|---|---|---|
| F1 | Anam | **holds** | 5 sessions: Anam 0.6706 beats close-to-close 0.6784 (t = −2.06) |
| F2 | Anam | **holds** | 5 sessions: Anam beats Parkinson 0.7352 (t = −11.01) |
| F3 | Anam | **holds** | calibrated level 1.005; overnight² + Parkinson 1.283; Yang–Zhang daily form 1.273 |
| best in panel | Anam | **yes** | no rival beats Anam at 5 or 21 sessions |
| V1 | open-free form | **holds** | 5 sessions: 0.6633 beats close-to-close 0.6784 (t = −4.53) |
| V2 | open-free form | **holds** | 5 sessions: beats the full estimator 0.6706 (t = −4.75) |
| V3 | open-free form | **holds** | no estimator beats it at 5 or 21 sessions; it has the lowest loss of all nine at both |
| O | open-free form | **holds** | V1 and V3 both hold |

**Predictions.** One of the plan's predictions failed, in the estimator's favour: F1 was predicted
not to hold, and the frozen estimator beat close-to-close at 5 sessions. Every other prediction held.

## What the Morocco test establishes

1. **The open-free form passed its first test on data nobody had examined.** On the test span
   (2019-04-01 to 2026-03-27, 78,923 stock-days, `table113`) it has the lowest loss of all nine
   estimators at both horizons:

   | Horizon | Open-free form | Full estimator | Close-to-close | Open-free vs close-to-close | Open-free vs full |
   |---|---|---|---|---|---|
   | 5 sessions | 0.6633 | 0.6706 | 0.6784 | t = −4.53 | t = −4.75 |
   | 21 sessions | 0.3272 | 0.3314 | 0.3363 | t = −1.94 | t = −2.38 |

   At 21 sessions the gap to close-to-close falls just short of the plan's threshold. The hypothesis
   was singled out after M17, but it was fixed in the frozen plan before these data were read.
2. **The frozen estimator also beat close-to-close at 5 sessions.** This is the first primary
   frontier-market panel where it did (M16's NEPSE holdout and M17's two primary panels showed no
   difference). It beats every range-based rival at 5 sessions, and none beats it at 21.
3. **The level is right, and the classical estimators are off in both directions** (`table114`).
   * **Both calibrated forms:** 1.005 times close-to-close variance on the test span, and 1.009–1.034
     in each band regime.
   * **The range-only estimators understate by 46–55%:** Parkinson 0.544, Garman–Klass 0.453,
     Rogers–Satchell 0.495. In this thin market 29% of the records have the high equal to the low,
     so the range misses much of the variance.
   * **The estimators that add the overnight return overstate by 19–28%:** overnight² + Parkinson
     1.283, the Yang–Zhang daily form 1.273, overnight² + Garman–Klass 1.191.
4. **Casablanca's open overreacts less than Nepal's or Dhaka's.** The median b̂ on the test span is
   0.642, and 0.71, 0.69, 0.63 and 0.64 in the four band regimes (`table112`). Against M17's
   0.328–0.538 and NEPSE's 0.13–0.36, the session keeps more of the overnight move here. Both forms
   still win.

## What it does not establish

* **Neither form beats close-to-close significantly at 21 sessions:** t = −1.94 for the open-free
  form and −1.00 for the full estimator, although both have lower loss.
* **Band regimes (reported only, no decision; `table113`).** The four regimes are short, and they
  do not all point the same way:
  * **4% regime (2020-03-17 to 2021-10-11).** The estimators that read the open had the lowest
    losses (overnight² + Garman–Klass at 5 sessions, the Yang–Zhang daily form at 21). The full
    estimator beat the open-free form at 21 sessions (t = +2.09 for the open-free form's excess
    loss). With prices held within 4%, the overnight move carries more of the day's information.
  * **6% regime (2021-10-12 to 2023-10-08).** Close-to-close had the lowest loss at 21 sessions. It
    beat the full estimator there (t = +2.99), but not the open-free form (t = +0.96).
  * **The two 10% regimes.** The open-free form was first at 5 sessions in both.
* **Instrumented noise (T4, reported; `table115`).** Every estimator's efficiency lower bound is
  below close-to-close's: open-free form 0.471, full estimator 0.237, Parkinson 0.156. The
  instrumented slopes of the range estimators are near 0.1. By this lens, the high and low of
  Casablanca's thin shares carry little information about close-to-close variance, while the
  forecast test ranks both forms first. The two lenses disagree here, as they have in every market
  so far.
* **The data.** The author supplied the files without a stated source, and they are not adjusted for
  corporate actions. Dividend ex-dates within the band stay in the panel and affect every estimator
  that reads the previous close.

## Where the open-free form now stands

In all four panels of M17 and M18, the open-free form had the lowest loss of all nine estimators at
5 sessions, and it beat close-to-close at 5 sessions in each:

* M17 (reported variant): Dhaka 2023–2026, Dhaka 2009–2021 and Vietnam 2007–2020;
* M18 (frozen hypothesis): Morocco 2012–2026.

Two further records bear on it:

* **NEPSE (M16, reported variant).** Its loss was below the full estimator's in every comparison.
  But close-to-close was ahead of it on the holdout, and significantly so in regime C, the 90
  sessions after the April 2026 band reform (t = +3.38 at 5 sessions and +2.40 at 21; `table101`).
* **NIFTY 50 and the S&P 500.** Where the open is nearly efficient, the full estimator was better,
  though not significantly.

M18 is the first test in which the form's advantage was a decision rule fixed before the data were
seen, and it passed. **The record supports the open-free form as the frontier-market version of
Anam's estimator, with the full form kept for markets whose open is efficient.** One caveat stands:
right after a sudden change in market rules, close-to-close has beaten it (NEPSE regime C), as it
beat the full estimator in Morocco's 6% regime at 21 sessions. One more frozen test on later data
would put the claim on two confirmations rather than one: NEPSE after 26 August 2026, or Dhaka after
8 October 2026.

## Corrections

| ID | Detail | Effect |
|---|---|---|
| `M-018` | The plan abbreviates the archive's SHA-256 as `c9cc8888…0e02e0ef1be`; it ends `…4e02e0ef1be`. | None: the full digest is correct in the module and the data README, and the code checks the 77 share files by their manifest digest, which the plan quotes correctly. |
