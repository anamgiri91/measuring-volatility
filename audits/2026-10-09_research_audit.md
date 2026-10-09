<!--
The independent research audit of 9 October 2026, as received in the author's working session. It is kept
here verbatim so that the response (RESEARCH_AUDIT_RESPONSE.md) and plan M20 can cite its item numbers.
The diagnostic files it links (artifact_checks.json, forecast_design_checks.csv, forecast_sensitivities.csv,
measurement_point_checks.json, verify_research.py, opening_noise_counterexample.csv) were not supplied with
it and are not in this repository; the links are left as written.
-->

# Research audit for journal submission

Audit date: 9 October 2026. Repository reviewed: commit `55a3ab4`. This is an independent, post hoc audit of the current research and submission files, with new diagnostics stored in this directory. The manuscript, original analyses, frozen results, and existing audit register have not been changed.

**Assessment: do not submit the current version to Journal of Financial Econometrics, Mathematical Finance, or SIAM Journal on Financial Mathematics.** There is useful empirical work here, especially the instrument-composition audit, opening-return reversal, and Yang–Zhang covariance decomposition. However, the current package has confirmed forecasting-design defects, incomplete external-data reproducibility, and claims about identification and efficient prices that exceed what its assumptions and tests establish. Fixing the code is necessary; reaching these journals also requires a clearer and stronger research contribution.

I found no basis in this audit to allege fabricated results or intentional misconduct. The repository discloses many failed predictions and past corrections. Passing tests and matching hashes establish internal consistency, however, not source authenticity or the validity of the research design.

## What was checked

I inspected the current Word manuscript, anonymous manuscript and submission letters; the README and analysis plans; the previous audit responses; estimator, calibration, opening-price, panel-construction and forecasting code; the package's forecasting implementation; frozen output tables; and the submission manifest. I read journal guidance and selected primary literature. This was not an exhaustive verification of every reference or every institutional claim against original exchange circulars.

Executed checks:

- Installed the exact research dependency pins in an isolated environment: Python 3.14.7, NumPy 2.5.2, pandas 3.0.5, statsmodels 0.14.6, SciPy 1.18.1, arch 8.0.0. Python is one patch above the documented reference interpreter.
- Ran the full existing test suite: **326 passed in 47.84 seconds**.
- Verified the original manifest: **333 listed files, zero missing files or hash mismatches**.
- Checked the three packaged main panels for duplicate security/date keys and OHLC-envelope violations: **zero of either**.
- Recomputed all nine estimators' M16 forecast losses for the main NEPSE holdout and both indices, at both horizons. Maximum absolute difference from the committed QLIKE values was below **5 × 10⁻¹¹**.
- Recomputed the central opening coefficients and the Parkinson IV-calibration point estimate and J statistic. They reproduce.
- Ran separate, explicitly post hoc forecast sensitivities and exact mathematical counterexamples, described below.

**Limits:** I did not rerun the complete producer pipeline, all bootstrap confidence intervals, or all Monte Carlo experiments. The M17/M18 source inputs are absent from this checkout, so I could inspect their code and frozen outputs but could not independently recompute their results or quantify the new forecast defects there. Word files were inspected as text and structure; this audit is not a rendered-page layout certification.

Evidence is in [artifact_checks.json](artifact_checks.json), [forecast_design_checks.csv](forecast_design_checks.csv), [forecast_sensitivities.csv](forecast_sensitivities.csv), and [measurement_point_checks.json](measurement_point_checks.json). The [verification script](verify_research.py) reproduces these checks without replacing research outputs.

## Priority findings

“Blocker” means correct or resolve before submitting the affected research. “Major” means a substantive methodological or interpretive problem. “Moderate” means a bounded implementation or presentation problem. Some problems were already acknowledged in the repository; those are identified rather than presented as new discoveries.

| ID | Priority | Finding | Evidence status |
|---|---|---|---|
| A01 | Blocker | Training labels extend into the test period | Newly quantified on packaged data |
| A02 | Blocker | Forecast horizons stitch retained observations across missing exchange sessions | Newly quantified on NEPSE |
| A03 | Blocker for latent-volatility claims | QLIKE argument assumes an unbiased latent-variance proxy without establishing it | Confirmed methodological gap |
| A04 | Major | Effective-open interpretation confuses a predictor with a latent realization and its variance | Exact counterexample |
| A05 | Major | Extending the range does not remove an opening error embedded in the high or low | Exact counterexample |
| A06 | Major | Calibration is asserted more strongly than the identifying restrictions and intervals support | Previously disclosed in limitations, still overstated in summaries |
| A07 | Major | Event timing does not identify the pre-open band's isolated causal effect | Previously disclosed, still inconsistent wording |
| A08 | Major, impact unresolved externally | Zero future targets are excluded, and candidate forecasts can be scored on different training samples | Confirmed code behavior; bounded impact on packaged samples |
| A09 | Moderate | Reported mean loss differences and reported t statistics target different weightings | Confirmed, including opposite signs in one frozen comparison |
| A10 | Blocker for full replication | Four-market headline cannot be regenerated from the distributed inputs | Confirmed missing inputs |
| A11 | Major | External-panel source, adjustment, calendar and selection assumptions remain weak | Disclosed; independent validation still needed |
| A12 | Major | “Not significantly beaten” and historical tests are insufficient evidence of general superiority | Inferential and contribution gap |
| A13 | Moderate | A claimed predictable precision weight uses a full-sample quantile | Confirmed code behavior |
| A14 | Major for submission | Manuscript rebuilding and “complete package” statements are inaccurate | Confirmed packaging gaps |
| A15 | Moderate | Journal format and several smaller factual statements remain inconsistent | Confirmed from current artifacts |

### A01 Training outcomes cross the holdout boundary

`src/nepsevol/volforecast.py:69–72,99–105` constructs forward outcomes on the entire panel, then applies the training mask to the **forecast origin** only. It never requires the last outcome used by a training example to precede the test cutoff. Consequently, selection of the shrinkage parameter uses some test-period returns. The same problem is present in `anam-estimator/src/anam_estimator/model.py:133–167`, including the documented `train_end` workflow. Script 44 copies this construction, so its post hoc robustness checks inherit the issue.

| Sample | Horizon | Eligible training origins | Training origins using outcomes on/after test start |
|---|---:|---:|---:|
| NEPSE | 5 | 66,931 | **1,239** |
| NEPSE | 21 | 66,917 | **5,191** |
| NIFTY 50 | 5 / 21 | 1,900 at each horizon | **5 / 21** |
| S&P 500 | 5 / 21 | 2,397 at each horizon | **5 / 21** |

This is separate from the already disclosed fact that full-sample M15 findings informed the estimator design. A frozen plan does not make boundary-crossing training labels out of sample.

**Measured effect:** purging these origins changes NEPSE's fitted full-form and open-free weights from 0.65 to 0.70 at five sessions and from 0.65 to 0.75 at 21 sessions. It does **not** produce a significant win over close-to-close; the main qualitative result remains. The index weights and results are unchanged. These bounded effects should be reported, not exaggerated into a claim that all results collapse.

**Required correction:** define and retain an outcome-end date. Fit only where that date is strictly before the cutoff. Apply the same rule to tuning folds, development cross-regime comparisons, the package API, and all external-market tests. Add a test that changing every outcome on or after a cutoff cannot change a model fitted before it.

### A02 Five or 21 retained rows are not necessarily five or 21 exchange sessions

The rolling target in `volforecast.py:69–70` counts the next `win` rows within a security. NEPSE's forecast loader drops rows with missing coordinates (`scripts/40_anam_holdout.py:58–64`), and the frontier builder drops bars without a consecutive previous close and other screened records (`src/nepsevol/frontier.py:283–299`). Rolling over the resulting compacted panel bridges the holes. Historical forecast features also use retained rows.

| NEPSE holdout horizon | Scored origins | Targets spanning more exchange sessions than stated | Maximum span |
|---|---:|---:|---:|
| 5 | 53,168 | **218** | **47 sessions** |
| 21 | 48,912 | **618** | **81 sessions** |

These targets average a selection of surviving one-session returns across a longer interval. They do not measure the complete return variation over that interval either. The problem is especially relevant to a paper motivated by thin trading, although its size in the more irregular Moroccan and other external panels cannot be measured here.

I purged boundary-crossing training labels and restricted targets to consecutive session ordinals. The full-form NEPSE five-session weight became 0.75 and the loss difference versus CC rose from 0.01598 to 0.01938; its equal-date t rose from 1.19 to 1.58. Still no significant win or loss. The 21-session conclusion also remained inconclusive. This sensitivity fixes target continuity only; it is not a complete redesign of historical feature windows or missing-data handling.

**Required correction:** construct a security-by-exchange-calendar panel, preserve missing rows, and define horizon availability explicitly. Do not fill unobserved efficient returns with zero. Report the eligible universe and exclusion rates by liquidity. If transaction-time forecasting is intended instead, label it as such and abandon fixed-session interpretations and horizon-based dependence assumptions.

### A03 The forecast comparison does not establish accuracy for latent variance

The manuscript §6.8 calls future mean squared close-to-close returns “a conditionally unbiased target” and says QLIKE rankings therefore match those under true variance. `volforecast.py:1–15` makes the same assertion. The conclusion needs a specified latent target and a justified conditional-unbiasedness restriction. The relevant result is conditional, as emphasized in [Patton's primary publication record](https://scholars.duke.edu/publication/792433).

For an observed return, even without microstructure error,

`E[r² | F] = Var(r | F) + E[r | F]²`.

With `r_observed = r_efficient + ε_close,t − ε_close,t−1`, squared observed returns also contain closing-error and covariance terms. A last-trade close, a fifteen-minute VWAP close, stale trading, corporate actions and binding daily price limits need not measure the same efficient endpoint. Avoiding the open does not resolve these issues. Options would measure a different, risk-neutral object and would not automatically supply latent physical-variance ground truth either.

**Defensible claim now:** the exercise compares forecasts of the **future mean squared observed close-to-close return on the retained sample**, using a stated loss. That is a legitimate target. It does not by itself rank contemporaneous estimators of latent integrated variance. Each estimator also has separately tuned forecasting dynamics, so the comparison assesses a measurement-and-forecasting procedure, not just a daily measurement kernel.

**Required correction:** define observed-return second moment, conditional return variance, integrated variance, and jump-inclusive variation separately. Establish the extra assumptions before moving between them. Add a separate validation with known truth or a well-supported high-frequency proxy if latent measurement is central.

### A04 A linear predictor is not the permanent overnight realization

`src/nepsevol/estimators/anam.py:27–28` calls `PC exp(b o)` the best linear predictor of the efficient opening price and says `b o` **is** the permanent overnight move. The estimator description in §6.8 gives a similar interpretation.

Even in the favorable model `o = x + η`, with zero-mean independent efficient overnight move `x` and opening error `η`, and a subsequent efficient intraday move independent of both,

`b = Var(x) / [Var(x) + Var(η)]`.

Here `b o` is the best linear predictor of **the log move**, not its observed latent realization. Exponentiating it does not give a linear predictor of a price, or generally the conditional mean price. Moreover,

`E[(b o)²] = b Var(x)`,

which is below `Var(x)` for `0 < b < 1`. Squaring a denoised conditional mean omits residual uncertainty. In the illustrative case `Var(x)=1`, `Var(η)=3`, the true overnight variance is 1 and `E[(b o)²]=0.25`. A Gaussian posterior contributes the missing 0.75.

This does not prove that the calibrated total estimator is empirically poor. It proves that its overnight term is not justified as an unbiased estimate of permanent overnight variance by this argument. The common market calibration can correct an average scale without identifying each latent component or each security's scale.

**Required correction:** call it a shrinkage predictor/anchor. Derive a variance estimator from a stated loss and observation model, including residual uncertainty, or present the current construction as a heuristic forecast feature. Quantify heterogeneity in `b` and calibration rather than treating market pooling as an identified common error structure.

### A05 The range extension cannot remove an opening error already in an extreme

`anam.py:29–34` says the extension is set by the far extreme “so an overshooting open cannot inflate it.” If “it” refers only to the added extension term, that narrow claim needs to be explicit. It is false for the total extended range and kernel, and the surrounding explanation invites that stronger reading.

By definition `R* ≥ log(H/L)`: this operation extends the observed range; it never contracts a contaminated high or low. Take `PC = C = L = 100`, an otherwise flat efficient path, and a noisy opening print `O = H = 105`. With `b=0`, the effective anchor is 100 but `R* = log(1.05)`. The open-free daily kernel is positive solely because of the erroneous high. Larger opening errors increase it. [opening_noise_counterexample.csv](opening_noise_counterexample.csv) evaluates this directly through the research implementation.

**Required correction:** distinguish invariance to changing the **open column while holding H/L/C fixed** from robustness to an opening event that changes the high or low. Daily bars generally cannot reveal the next genuine extreme after removing an auction print. Measure the limits of the method under this contamination instead of claiming it removes it.

### A06 “Calibration, not cancelling errors” is too strong

The README's second answer, introduction and cover letters describe calibration as established. But the Parkinson slope's interval is **[0.760, 1.056]**. That interval is compatible with nearly 24% attenuation. Containing one establishes failure to reject a unit slope; it does not establish equivalence to one. The M14 “no detectable attenuation” verdict is appropriately narrower.

In addition, the frozen primary overidentification restrictions are rejected: Parkinson and GK have **J p = 0.0001883**, RS **p = 0.0012204** (`table78_calibration_full.csv`). The manuscript acknowledges this in limitation 13. The post hoc security-by-regime specification improves matters—Parkinson/GK p about 0.175, RS about 0.154—but does not retrospectively validate the primary assumptions.

Volatility persistence supplies relevance. It does not prove that lagged volatility measures are excluded from persistent spreads, auction errors or other measurement distortions. A rank-one share close to one describes the dominant covariance pattern, not exact instrument validity. Normalizing the OC proxy's loading to one identifies relative scale under the maintained model; it does not show that this proxy has unit loading on efficient latent variance.

**Required correction:** put identifying assumptions, rejections, the relative-scale interpretation, and sensitivity results beside the headline result. Use a prespecified equivalence margin if near-unit response is the claim. Report dependence-robust instrument-strength diagnostics: the current `first_stage_F` is calculated from a conventional fitted/residual sum-of-squares formula, not a cluster-robust weak-instrument diagnostic. Develop sensitivity to persistent and volatility-dependent measurement error.

### A07 The reform result supports a break around a policy package

The event coefficient and placebo ranking reproduce as documented, but the pre-open band, daily limit, continuous-session order band, circuit breakers and order queuing changed together. There is one treated market and one common event. The exposure-based DiD is **−0.019 [−0.173, 0.104]**, so the proposed cross-sectional identification did not succeed. These limitations are already disclosed in §6.7.

The abstract still calls the band a natural experiment; the introduction and cover letters say widening it produced the change. Overlapping placebo windows show an unusual historical break. They do not make the actual reform date exchangeable with placebo dates, rule out simultaneous shocks, or isolate the pre-open band's effect. Hundreds of securities do not create hundreds of independently assigned policy interventions.

Nor does a pooled slope below one identify behavioral overreaction by itself. Bid–ask effects, correlated efficient returns, reference-price errors, closing-price construction and selection into a boundary can also affect it. The “64–87%” figure is `1 − b`, a pooled projection statistic weighted by squared opening moves, not the fraction reversed on every day or the fraction of openings proved erroneous.

**Required correction:** say “a pronounced change coincided with the April 2026 market-rule package.” Reserve a causal band claim for a design with independent treatment variation and a supported mechanism. Obtain primary dated rule circulars, add longer post-event evidence, and investigate pre-trends and contemporaneous shocks. If those data cannot distinguish the components, keep the descriptive conclusion.

### A08 Outcome-dependent exclusions and parameter-dependent training samples

`volforecast.py:94` removes every zero future target. These are valid observations when forecasting squared returns, particularly in inactive markets. The normalized loss `y/f − log(y/f) − 1` is unsuitable at `y=0`; ranking losses with `log(f) + y/f` are well defined there for `f>0`. On a fixed positive-target sample the two losses differ only by a target-only term.

The grid also allows `φ` up to 2, so `φ current + (1−φ) longrun` can be nonpositive. The loss function then silently drops those origins separately for each candidate. A parameter can therefore be selected on a different set of observations from other parameters. Across NEPSE's five-session training grid, the largest such count change is **33,410 origins**.

**Limits of the finding:** no otherwise eligible zero targets occurred in the audited main NEPSE/index comparisons, and every selected parameter in frozen Tables 101, 108 and 113 is at most one. Thus this audit does not establish that the published selected forecasts use unequal final samples, or that zero filtering changes the packaged M16 results. The logic remains defective, and its zero-target effect in missing external panels is unresolved.

The common-sample rule additionally removes an origin if any comparator's recent kernel is zero, even when a positive long-run blend would provide a usable forecast. This can exclude exactly the difficult zero-range episodes the paper purports to address.

**Required correction:** retain zero outcomes with canonical QLIKE; define eligibility from known information and target observability; ensure every candidate is evaluated on the same eligible training sample. Use a positive forecast construction or reject inadmissible parameters rather than dropping observations. Report coverage losses by reason, market and liquidity group.

### A09 Loss levels and inference use different population weights

`volforecast.py:113–115` reports `diff.mean()` over stock-days but computes its t statistic from the equal-weight mean of per-date average differences. These are different estimands in an unbalanced panel. For Morocco, Anam versus `o2+P` at 21 sessions has a reported mean difference **−0.00009985** but a t statistic **+0.1893** (Table 116), demonstrating the distinction directly.

The NEPSE difference is small: at five sessions the full-form t is 1.192 under equal-date weighting and 1.206 using a date-level ratio-estimator influence calculation for the stock-day mean. No central conclusion flips in the audited samples.

**Required correction:** choose the economic weighting before tuning and use it for optimization, reported loss differences and inference. For a stock-day ratio use date sums and date counts consistently; for equal-date performance report equal-date mean losses. Show equal-security performance as a separate estimand. Account for persistence beyond mechanical overlap and fitted-parameter uncertainty in the final comparison.

### A10 External claims are not fully reproducible from this checkout

`data/external/frontier/` is absent. Scripts 42, 43 and 44 require these files; `run_paper_analysis.sh:47–62` skips them and then finishes with “Paper-facing reproduction completed successfully.” Frozen tables can be reformatted and tested for consistency without their empirical results being recomputed.

The manuscript's limitation 10, title-page availability statement and all cover letters nevertheless say the processed panels reproduce every result or that a complete package accompanies the submission. These claims became inaccurate when the M17/M18 findings were added.

JFEC requires source/data materials for editorial replicability review, with an exemption requested in the cover letter when compliance is incomplete. That is directly relevant to this package, rather than a hypothetical concern. [JFEC author instructions](https://academic.oup.com/jfec/pages/general_instructions).

**Required correction:** supply documented reviewer access to all necessary inputs, or request a specific exemption and accurately delimit what can be reproduced. Use an explicit partial-reproduction status. A hash proves file identity, not source quality, entitlement to distribute it, or that a reviewer can obtain it.

### A11 Data assumptions constrain external validity

The repository itself records these issues in `data/external/README.md` and M17/M18:

- The author-supplied Dhaka upload does not match the cited public dataset's row count. Dates before 2023 require a day/month repair; 2022 is dropped. The repaired older history is valuable sensitivity evidence, but weaker as a primary replication.
- The Vietnamese panels have no verified original provider/license, no explicit exchange labels, and retrospective corporate-action-adjusted, rounded prices. Three-character ticker selection does not establish a point-in-time ordinary-equity universe.
- Casablanca's original provider is unstated. Prices are unadjusted for corporate actions. Continuous and fixing securities are not distinguished when applying band screens.
- Dropping no-trade records, gaps and large moves changes the target population. In Morocco, 23,430 bars without a previous-session close are removed before forecasting. Surviving-sample performance does not validate the method on those missing thin-market cases.

Corporate-action detection in NEPSE is more explicit, but it remains a rule inferred from reference-price disagreements, not an independently matched event feed. Its 0.5% tolerance should not be justified simply as unavoidable two-decimal tick rounding for prices in the hundreds.

**Required correction:** establish provider and field definitions, archive calendars and rule schedules, acquire adjustment factors and historical security identities, validate ambiguous dates against an independent source, and publish a full sample funnel. Quantify exclusions' impact using information available before each forecast. Do not infer absence of survivorship bias or correct adjustment from a clean OHLC envelope.

### A12 Superiority, multiplicity and the contribution need stronger support

The revised manuscript correctly clarifies that “best” in its plans means no rival has significantly lower loss. That definition is still a weak positive claim: low power can make a poor estimator satisfy it. Lack of significant inferiority is neither equivalence nor superiority. A joint model-confidence-set procedure is a more defensible way to summarize a large comparison set. [Hansen, Lunde and Nason](https://onlinelibrary.wiley.com/doi/10.3982/ECTA5771).

The comparison is with six classical kernels embedded in one calibration/shrinkage model. It does not compare against all volatility forecasting approaches. The open-free variant beating the adaptive full form throughout frontier samples weakens the argument that **estimating the opening-reliability weight** is the valuable innovation. On the S&P 500 the full form is exactly `o² + Parkinson`. The existing shared-calibration recheck also shows the level agreement is largely mechanical. These disclosures are useful and should stay prominent.

The repaired Dhaka sample is not an independent market from recent Dhaka. Seven panels are not seven independent replications. Plans recorded after seeing prior market results are a sequential research process, not one globally untouched test. The history openly discloses rewriting and lack of an external registry; I found no reason to recast that disclosure as deception. Some code docstrings still say “before any holdout data were read,” contrary to M16's fuller disclosure.

**Required improvement:** compare against strong return-only forecasts, pure calibrated true range, fixed mixtures and nested versions of the method; isolate whether gains come from the range, pooling, calibration or shrinkage. Use joint inference, prespecified practical-effect margins and a genuinely new external evaluation. A targeted search that did not find the exact combination is not a demonstration of methodological novelty.

### A13 Predictable weighting is not strictly predictable as implemented

`src/nepsevol/calibration.py:284–297` first constructs a lagged scale, then floors it at `np.nanquantile(S, 0.01)` computed across the full supplied dataset. The empirical floor uses future observations. Thus the statement that the entire weight is `F[t−1]`-measurable “by construction” is false in finite samples.

This weight is used in calibration/noise analyses; it is **not** the pooled calibration coefficient in the forecast test, so it should not be conflated with A01. Its empirical effect has not been quantified in this audit.

**Required correction:** fix the floor from a training sample, use a past-only expanding estimate, or derive the effect of estimating the nuisance threshold jointly and describe it accurately. Rerun the relevant slope and noise sensitivities.

### A14 The manuscript is not built cleanly from the shipped source set

The README describes rebuilding the manuscript by applying a sequence of revision scripts. But `paper/apply_referee_revisions.py:881–890` defaults to an original Word document in the author's **Downloads** folder, which is not a tracked source. The pipeline does not run the manuscript/submission builders, and the declared environments omit `python-docx`, required by those builders. A recipient can possess the final Word file without being able to regenerate it from a complete source package.

Further, `build_manifest.py` writes descriptions of earlier successful pipeline executions; those descriptive strings are not evidence that the current invocation regenerated every result. The refreshed manifest authenticates the current listed bytes, not a new end-to-end execution. This is transparent on inspection but stronger reproducibility wording obscures it.

**Required correction:** ship a canonical editable manuscript source and one deterministic build entry point; declare document-building dependencies; derive verification status from captured execution results; fail a submission build if a required empirical step was skipped. Preserve the original manifest as a historical snapshot rather than interpreting a regenerated one as validation.

### A15 Submission and smaller inconsistencies

The current named Word manuscript contains approximately **25,752 words including tables**, **21,296 words in body paragraphs**, **38 tables**, a **255-word abstract**, and **14 keywords**. The anonymous version has a 256-word abstract. JFEC currently specifies an abstract no longer than 100 words and two to six keywords. [JFEC author instructions](https://academic.oup.com/jfec/pages/general_instructions). The length recommendation in the accompanying plan is editorial judgment; I did not find a basis to invent a universal journal page limit.

Additional confirmed items:

- The title page still contains author/contact/ORCID placeholders; cover letters contain `[Date]` and a placeholder signature.
- §7.2 calls **1.280 “higher than” 1.288**. It is lower. Numerical interpolation does not validate the surrounding prose.
- `data/processed/README.md` says the analysis panel has 184,390 rows; the shipped file has **184,391**. The main equity count remains correct at 143,718.
- §7.1 writes the rolling estimate as the average of daily `κ A`, whereas the implementation applies the **current** `κ_t` to the entire window average of historical kernels. Those coincide only if κ is constant or the notation explicitly uses the current κ throughout the window.
- Limitation 4 says NEPSE forecasting cannot be tested without options. §6.8 already performs such a forecast test. Remove the contradiction and the implication that options are required to evaluate physical-return forecasts.
- Calling the proxy-based intervals a “lower bound on total uncertainty” has no general demonstrated coverage result. They quantify sampling uncertainty for stated observable statistics; uncertainty about a latent target requires a model or sensitivity analysis.
- The current PDF is expressly a historical manuscript. A current submission PDF still needs to be rendered and checked. No layout verdict is given here.

## Claims that can be retained and claims to rewrite

| Current claim or implication | Evidence-supported wording |
|---|---|
| Range estimators are calibrated, not subject to cancelling errors | Unit relative slopes are not rejected; economically material attenuation remains compatible with the intervals, and primary restrictions reject |
| The opening move is mostly a transient pricing error | Opening returns have strong negative covariance with subsequent intraday returns; a transient-error interpretation needs stated assumptions |
| The band widening caused the break | The break coincided with the April 2026 rule package; the band's separate effect is not identified |
| `b o` is the permanent overnight move | `b o` is a clipped linear shrinkage predictor under a maintained signal/noise interpretation |
| The extended range removes opening overreaction | The anchor changes, but opening contamination already in H/L remains |
| Close-to-close is an unbiased benchmark for latent variance | Close-to-close avoids direct use of the open and supplies an observable target; latent-variance unbiasedness requires further assumptions |
| No classical estimator beats the proposed method | No listed comparator has significantly lower QLIKE under the specified pipeline and samples, subject to the evaluation corrections |
| Near-unit calibrated levels validate the kernel | Calibration explains most level agreement; incremental information requires separate testing |
| Tested out of sample under frozen plans | Historical tests used repository-frozen plans, disclosed prior knowledge, and require purging boundary-crossing labels |
| The package reproduces every result | Packaged-data analyses can be reproduced; external-market results require separately obtained inputs |

## Publication assessment

**Journal of Financial Econometrics:** the topic is relevant; the present research is not ready. The strongest route is a precisely defined measurement/inference problem with defensible identification, dependence-aware inference, fair forecasts and independently supported validation. A weighted combination of known kernels plus extensive empirical tables is not, by itself, a strong methodological contribution. This is my assessment, not a statement that the journal requires one particular theorem. The journal describes a focus on core statistical challenges in financial data. [Journal overview](https://academic.oup.com/jfec).

**Mathematical Finance:** substantial new research is needed. Its stated criteria emphasize methodological novelty, mathematical rigor and financial insight. Existing identities, a heuristic kernel and backtests do not yet provide that contribution. A meaningful identification/impossibility result, an optimal estimator under a realistic observation model, or a substantial result about noise and market constraints could change the fit. [Official scope](https://onlinelibrary.wiley.com/page/journal/14679965/homepage/productinformation.html).

**SIAM Journal on Financial Mathematics:** likewise a poor current fit. Its scope calls for demonstrable mathematical developments or significant computational advances. Merely adding proofs of nonnegativity or more simulations would not bridge that gap. [Official scope](https://www.siam.org/publications/siam-journals/siam-journal-on-financial-mathematics/).

**Empirical route:** an extensively revised paper aimed at Journal of Empirical Finance is more plausible in topic and format than a mathematical-finance submission, although still demanding. Journal of Financial Markets is a possible route if the opening-price mechanism and market-design identification can be materially strengthened. The latter field's concern with trading protocols and price formation is evident in its [published microstructure literature](https://www.sciencedirect.com/science/article/pii/S1386418104000382). These are judgments about fit, not acceptance predictions or a journal ranking.

The [publication plan](PUBLICATION_PLAN.md) specifies the corrections, new evidence, theoretical work and decision gates needed before choosing a target.
