# Calculating Volatility in Frontier Markets Without Options

**Evidence and a practical framework from the Nepal Stock Exchange**

Anam Giri · Draft research paper, August 2026

Replication package for a study of how volatility can be measured in a cash-only
frontier market. The Nepal Stock Exchange (NEPSE) has no exchange-traded equity
options or futures, so there is no option chain to invert and no NEPSE analogue of
the VIX. This repository contains the estimator library, cleaning pipeline, and
analysis scripts that ask what *can* be measured from daily OHLC data instead, and
how far those measurements can be trusted.

---

## The short version

Volatility in a frontier market is as much a **data-engineering** problem as an
econometric one. Three findings drive the paper:

**1. Ordinary equity is far more usable than the exchange's published file suggests.**
Across 143,149 stock-days for 291 ordinary equities (March 2024 – August 2026), the
Parkinson standard-deviation ratio against a matched open-to-close benchmark stays
between **0.935 and 1.058** across liquidity groups. The thinnest equity bucket has a
zero-range rate of just **1.63%**. Range estimators do not collapse under thin trading.

**2. The apparent collapse is an instrument-composition artifact.**
NEPSE publishes ordinary equity, corporate debentures, closed-end funds, and
restricted promoter shares in one daily table **with no instrument-type field**. Pool
them, sort by trading intensity, and the thinnest quintile returns a Rogers-Satchell
variance ratio of **0.172** — which looks like catastrophic estimator failure and is
really an asset-class ranking. The thinnest pooled decile is **94.3% non-equity** by
stock-day.

| Measure | Pooled universe | Ordinary equity |
|---|---:|---:|
| Stock-days | 184,390 | 143,149 |
| Median trades/day | 111 | 165 |
| 10th percentile trades/day | 4 | 37 |
| Stock-days below 10 trades | 14.8% | 1.6% |
| P(H = L) | 5.70% | 0.28% |
| Rogers-Satchell exactly zero | 15.25% | 4.35% |

**3. Daily ranges carry real information about the option-implied volatility state —
but do not dominate close-to-close.**
On the NIFTY 50, where an options market exists, 21-session Parkinson volatility
correlates **0.776** with India VIX (R² = 0.602). Standard 21-session close-to-close
volatility correlates **0.796** (R² = 0.634). Both track the volatility state that
options price; the range measure does not outperform in this validation. This is a
validation anchor, **not** an implied-volatility substitute — Parkinson is backward-
looking and statistical, India VIX is forward-looking and risk-neutral.

A corollary worth its own line: **do not import a bias correction without testing its
premise.** Additive Rogers-Satchell (AddRS) lands at 1.005 of benchmark on NIFTY 50,
but reaches **1.149–1.323** on NEPSE equity, where no downward RS bias is detectable
against the available proxy. The correction is non-negative by construction, so where
the base estimator is not deficient it can only overshoot.

---

## Repository layout

```
src/nepsevol/            estimator + cleaning library
  estimators/
    range_.py            Parkinson, Garman-Klass, Rogers-Satchell, GKYZ,
                         Yang-Zhang, realized range, AddRS
    simulate.py          price paths with KNOWN sigma, sampled at controllable
                         trade intensity — the discretisation-bias experiment
    ratios.py            scale-explicit variance vs SD ratios
  clean/
    ohlc.py              envelope repair + duplicate-key resolution
    limits.py            price-limit and pre-open band censoring detection
    special_sessions.py  documented make-up sessions, with evidence status
  trading_calendar/      session detection from data, not a weekday rule
  universe/              instrument classification, validated against par value
  sample.py              universe selection (equity vs full)
  validate.py            invariants that HALT the build
  provenance.py          versioned build manifests

scripts/                 numbered pipeline stages (see mapping below)
tests/                   estimator validation + audit regression tests
data/processed/          committed analysis artifacts + build manifest
data/raw/                empty by design — see Data availability
```

---

## Installation

Requires **Python 3.12+**.

```bash
git clone https://github.com/anamgiri91/measuring-volatility.git
cd measuring-volatility
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest
```

Dependencies are pinned to exact versions. A replication package that floats its
dependencies does not replicate — numeric output can move across minor releases of
pandas, numpy, scipy and statsmodels, and results here are reported to three decimals.

---

## Data availability

**`data/raw/` ships empty, deliberately.** The raw NEPSE series was self-scraped from
a source whose redistribution terms are unresolved. Until provenance and licence are
established, the conservative state is to keep it out of the public package — public
is the harder state to undo. See [`data/raw/README.md`](data/raw/README.md) for the
contract governing anything later placed there.

**Processed analysis artifacts are committed**, so the core equity results can be
reproduced without the private vault:

| File | Rows | Securities | Coverage |
|---|---:|---:|---|
| `panel_long.parquet` | 505,525 | 372 | 1995-07-20 → 2026-08-26 |
| `panel_trades.parquet` | 286,994 | 521 | 2024-03-04 → 2026-08-26 |
| `panel_trades_clean.parquet` | 184,430 | 521 | session-filtered, 569 sessions |
| `equity_sample.parquet` | — | 291 equities | primary estimation universe |
| `analysis_sample.parquet` | — | mixed | composition-warning universe |

`panel_trades_clean` carries 184,430 rows and 521 securities; the paper's pooled
analysis sample reports 184,390 stock-days and 520 securities, the difference being
the positivity, return, and feasible-range screens applied downstream.

Scripts that need the private vault expect it as a **sibling** directory:

```
../private/data-vault/raw/                 stock-daily-long/, stock-daily-trades/
../private/data-vault/raw/external/        nifty50.csv, india_vix.csv
../private/data-vault/raw/                 nepse_index_history.csv
```

Every processed artifact is stamped by `nepsevol.provenance` into
[`data/processed/BUILD-MANIFEST.json`](data/processed/BUILD-MANIFEST.json), which
records the git commit, the aggregate SHA-256 of the raw inputs, a hash of the
cleaning code, the version of every cleaning rule in force, and the shape of each
artifact. An artifact that cannot say which code and which raw data produced it is
not evidence.

---

## Reproducing the results

Scripts write to `output/figures/` and `output/tables/`.

| Script | Produces | Paper exhibit | Runs from this repo alone? |
|---|---|---|:--:|
| `02_build_panel.py` | the three panels + repair audits | §3 | ✗ needs raw vault |
| `03_descriptive.py` | Tables 1–3, Figures 1 & 5 | §5.2, §6.1 | ✓ |
| `09_cross_market_control.py` | Tables 14, 15, 30; Figure 12 | §6.2, §6.3 | ✗ needs NIFTY + VIX |
| `12_benchmark_diagnosis.py` | Table 18, Figure 14 | §5.4 | ✗ needs NIFTY + index |
| `13_opening_auction.py` | Table 19, Figure 15 | §5.3 | ✓ |
| `17_addrs_benchmark.py` | Table 23, Figure 18 | §6.4 | ✗ needs NIFTY |
| `19_addrs_premise.py` | Table 25 | §6.4 | ✗ needs NIFTY + index |
| `22_universe_composition.py` | Table 27, Figure 21 | §5.1 | ✓ |
| `24_duplicate_key_reconciliation.py` | Table 29 | §3 | ✗ needs raw vault |

The four vault-dependent cross-market scripts are the NIFTY 50 / India VIX validation
and the raw-panel audit. Everything resting on the committed NEPSE equity panels —
including the paper's central composition result (§5.1) — runs from a clean clone.

*Runnability above is determined by reading each script's declared inputs; the scripts
have not been executed in a fresh environment as part of writing this README.*

---

## Estimators

All functions return **daily variance** — not annualised, not sigma. Callers
annualise explicitly with a session count from `nepsevol.trading_calendar` rather than
assuming 252, because NEPSE's session count is neither 252 nor stable across its
April 2026 schedule change.

| Estimator | Uses | Strength | Frontier-market risk |
|---|---|---|---|
| Close-to-close | C_t, C_{t−1} | robust to H/L errors | discards intraday path; stale closes |
| Parkinson | H, L | efficient use of range | zero range when trades are few |
| Garman-Klass | O,H,L,C | range plus O→C move | opening jumps; invalid bars |
| Rogers-Satchell | O,H,L,C | drift-independent | discrete extrema; monotone-day zeros |
| Yang-Zhang | prior C + OHLC | includes overnight variation | calendar definition; window dependence |
| AddRS | OHLC + boundary term | targets discrete-extrema bias | overcorrects if no downward bias exists |

Every estimator is tested against a case with a **known answer** — see
`tests/test_estimators.py`, which validates each one against a densely-sampled
simulated path with true sigma fixed by construction. These are four-line formulas
that are easy to write and easy to get subtly wrong, and a wrong one produces
plausible numbers rather than an error.

---

## Design decisions that carry the results

These are the parts most likely to be reused, and each exists because something went
wrong first.

**Cleaning order is load-bearing.** `resolve_duplicate_keys` must run on *original,
unrepaired* values, before `repair_ohlc`. Repairing first can push two genuinely
conflicting records' extrema out to the same `max(H,O,C)` / `min(L,O,C)`, silently
reclassifying a price conflict as an exact duplicate. The order is exported as
`CLEANING_ORDER` and enforced by test.

**Envelope repair never touches open or close.** O and C are single transaction prices
carried from the tape; H and L are session extrema and are the fields an exchange feed
most often reports inconsistently. Repair is `H := max(H,O,C)`, `L := min(L,O,C)`,
idempotent and order-independent, with every changed value itemised in
`data/processed/audit/`.

**Duplicates are excluded, not tie-broken.** 622 exact-duplicate keys are collapsed;
18 keys with conflicting OHLC are dropped whole rather than resolved by file order.

**The trading calendar is detected, not assumed.** NEPSE traded Sunday–Thursday and
moved to Monday–Friday in April 2026. A hard-coded Sun–Thu filter deletes genuine
Friday sessions and retains stale Sundays after the change — contaminating precisely
the window containing the widened price-band regime. Sessions are inferred from a
staleness signature instead.

**Instrument type is recovered and validated.** No type field exists, so type is read
from ticker convention and confirmed against par value (funds ~10, equity/promoter
~100, debentures ~1,000). The fund band is separated by an empty interval — the
51st-lowest median close is 10.78, the 52nd is 100.00 — so funds are identified by
price with no judgement call.

**Invariants halt the build.** `nepsevol.validate` raises; it does not warn. A warning
in a long run log is not a guard, and the reason several defects here survived into
committed results is that nothing refused to continue.

**Ratio scale is explicit.** Variance ratios and SD ratios differ by a square root.
Both were once computed under the bare name `ratio`, and the same quantity appeared in
adjacent manuscript sections as 0.980 and 0.965 purely because one script applied
`np.sqrt` and the other did not. `nepsevol.estimators.ratios` returns a scale label
with every value and raises on mismatched comparison.

---

## Practical protocol

The paper's operational recommendation (§7), condensed:

1. **Define the target first** — within-session volatility, or total daily risk
   including overnight variation. They need different estimators and different benchmarks.
2. **Restrict the universe to the intended asset class** before ranking by liquidity.
   Do not let debentures, funds, or promoter shares define the "thin stock" bucket.
3. **Validate every bar**: `L ≤ min(O,C) ≤ max(O,C) ≤ H`. Negative simplified
   Garman-Klass or Rogers-Satchell on an invalid bar is a data problem, not a market
   phenomenon.
4. **Use the genuine session calendar.** "Previous close" means previous *session*.
   Annualise on the market's actual session count.
5. **Compute at least two estimators.** Agreement reassures; disagreement is a
   diagnostic to investigate.
6. **Report P(H=L), zero-return rates, and trade counts by liquidity group.**
7. **Do not add a bias correction until the bias premise is supported in the target
   sample.**
8. **Separate measurement from prediction.** Feed the volatility series into HAR,
   GARCH or CARR models; do not call a historical measure "implied volatility."

Recommended 21-session reporting formula:

```
σ̂₂₁,ₜ = √[ A × (1/21) × Σⱼ₌₀²⁰ v̂ₜ₋ⱼ ]
```

where `v̂` is the chosen daily variance estimator and `A` the stated annual session
count. Report close-to-close volatility beside it, with the security's median trade
count and zero-range rate over the same window.

---

## What is deliberately absent

The archive records failed and superseded analyses, and they are **not** promoted into
results. Specifically excluded:

- the attempted **censored-normal** estimate of latent opening dispersion, which failed
  its post-April-2026 regime-change check;
- the earlier **multi-horizon convergence** result, invalidated by a stock-day bucket
  construction that stitched nonconsecutive sessions;
- alternative equity-classifier robustness rows and post-hoc confirmatory diagnostics
  for which the audit found no producing code.

Attractive findings that cannot be regenerated are treated as unavailable evidence.
`tests/test_audit_invariants.py` contains one regression test per defect the
2026-08-28 audit found — including several that reached committed results before being
caught.

---

## Limitations

The NEPSE benchmark is **not** true integrated variance. Without high-frequency data
or an options market, latent daily variance is unobserved; the matched open-to-close
squared return is a practical proxy, and Patton (2011) shows imperfect proxies affect
comparisons. The paper therefore reports whether downward bias is *detectable against
the available benchmark*, not that true latent variance is known. Institutional rules
— pre-open bands, price limits, no-match auction outcomes — are documented as
observable fingerprints rather than used to identify a latent uncensored distribution.
The India VIX exercise is a cross-market validation, not a Nepal-specific
implied-volatility comparison. The scope is measurement, not forecasting.

---

## Key references

Parkinson (1980) *J. Business* 53(1) 61–65 · Garman & Klass (1980) *J. Business* 53(1)
67–78 · Rogers & Satchell (1991) *Ann. Appl. Prob.* 1(4) 504–512 · Yang & Zhang (2000)
*J. Business* 73(3) 477–491 · Maheswaran & Kumar (2013) *Economic Modelling* 33
701–712 · Kumar & Maheswaran (2014) *Economic Modelling* 38 33–44 · Patton (2011)
*J. Econometrics* 160(1) 246–256

---

## Citation

```bibtex
@unpublished{giri2026volatility,
  author = {Giri, Anam},
  title  = {Calculating Volatility in Frontier Markets Without Options:
            Evidence and a Practical Framework from the Nepal Stock Exchange},
  year   = {2026},
  month  = {August},
  note   = {Draft research paper}
}
```

**Status.** Draft. The research remains exploratory unless a claim is explicitly
designated otherwise. Empirical quantities are drawn from the NEPSE volatility
research archive and its generated outputs; this revision retains only claims backed
by an explicit producer script, a generated table or figure, or a directly auditable
source artifact.

**Licence.** Not yet specified. Until a licence file is added, default copyright
applies and no reuse rights are granted.
