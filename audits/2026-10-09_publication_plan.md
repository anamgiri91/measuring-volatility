<!--
The publication development plan that accompanied the 9 October 2026 research audit, as received in the
author's working session, kept verbatim. Its links to RESEARCH_AUDIT.md point to
audits/2026-10-09_research_audit.md in this repository.
-->

# Publication development plan

This plan follows the [9 October 2026 research audit](RESEARCH_AUDIT.md). The first task is to repair and accurately delimit the existing evidence. The next is to choose one main contribution and develop it far enough to justify the target journal. A more confident abstract or a larger collection of markets will not substitute for these steps.

**Recommended direction:** develop a paper about daily volatility measurement when opening prices and observed extrema are contaminated. Use NEPSE as a motivating and diagnostic application. Treat the current estimator as a candidate method whose contribution must be established by derivation, ablation and independent validation. Keep a separate empirical market-design route available if institutional data can identify the reform's mechanism.

This is a research-development plan, not a prediction that the desired journal will accept the resulting paper. The schedule below assumes data access can be resolved; acquiring and validating new sources may take longer.

## Choose a contribution before expanding the paper

| Route | Main question | What would constitute a substantial contribution | Current obstacle | Target to consider after the evidence exists |
|---|---|---|---|---|
| Financial econometrics | What can daily bars identify about volatility under noisy opens, closes and sparse trading, and how should estimation/inference work? | A defensible identification or partial-identification result, an estimator with established properties, and independent validation | Unverified proxy assumptions and heuristic kernel interpretation | Journal of Financial Econometrics |
| Mathematical finance | What is the optimal or achievable estimation risk under a specified financial observation model? | A materially new theorem, bound, optimal procedure or computational result with financial relevance | Current results are mostly empirical and do not establish such a contribution | Mathematical Finance or SIAM Journal on Financial Mathematics |
| Empirical finance | How do market institutions alter daily volatility measures, and which practical procedures remain informative? | Credible data, fair forecasting, economically meaningful effects, transparent external validation | Forecast-design defects and incomplete source provenance | Journal of Empirical Finance |
| Market microstructure | How does the rule package change opening price discovery, and through which mechanism? | Stronger independent treatment variation or persuasive mechanism evidence, supported by institutional records | Simultaneous reforms, failed dose-response, short post-event window | Journal of Financial Markets |

These are fit assessments. Mathematical Finance explicitly emphasizes rigorous, novel methodology and financial insight; SIFIN asks for demonstrable mathematical developments or significant computational advances. Those ambitions require additional research, not simply relabeling the current empirical paper. [Mathematical Finance scope](https://onlinelibrary.wiley.com/page/journal/14679965/homepage/productinformation.html), [SIFIN scope](https://www.siam.org/publications/siam-journals/siam-journal-on-financial-mathematics/).

Do not try to make the same long manuscript simultaneously a data-cleaning guide, an India VIX validation paper, an IV-calibration paper, a causal reform paper and a new-estimator paper. Select the central question, retain supporting evidence, and move secondary analyses and correction history to an organized supplement.

## Phase 1 Correct the evaluation and the claims

Suggested effort: the first one to two weeks. This work is necessary for every publication route.

| Work item | Concrete change | Completion criterion |
|---|---|---|
| Forecast timing | Record origin, information cutoff and outcome-end dates; exclude training labels ending on/after validation/test start | Zero boundary-crossing training labels in every split and market |
| Calendar alignment | Preserve the exchange calendar and missing security observations; specify availability of each target and feature | Every target described as h sessions has exactly those h consecutive exchange sessions |
| Zero targets | Use canonical QLIKE, `log(f)+y/f`, including `y=0` | All observable zero targets are eligible; loss differences agree with the old formula on positive targets |
| Positive predictions | Restrict to an admissible forecast family, or reject an invalid candidate on the fixed sample | No parameter is rewarded by silently discarding its invalid forecasts |
| Common sample | Define eligibility explicitly and disclose zero-range/comparator-induced exclusions | Candidate selection and comparisons use documented common origins; coverage reported by liquidity |
| Weighting | Choose stock-day, equal-date or equal-security risk as the primary estimand | Optimization, mean difference and standard error estimate that same object |
| Calibration precision weights | Estimate floors using a training sample or past-only data | Future-data perturbations do not change purportedly predictable past weights |
| Single implementation | Share target and scoring logic across the research module, recheck and installable package | Package agreement tests compare with a correct calendar/timing specification, not just duplicated code |
| Correction record | Preserve original tables; issue a clearly dated correction analysis | A before/after table reports every affected headline and explains any change |

Add a small set of tests that address the actual failure modes:

1. Changing all post-cutoff returns cannot alter fitted pre-cutoff parameters.
2. Removing one intermediate exchange session cannot turn the next five retained rows into a five-session target.
3. A zero outcome yields a finite canonical loss and a defined paired loss difference.
4. A candidate with a nonpositive forecast is rejected or handled by a prespecified positive transformation; its sample does not shrink.
5. A deliberately unbalanced panel produces inference for the same weighting used in the reported mean.
6. Extending an observed range preserves contamination already in H/L, including the exact opening-print counterexample from this audit.

Same-day OHLC inputs are available for an **after-close** forecast. Using the current date to update b and κ is not automatically look-ahead bias. State this operational timing rather than shifting everything by one day unnecessarily.

Revise the abstract, introduction, estimator docstrings, README, model card, submission letters and conclusion together. Replace unsupported claims identified in A03–A07 and A12. Correcting only the limitations section leaves contradictory headlines intact.

**Gate 1:** run the corrected evaluation on every sample with available inputs. Reproduce the audit's original-baseline comparison first. Do not make a new superiority claim until all required inputs and corrected outputs are available. The audit's limited sensitivities do not replace this comprehensive rerun.

## Phase 2 Establish the data and the estimand

Suggested effort: weeks two to four, partly concurrent with Phase 1 if sources are available.

Define the primary target in a short methods note before further optimization. A defensible immediately available target is

`m_it(h) = E[(1/h) Σ[j=1..h] r_observed,i,t+j² | F_t]`.

That is an observed-return conditional second moment. If the paper instead targets efficient integrated variance or a jump-inclusive quadratic variation, state the price model and explain how the observed returns, auction prints, closing rules and limits relate to it. Do not imply that observing option prices would solve the physical-variance measurement problem.

Build an input ledger with provider, retrieval date, exact file/request identifier, hash, raw field definitions, units, price-adjustment convention, exchange, historical security identifier and reviewer-access instructions. Record missing information as missing. A hash is not a provenance substitute.

The highest-value data tasks are:

- Obtain original dated NEPSE circulars for the trading week, opening and continuous-session bands, daily limits and closing-rule changes. Reconcile publication and effective dates.
- Validate a sample of NEPSE adjustment flags against an independent corporate-action source, including discrepancies below the current tolerance and upward reference-price changes.
- Establish the original Casablanca provider and corporate-action factors; identify fixing versus continuous-trading securities and their applicable limits.
- Validate the Dhaka date repair against an independent session/price source. Retain the repaired history as secondary evidence unless the mapping can be established convincingly.
- Obtain Vietnamese exchange labels, point-in-time security membership and adjustment metadata. Avoid inferring exchange membership from the same returns being studied as the only validation.
- Publish counts at every filter, including no-trade dates, gaps, return/range screens, initialization, target observability and final common-sample restrictions.
- Report thin-security coverage before and after forecasting screens, so the scope of the thin-market claim is visible.

**Gate 2:** a reviewer must be able to obtain or access the inputs needed for each main result. If a panel's provenance cannot be resolved, remove it from the principal confirmation set or label it exploratory and reduce the headline accordingly. Resolve restricted-data arrangements before submission; do not describe missing data as packaged.

## Phase 3 Develop the methodological contribution

Suggested effort: weeks four to eight initially, potentially several months for a strong theorem. This phase decides whether JFEC or a mathematical-finance journal is a sensible target.

Start with a model that distinguishes the efficient overnight move, efficient intraday path, opening-auction error, closing error, observed noisy extrema, trading intensity and market rules. State which errors may depend on volatility or on each other. A realistic model need not identify everything; an honest impossibility or partial-identification result can be more useful than an unjustified point estimate.

Theoretical tasks, in order of dependence:

1. **Identification.** Characterize what the joint OHLC distribution and its lagged moments identify. Exhibit observationally equivalent mechanisms when a component cannot be recovered. Identify the normalization that determines the latent variance scale.
2. **Interpretation of b.** Derive its population limit under independent signal/noise, noisy previous close, correlated overnight/intraday efficient returns, price censoring and heterogeneous securities. Explain when b is a reliability ratio, when it is only a projection coefficient, and what clipping changes.
3. **Variance construction.** If using the fitted overnight move, account for residual uncertainty. Derive the kernel and blend from a loss or constrained optimization problem, or explicitly retain them as heuristics. Establish which opening/extreme contaminations the procedure can and cannot attenuate.
4. **Pooling and dynamics.** Analyze estimation with common market shocks, unequal security histories and heterogeneous b/κ. A fixed 60-date window does not automatically make estimation error vanish as time grows. Specify the asymptotic regime or provide finite-sample guarantees appropriate to the proposed use.
5. **Inference.** Include nuisance-parameter estimation, boundary clipping, generated forecasts and serial/cross-sectional dependence. If IV calibration remains central, develop sensitivity to instrument exclusion failures rather than treating persistence as sufficient for validity.

The appendix already contains useful identities and the repository has Monte Carlo tests. Those are a starting point. Nonnegativity, dimensional consistency and reproduction of a chosen simulation do not establish consistency, efficiency or robust latent-variance identification.

The crucial ablations should separate components:

| Comparison | What it establishes |
|---|---|
| Raw versus equally calibrated kernels | Whether apparent level improvement is only rescaling |
| Calibrated Parkinson versus calibrated true range | Value of including the previous-close anchor |
| Pure true range versus true range plus r² | Value of the close-to-close blend |
| Fixed b=0, fixed b=1, and estimated b | Value of estimating opening reliability |
| Fixed common pooling versus security-specific/hierarchical pooling | Value and cost of cross-sectional pooling |
| Common forecast dynamics versus separately tuned dynamics | How much performance comes from measurement versus forecasting |
| Constant-scale versus adaptive-scale versions | Value of adaptation and its cost around structural breaks |

Do not select the best ablation and call it confirmed on the same samples. Treat the existing samples as development evidence after these changes.

**Gate 3:** write a two-page contribution memo comparing the final method with Parkinson/GK/RS/Yang–Zhang, true-range methods, overnight weighting/scaling, errors-in-variables calibration and forecast combination. State one result that is new and useful. If the result remains a convenient heuristic with mixed forecasting performance, choose an empirical/applied route rather than claim a mathematical breakthrough.

## Phase 4 Challenge the method with independent evidence

Suggested effort: weeks eight to twelve, subject to data access and theory progress.

Freeze a new, externally timestamped protocol for a genuinely unexamined market or future period, after implementation choices are complete. List data already inspected, primary target, horizon, loss, weighting, model set, tuning scheme, missingness rules, exclusion logic, multiplicity family and economic-effect threshold. Do not create another holdout by relabeling data already used during the audit.

For forecasting, include strong and interpretable baselines: a historical return-variance forecast, EWMA, GARCH(1,1) and an asymmetric alternative, plus HAR-type or range-based dynamics where appropriate to the available data. Include pure calibrated true range and simple mixtures. Give all methods a fair tuning budget and information set. A flexible model should earn its place through incremental information; an arbitrary large model menu only creates another selection problem.

Use time-ordered training/validation/test periods with complete training outcomes and nested tuning when required. Keep the genuinely new test closed until specifications are final. Report QLIKE as the primary loss if justified, MSE as a prespecified secondary criterion, and interval estimates for both economic effect sizes and rankings. Different losses can legitimately rank imperfect forecasts differently.

Use dependence-aware joint comparison, such as a model confidence set, and a defined multiplicity adjustment for the primary claims. Non-overlapping origins and alternative block lengths are sensitivities, not guarantees of independence. [The model confidence set](https://onlinelibrary.wiley.com/doi/10.3982/ECTA5771) supplies a relevant primary reference.

Add validation that speaks to measurement rather than only future-return prediction:

- Use an independently sourced liquid-market dataset with intraday observations and a carefully constructed realized-variance benchmark, then evaluate the daily-bar method at matched scope and horizon.
- Degrade observation intensity and introduce controlled opening contamination to learn which errors the method addresses. This establishes performance under specified mechanisms, not causal truth about Nepal.
- Run a prespecified simulation grid with jumps, drift, correlated news, volatility-dependent auction errors, closing VWAPs, stale/zero trading, endogenous trade intensity, tick sizes, price bands, common shocks and rule breaks.
- Report biases, RMSE, losses, coverage, parameter estimation error and failure rates with Monte Carlo uncertainty. Include parameter settings unfavorable to the proposed method.

Add one economic application consistent with the chosen estimand, such as a clearly specified risk-budgeting or volatility-targeting exercise with implementable trading timing and realistic costs. If evaluating VaR/ES, fit and evaluate a return-distribution model; a variance forecast alone does not determine a quantile. Economic use should demonstrate relevance without changing the main criterion after seeing results.

**Gate 4:** assess whether the new evidence supports a useful claim. A failure to improve on simple baselines is a result to report, not an instruction to keep searching markets until one works. An estimator paper needs defensible incremental value; a measurement-diagnostics paper can remain useful even if its proposed estimator fails.

## Optional empirical branch Strengthen the reform analysis

Pursue this if the market-design result becomes the main contribution. It is not a shortcut around identifying assumptions.

Obtain opening-auction trades, volume, indicative prices, order imbalances or auction participation where available, and extend the post-reform span. Seek treatment variation that differs across instruments or venues for institutional reasons known before the event. Study whether opening reversals are associated with auction liquidity, tick size, pinned orders and the continuous-session path.

Define the policy estimand as the effect of the whole rule package unless the data supply separate variation in its components. Use an event-study design appropriate to the actual assignment mechanism and document concurrent news and institutional changes. If an exposure design is used, measure exposure before the event, show pre-trends and avoid defining treatment by post-event outcomes. There is still only one common market event; security-level precision cannot replace treatment-level identification.

If those data are unavailable, retain the observed break and covariance decomposition as descriptive evidence, and remove isolated-band causal claims from the title, abstract and cover letter.

## Phase 5 Rebuild a focused submission

Suggested effort: the final two to three weeks after the research gates are met.

Proposed title for a measurement paper: **Daily volatility measurement with noisy opening prices**. A descriptive reform paper could use **Opening returns and volatility measurement around a market rule reform**. Final titles should reflect the evidence actually obtained. A descriptive method name will also travel more naturally across an anonymous manuscript and reproducibility package than an author's name.

An effective main-paper structure would be:

1. The precise measurement problem, main result and closest literature.
2. Observation model, estimand and identifying assumptions.
3. Method, established properties and limitations.
4. Data provenance and relevant institutional setting.
5. One central validation exercise and a concise comparison with strong baselines.
6. External validation and one economic or market-design implication.
7. A short conclusion stating what has and has not been learned.

Aim provisionally for about six to eight main tables and three or four main figures, with cleaning details, alternative definitions, extensive sensitivity tables, derivations and the audit history in appendices/supplements. This is an editorial recommendation, not a quoted journal rule. Replace repetitive caveats with precise claims supported at the point of use.

A cautious provisional abstract, to revise after the corrected analysis, is:

> Daily volatility measures can be distorted when opening prices contain transient components. Using ordinary-equity data from Nepal, we document opening-return reversals and decompose the difference between Yang–Zhang and close-to-close variance. A pronounced change coincides with a market-rule package, whose individual components cannot be separated. We study calibrated range-based forecasting procedures and obtain mixed performance relative to close-to-close returns. The evidence highlights the distinction between agreement with an observable return proxy and accuracy for latent variance, and the importance of exchange calendars, forecast timing and data provenance.

This deliberately describes the present evidence without promising the future theory. A final JFEC abstract should emphasize whatever methodological contribution Phase 3 actually establishes.

Build the manuscript from one canonical tracked source with explicit dependencies and an end-to-end command. A submission run should produce all required results, manuscript, anonymous set and a current rendered PDF; fail if a required dataset or analysis is unavailable; and retain a machine-readable log showing reproduced, reused or skipped artifacts. Add a release identifier and archive data/code with access provisions appropriate to the sources.

Complete author/contact/ORCID details and journal-specific format checks. JFEC's current limits are 100 abstract words and two to six keywords; its editorial replication requirements also need to be addressed explicitly. [JFEC instructions](https://academic.oup.com/jfec/pages/general_instructions). Do not send the current “complete package” letter while external inputs are missing.

## Submission readiness decisions

| Gate | Evidence required | Decision if absent |
|---|---|---|
| Evaluation integrity | Purged labels, calendar-consistent horizons, fixed eligible samples, coherent losses and inference | Correct before any submission |
| Data credibility | Traceable sources and a reviewer-access route for every principal panel | Narrow the claim/sample or obtain access |
| Identification | Explicit target, justified assumptions and sensitivity to their failure | Restrict conclusions to observable quantities |
| Incremental contribution | A clear methodological result or compelling empirical mechanism beyond known formulas | Reframe for an empirical/applied journal |
| External confirmation | Evaluation untouched by method selection, with complete reporting | Label results as historical/development evidence |
| Manuscript coherence | Focused narrative, consistent claims, deterministic current submission set | Rebuild and review before submission |

The highest-return next step is **Phase 1 plus the estimand note from Phase 2**. Those results will show which claims survive and determine whether further effort should go into econometric theory, auction data or a more focused empirical paper.
