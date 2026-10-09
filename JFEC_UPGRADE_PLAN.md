# Plan: upgrading the research for the Journal of Financial Econometrics

Written 2026-10-09. This is a working plan, not a frozen analysis plan; each confirmatory test it calls
for gets its own frozen plan before its data are read.

## 1. The honest starting point

No plan can make acceptance at the Journal of Financial Econometrics (JFEC) "very likely". It is a
selective field journal, and its referees are econometricians. The aim here is narrower and achievable:
turn the work into a paper that survives the editor's desk and gives referees what they require. In its
current form I would expect a desk rejection, for four reasons.

| What a JFEC referee needs | Where the paper stands now | Gap |
|---|---|---|
| A methodological contribution with theory: a model, identification, an estimator with known properties, inference | Anam's estimator is an empirical combination of known parts. Its constants (λ₀ = 0.2, 60-date pooling) were chosen on development data, and nothing is derived | **Large** |
| Validation against the object being estimated (integrated variance), usually through high-frequency data | No intraday benchmark anywhere. Evaluation is by forecast loss against noisy r², and the instrumented calibration test of Section 6.6 | **Large** |
| Comparison with the state of the art: HAR/CARR/GARCH-type models, realized measures, the recent daily-bar forecasting literature | Compared only with classical range estimators and close-to-close | Medium |
| Robust, pre-specified inference across many comparisons | Done post hoc in round 16. The record against close-to-close is loss-dependent, and Morocco's win is fragile | Medium |
| A focused paper | Five questions, three study generations, a market-design natural experiment, a long audit trail | Medium |

Assets that carry over: a real and under-studied problem (opening auctions that overreact), a measured
fact (the session undoes 64-87% of the overnight move), a natural experiment, out-of-sample evidence in
four frontier markets, an identification idea for markets without high-frequency data (M14), and a
reproducible package.

## 2. The target paper

**Working title:** *Daily Volatility from Daily Bars When the Opening Price Is Noisy*

**One-paragraph pitch.** Range-based estimators assume the opening price is an efficient price. In
markets where the open comes from a thin call auction, it is not, and every estimator that reads the open
inherits its error. The paper makes four contributions:

1. A model of daily bars with a noisy open (independent noise, proportional overreaction, an error that
   decays during the session, and censoring at a pre-open band).
2. What the bar identifies under that model: the open's unbiasedness coefficient identifies the
   signal share of the overnight move.
3. The minimum-variance unbiased quadratic estimator of daily variance under it, a Garman–Klass (1980)
   problem with a noisy open. A feasible version estimates the nuisance parameters from the
   cross-section, with asymptotic theory.
4. An evaluation method for markets without high-frequency data: the instrumented calibration test.

High-frequency data, where the open comes from a call auction, validate the estimator. Four frontier
markets apply it. The Nepal band reform is a shift in the opening noise that the estimator must track.

**Positioning.** It generalises Garman–Klass, Rogers–Satchell and Yang–Zhang to a noisy open. It is
complementary to Hansen & Lunde (2005) on overnight weighting, and it answers Lyócsa, Molnár & Výrost
(2021, IJF) for markets where daily bars are all there is.

## 3. Workstreams

Each workstream ends at a gate. If a gate fails, the plan changes before more work is spent.

### W1. Literature and novelty check (1-2 weeks)
- A systematic search on the topics below, each reference verified against the publisher record before
  citing:
  - range estimators: Parkinson; Garman–Klass; Kunitomo; Rogers–Satchell; Yang–Zhang;
    Alizadeh–Brandt–Diebold 2002; Chou 2005 (CARR); Brandt–Jones 2006; Christensen–Podolskij 2007;
    Martens–van Dijk 2007; Molnár 2012; Lyócsa–Molnár–Výrost 2021;
  - overnight and open: Hansen–Lunde 2005; Ahoniemi–Lanne 2013; Tsiakas 2008;
  - opening auctions: Biais–Hillion–Spatt 1999; Cao–Ghysels–Hatheway 2000; Barclay–Hendershott 2003;
  - measurement error: Hansen–Lunde 2014;
  - forecast evaluation: Patton 2011; Hansen–Lunde–Nason 2011; Giacomini–White 2006; Corsi 2009.
- **Gate:** no published paper derives range estimators under a noisy or overreacting open. If one
  exists, the contribution shifts to identification and evaluation (W2 part 2 and W4) rather than the
  estimator.

### W2. Theory (3-6 weeks; the core of the JFEC paper)
1. **Model.** Write the bar coordinates: o = η + e, r = η + D, c = D − e. Here η is the efficient
   overnight move, D the efficient intraday move and e the opening error. Cover four cases:
   1. e independent of η and D;
   2. overreaction e = θη + ν (the case Section 6.7 found in NEPSE);
   3. an error that decays during the session, which reaches the high and the low;
   4. censoring of the open at a pre-open band.
2. **Identification.**
   - Case 1: E[o·r] = σ²_overnight, and b = σ²_η / (σ²_η + σ²_e). Under Gaussianity, b·o is exactly
     E[η | o], which turns the "effective open" from a heuristic into a theorem.
   - Case 2: the (o, c) moments under-identify; show which range moments restore identification.
3. **Bias of the classical estimators** (Parkinson, GK, RS, YZ, overnight² + Parkinson) under each
   case, in closed form where possible and numerically otherwise.
4. **Optimal estimator.** Find the minimum-variance unbiased quadratic estimator in (o, u, d, c) under
   each case, as a function of the nuisance parameters. This is Garman–Klass's own problem with a noisy
   open: the weights come from the moments of the Brownian range started at a noisy open, computed
   numerically to high precision. Then:
   - compare the frozen kernel, with its ad hoc 0.2 blend, to the optimum;
   - if it is close, the frozen evidence keeps its value; if not, the optimal estimator becomes version
     2 and needs fresh tests (W6).
5. **Feasible estimator and inference.**
   - Estimate the nuisance parameters from cross-sectional pooled moments (large N) or a series' own
     history (large T).
   - Derive consistency and asymptotic normality, and the effect of plug-in estimation (by delta
     method).
   - Give confidence intervals for a window's variance.
   - The calibration κ becomes a specification check: under the model κ = 1, so testing κ = 1 tests the
     model.
6. **The instrumented calibration test (M14) as a method.** State the conditions (measurement error
   uncorrelated with lagged proxies; persistence for relevance), building on Hansen & Lunde (2014).
   Cover size and power, and weak-instrument diagnostics.
- **Gate:** every result is checked by simulation to machine precision before it is written.

### W3. Monte Carlo (2-3 weeks)
- Extend the existing simulation testbed with:
  - stochastic volatility, and jumps overnight and intraday;
  - discrete and thin trading, tick size and bid-ask bounce;
  - the four noise cases, and a ±2% pre-open band that censors the auction.
- Report bias, RMSE against integrated variance, interval coverage, and forecast loss inside HAR. Cover
  every classical estimator, both forms of the current estimator, the optimal estimator, the
  Lyócsa et al. average of range estimators, and close-to-close.
- **Gate:** the theory's predictions about who wins, and when (as a function of b), hold in
  simulation.

### W4. High-frequency validation (3-4 weeks; depends on data access, decision D1)
- Find a market with a call-auction open and intraday data. The benchmark is realized variance from
  5-minute returns, plus the overnight return (Hansen–Lunde 2005 weighting).
- Measure each daily estimator's bias and MSE against it.
- Test the noise model directly: compare the open print with the first minutes' VWAP; check whether
  the error is proportional to overnight news; check how fast it decays.
- Forecast with realized-variance targets, which give far more power than r².
- **Gate:** where b < 1, the optimal (or current) estimator beats the classical range estimators
  against realized variance. If it does not, the paper becomes an identification-and-evaluation paper,
  or moves down the venue list (§6).

### W5. Benchmarks and inference to JFEC standard (2 weeks)
- Feed each daily estimator into HAR (Corsi 2009), CARR (Chou 2005) and a range-based GARCH.
- Compare against Lyócsa et al. (2021), using:
  - the model confidence set (Hansen–Lunde–Nason 2011);
  - Giacomini–White conditional tests, to show when the estimator helps (conditional on b);
  - QLIKE as the primary loss and MSE as secondary, with a rule for disagreement fixed in advance.
- Replace the 60-date calibration with a principled adaptive one (an exponentially weighted window
  with its half-life chosen by out-of-sample likelihood, or a change-point reset). The NEPSE reform
  showed the lag.
- Test it at Morocco's three dated band changes (2020, 2021, 2023), as frozen tests.

### W6. Fresh confirmatory evidence, externally registered (2-4 weeks after the data exist)
- Register each plan on OSF (or AsPredicted) before its data are read, so the timestamps no longer rest
  on the package's own history.
- Tests:
  - NEPSE after 26 August 2026: the fresh holdout the round-16 recheck asked for, which also extends
    the post-reform window of the natural experiment;
  - a held-out later span of the high-frequency sample;
  - version 2 of the estimator, if W2 produces one.

### W7. Rewrite as an econometrics paper (3-4 weeks)
- **Structure:**
  1. Introduction
  2. Model and identification
  3. Estimator and inference
  4. Evaluation without high-frequency data
  5. Monte Carlo
  6. Empirics: high-frequency validation; four frontier markets; the band reform as a shift in noise
  7. Conclusion

  About 35 pages, with proofs and extra results in an online appendix.
- **Cut or move:**
  - to a companion paper (decision D2): the instrument-composition audit, the NEPSE calendar and data
    construction, the India VIX exercise and the AddRS discussion;
  - to the replication package: most of the audit trail.
- **Name:** econometrics papers usually describe an estimator rather than name it after its author.
  Consider describing it in the paper (for example "the noisy-open range estimator") and keeping
  "Anam's estimator" for the package (decision D4).

### W8. Before submission (ongoing)
- Post a working paper (SSRN or arXiv).
- Present at the Society for Financial Econometrics (SoFiE), JFEC's own society, or a SoFiE summer
  school, and at least one seminar.
- Get comments from a financial econometrician, ideally as a co-author (decision D3).
- Check the journal's current author guidelines and data-and-code policy at submission time.

## 4. Decisions only the author can make

- **D1. High-frequency data.** Options, roughly best first:
  - NEPSE trade-level floorsheets with timestamps, if they exist (validation in the very market
    studied);
  - NSE India 1-minute bars (public datasets; NSE opens with a pre-open call auction);
  - TAQ through WRDS, if you have university access;
  - Chinese A-share minute data (call-auction open).
- **D2. Split the paper?** I recommend yes. The JFEC paper becomes the estimator and identification
  paper. The band-reform and data-construction work goes to a market-design paper (Emerging Markets
  Review or JIFMIM).
- **D3. A co-author** with a record in financial econometrics. It is optional, but it is the single
  largest raise in the odds.
- **D4. The name** in the paper (see W7).
- **D5. Version 2 of the estimator.** If theory gives different weights, adopt them and re-test under
  new frozen plans? The current frozen tests remain as first-generation evidence either way.
- **D6. Fresh NEPSE daily data** after 26 August 2026: from the same source as before.

## 5. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| The optimal estimator is not materially better than close-to-close or GK | The estimator contribution shrinks | Lead with identification (b, the bias formulas) and the evaluation method; the IJF or JEF fit improves |
| No high-frequency data obtainable | The biggest JFEC objection stays open | Rely on Monte Carlo plus the instrumented test; lower the target |
| Gains depend on the loss function | Referees doubt robustness | Fix losses and disagreement rules in advance (W5); report the model confidence set |
| The novelty check finds prior work | Contribution narrows | W1 runs first, before theory |
| Single, outside author | Desk risk | W8: working paper, SoFiE, co-author |

## 6. Venues, in order

1. Journal of Financial Econometrics (the target, after W1-W7).
2. Journal of Business & Economic Statistics, if the theory turns out strong; otherwise the
   International Journal of Forecasting, if the forecasting evidence is the strongest part.
3. Journal of Empirical Finance; Quantitative Finance.
4. Journal of Forecasting; Emerging Markets Review (the companion paper's first choice).

## 7. Who does what

- **I can do:**
  - draft the derivations, with every step checked numerically;
  - the Monte Carlo study;
  - all data work and estimation once data are supplied;
  - the HAR, CARR, GARCH, model-confidence-set and conditional-test machinery;
  - the adaptive calibration;
  - the frozen plans;
  - the rewrite, and the replication package.
- **The author must:**
  - check the theory;
  - supply or license the data (D1, D6);
  - register the plans externally;
  - make decisions D1-D6;
  - present the work and seek outside comments.

## 8. Timeline (indicative)

| Weeks | Work |
|---|---|
| 1-2 | W1, D1-D6 decided, data requested |
| 3-8 | W2 theory, W3 Monte Carlo |
| 6-10 | W4 high-frequency validation, W5 benchmarks (once data arrive) |
| 10-12 | W6 registered confirmatory tests |
| 12-16 | W7 rewrite; working paper posted |
| 16+ | W8 seminars and SoFiE, then submission |

The machine-learning forecaster (`anam_estimator.ml`, experimental) is not part of the JFEC paper. It
could appear in W5 as a flexible benchmark, under its own frozen plan.
