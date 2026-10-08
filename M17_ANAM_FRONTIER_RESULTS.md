# M17 — results: Anam's estimator in Bangladesh and Vietnam

This file reports what `scripts/42_anam_frontier.py` found when it executed the plan frozen in
`M17_ANAM_FRONTIER_PLAN.md`. That plan was committed and pushed in `db417ac`, together with the
panel module and its tests, before the script existed or any estimator was computed on these data.
This file applies the plan's decision rules exactly as written and records separately anything read
after the verdicts were seen.

Conventions:

* Numbers are read from the tables named in brackets.
* QLIKE is the forecast loss; lower is better.
* "t" is the Newey–West statistic of Anam's loss minus the rival's; a negative t favours Anam.
* The estimator is M16's, unchanged.

## The verdicts, applied mechanically (`table111_anam_frontier_decisions.csv`)

| Rule | Panel | Verdict | Evidence |
|---|---|---|---|
| F1 | DSE 2023-2026 | **does not hold** | 5 sessions: Anam 0.6316 vs close-to-close 0.6341 (t = −0.90, no difference) |
| F2 | DSE 2023-2026 | **holds** | 5 sessions: Anam beats Parkinson 0.6520 (t = −5.56) |
| F3 | DSE 2023-2026 | **holds** | calibrated level 1.002; overnight² + Parkinson 1.662; Yang–Zhang daily form 1.709 |
| best in panel | DSE 2023-2026 | **yes** | no rival beats Anam at 5 or 21 sessions |
| F1 | Vietnam 2007-2020 | **does not hold** | 5 sessions: Anam 0.7705 vs close-to-close 0.7699 (t = +0.20, no difference) |
| F2 | Vietnam 2007-2020 | **holds** | 5 sessions: Anam beats Parkinson 0.8225 (t = −22.42) |
| F3 | Vietnam 2007-2020 | **holds** | calibrated level 1.009; overnight² + Parkinson 1.556; Yang–Zhang daily form 1.594 |
| best in panel | Vietnam 2007-2020 | **no** | close-to-close beats Anam at 21 sessions (0.2737 vs 0.2850, t = +7.27) |
| F1 | DSE 2009-2021 | **holds** | 5 sessions: Anam 0.6044 beats close-to-close 0.6214 (t = −6.17) |
| F2 | DSE 2009-2021 | **holds** | 5 sessions: Anam beats Parkinson 0.6162 (t = −9.55) |
| F3 | DSE 2009-2021 | **holds** | calibrated level 1.004; overnight² + Parkinson 1.392; Yang–Zhang daily form 1.418 |
| best in panel | DSE 2009-2021 | **yes** | no rival beats Anam at 5 or 21 sessions |
| G | DSE 2023-2026 + Vietnam 2007-2020 | **does not hold** | F1 fails in both primary panels, and close-to-close beats Anam in Vietnam at 21 sessions |

Three of the plan's predictions failed:

* **F1 in both primary panels.** The prediction was that Anam would beat close-to-close at 5
  sessions.
* **G.** It fails on F1 alone, and on a second count as well: close-to-close beats Anam in Vietnam
  at 21 sessions, so "best in panel" fails there.

Everything predicted about the classical estimators held. So did the level test, everywhere.
DSE 2009-2021, the secondary panel whose dates were repaired, met every prediction, but it does not
enter G.

## What the frontier test establishes

1. **No range-based estimator beats Anam in either market.** The rivals are Parkinson,
   Garman–Klass, Rogers–Satchell, overnight² + Parkinson, overnight² + Garman–Klass and the
   Yang–Zhang daily form. Anam beats every one of them in all three panels at both horizons:
   36 comparisons out of 36, every |t| above 3.3 (`table111`). Together with M16, no range-based
   estimator has beaten it in any market tried: NEPSE, Bangladesh, Vietnam, NIFTY 50 and the
   S&P 500.
2. **The level is right in all three panels, and the classical estimators are off in both
   directions.**
   * **Anam:** its calibrated 21-session variance is 1.002, 1.009 and 1.004 times close-to-close
     variance on the three test spans (`table109`).
   * **Overstated by 39–71%:** overnight² + Parkinson (1.392–1.662) and the Yang–Zhang daily form
     (1.418–1.709).
   * **Understated by 27–37% in Vietnam:** Parkinson (0.721), Garman–Klass (0.633) and
     Rogers–Satchell (0.728).

   No fixed classical formula is right in both markets. Calibration fixes the level wherever it
   is tried.
3. **The open is mostly transient in these markets too.** The pooled open-quality coefficient b̂ is
   the share of the overnight move that the session keeps. Its median over the test span is
   (`table107`):
   * 0.328 in Dhaka 2023–2026;
   * 0.477 in Dhaka 2009–2021;
   * 0.538 in Vietnam.

   These are security-level coefficients, and they are not comparable with the index-level b of
   NIFTY 50 or the S&P 500 (see `M-014`: an index averages its constituents' opening errors).
   Against NEPSE's security-level 0.13–0.36 (M15), the overreacting open M15 found in Nepal is
   present in both new markets, if somewhat weaker.

## What the frontier test does not establish

* **Anam is not a better short-horizon forecaster than plain close-to-close in either primary
  market.**
  * **At 5 sessions:** Anam's loss is lower in Dhaka 2023–2026 (t = −0.90) and higher in Vietnam
    (t = +0.20); neither difference is significant.
  * **At 21 sessions:** Anam beats close-to-close in Dhaka 2023–2026 (0.2669 against 0.2749,
    t = −2.22) but loses to it in Vietnam (0.2850 against 0.2737, t = +7.27).

  This repeats M16's NEPSE result, where close-to-close was not beaten either, and contrasts with
  the two indices, where Anam beat it.
* **Only the repaired Dhaka history shows a clear win over close-to-close.** In Dhaka 2009–2021
  Anam beats close-to-close at both horizons: 0.6044 against 0.6214 at 5 sessions (t = −6.17) and
  0.3524 against 0.3631 at 21 (t = −3.02). Its dates were repaired and the
  plan kept it out of G, so this does not rescue F1.
* **Instrumented noise (T4, reported only; `table110`).** The efficiency lower bound against
  close-to-close ranks Anam:
  * above every rival in Vietnam (1.760, against 1.643 for overnight² + Garman–Klass and 1.221
    for Parkinson), second only to its own open-free variant (1.805);
  * behind Parkinson in Dhaka 2023–2026 (4.739 against 5.126);
  * behind Garman–Klass and Parkinson in Dhaka 2009–2021 (2.377 against 2.805 and 2.485).

  By this lens Parkinson is the less noisy measure in both Dhaka panels, while the forecast test
  ranks Anam well ahead of it. The two lenses disagree there, as they did on NEPSE in M16, where
  Anam's bound (2.895) was below Parkinson's (3.142). The instrumented slopes are also far from one
  in Dhaka 2023–2026 (Parkinson 1.606, Anam 1.690).

## Not in the plan: the open-free special case (post hoc reading of frozen tables)

The plan listed Anam's open-free special case (b = 0) as a reported variant, with no decision
attached. Its numbers are in the frozen tables. The comparison below was drawn only after the
verdicts were seen.

* **It beats the full estimator in all three panels.** It has the lowest loss of all nine
  estimators at 5 sessions in every panel. Its loss is below the full estimator's in every panel at
  both horizons:

  | Panel | 5 sessions | 21 sessions |
  |---|---|---|
  | DSE 2023-2026 | 0.6273 against 0.6316, t = −11.35 | 0.2667 against 0.2669, t = −0.18 |
  | Vietnam 2007-2020 | 0.7629 against 0.7705, t = −15.73 | 0.2770 against 0.2850, t = −10.03 |
  | DSE 2009-2021 | 0.6008 against 0.6044, t = −9.07 | 0.3508 against 0.3524, t = −2.82 |

* **It beats close-to-close where the full estimator does not.** At 5 sessions it beats
  close-to-close in all three panels (t = −2.55, −3.58 and −8.30). At 21 sessions it beats
  close-to-close in both Dhaka panels (t = −2.30 and −3.91), and close-to-close's lower loss in
  Vietnam (0.2737 against 0.2770) is not significant (t = +1.60).
* **The same ordering appears in every NEPSE comparison of M16 and reverses on the two indices.**
  The variant's loss was below the full estimator's in all four development comparisons
  (`table98`) and all six holdout comparisons (`table101`). The holdout differences are significant
  at 5 sessions on A2 ∪ C (t = −2.47) and at both horizons in regime C (t = −3.32 and −2.73). It was
  above the full estimator's on NIFTY 50 and the S&P 500 at both horizons, none significantly,
  where the open is nearly efficient.

One reading is consistent with the estimator's own logic: where b̂ is low, the b̂-weighted
overnight term still costs more than it adds, and the open-free form drops it and keeps the previous
close as the effective open. But the pattern was found after the verdicts, on data that have now
been seen. Two things follow:

* **Before it could replace the frozen estimator in frontier markets,** the open-free form would
  need a new frozen test on data not yet examined, for example:
  * NEPSE after 26 August 2026;
  * Dhaka after 8 October 2026;
  * a third frontier market.
* **Until then, the verdicts above are the record.**

## A note on the Dhaka data

The file supplied for Dhaka has day and month exchanged in its pre-2023 dates whose day is 12 or
less. This holds throughout 2009–2021; in 2022 the exchanged copies sit beside correctly dated
ones; and before 2009 there are 13 exceptions. The plan sets out the evidence (`nepsevol.frontier`
repairs 2009–2021 and drops 2022). Anyone
using that file for other work should repair or drop those dates first: as stamped, 37% of the
pre-2022 sessions (2,071 of 5,657 dates) sit at the wrong place in time.

One sentence of the frozen plan overstates the evidence. All 189 Friday stamps from 2009 to 2022
have a day of 12 or less. Before 2009, however, 13 of 153 do not, which is one more reason those
years are not used (`M-016`). No panel or result changes.

## Bottom line

**Where Anam wins.** Across two more frontier markets it does again what it did in M16: it beats
every classical range-based estimator, and its level is within 1% of close-to-close variance, while
theirs is off by between −37% and +71%.

**Where it doesn't.** It does not beat plain close-to-close at 5 sessions in either primary
panel, and Vietnam's close-to-close beats it at 21 sessions. The summary claim G fails.

**What to test next.** The one estimator that beat close-to-close at 5 sessions in every new
panel is Anam's own open-free form, a reported variant with no verdict attached. Whether it should become the frontier
version is now the question for a new frozen test.

## Implementation details and corrections

| ID | Detail | Effect |
|---|---|---|
| `M-016` | The plan's statement that "every Friday stamp before 2023 has a day of 12 or less" holds for 2009–2022 (189 of 189) but not before 2009 (13 of 153 have a larger day, or day equal to month). | None: the panels use 2009–2021 and 2023 onward only. The module docstring now states the evidence correctly; the plan's frozen text stands. |
