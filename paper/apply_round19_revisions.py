"""Round 19: the 9 October 2026 audit, the corrected forecast evaluation (plan M20) and the claims it changes.

    python paper/apply_round19_revisions.py [--base BASE.docx] [--out OUT.docx]

An independent audit of the package (``audits/2026-10-09_research_audit.md``; the response is
``RESEARCH_AUDIT_RESPONSE.md``) found three kinds of problem.

* **Four defects in the forecast evaluation of plans M16-M18** (``AUDIT-REGISTER.md`` M-028):
  * training outcomes crossed the holdout boundary;
  * targets stitched sessions across trading gaps;
  * zero targets were dropped;
  * the mean and its t statistic weighted forecast origins differently.

  Plan M20, frozen before any corrected loss was computed, removes them (``scripts/47``; tables 125-132),
  and adds return-only forecasts, ablations and a model confidence set. Its first run exposed
  floating-point residues of equal prices, which also inflate the frozen loss levels (M-033;
  ``scripts/51``, table 137).
* **Wording that went beyond the evidence** (M-029):
  * the QLIKE target described as unbiased for latent variance;
  * b·o described as the move the session keeps;
  * "genuine calibration";
  * "natural experiment" and "capping overreaction";
  * "no classical range estimator has significantly lower loss" as the main forecasting evidence.

  The calibration test's first-stage strength and weight floor were measured (M-030; ``scripts/49``,
  table 135).
* **Reproducibility statements and small factual errors** (M-031, M-032).

This round:

* rewrites the abstract, keywords, introduction, Sections 6.6-6.8, 7.1, 7.2, the Discussion, Section 9,
  the limitations (fourth, ninth, tenth, thirteenth, and a new seventeenth), the Conclusion, the data
  statements and Table 31's and Table 34's captions;
* keeps the plans' frozen results as their record and adds the corrected evaluation as Table 39;
* adds four references.

RULES ENFORCED HERE

* Every number is interpolated from a table, and every claim is asserted against the tables before it is
  written.
* The frozen M16-M18 figures stay in the text as the plans' record. The corrected evaluation is labelled
  as such wherever it is quoted.
* Edits replace text inside the single run that holds it, so no paragraph loses its formatting.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

import pandas as pd

try:
    import docx
except ImportError:
    sys.exit("python-docx is required:  pip install python-docx")

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from apply_referee_revisions import find, new_table_after, para_after, set_text  # noqa: E402
from apply_round4_revisions import set_repeat_header_row  # noqa: E402
from apply_round14_revisions import BANNED, ORDINALS, para_with, spacer_after, table_of  # noqa: E402
from apply_round15_revisions import NAME, SUBTITLE, TITLE, VARIANT, abstract_words  # noqa: E402
from apply_round16_revisions import edit  # noqa: E402

DOCX = ROOT / "paper" / "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"
ORD17 = ORDINALS + ["Sixteenth", "Seventeenth"]
CLASSICAL = ["P", "GK", "RS", "o2+P", "o2+GK", "YZ (daily form)"]
PRIMARY = {"NEPSE": "A2+C"}
FRONTIER = ["NEPSE", "DSE 2023-2026", "Vietnam 2007-2020", "DSE 2009-2021", "Morocco 2012-2026"]
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
         10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen"}

# Checked by web search, because the session's network could not reach Crossref (as for M-012 and
# M-019). The house style gives a DOI only where one was confirmed; Montiel Olea and Pflueger's was not.
REFS = [
    "Bollerslev, T. (1986). Generalized autoregressive conditional heteroskedasticity. Journal of "
    "Econometrics, 31(3), 307-327. https://doi.org/10.1016/0304-4076(86)90063-1",
    "Corsi, F. (2009). A simple approximate long-memory model of realized volatility. Journal of Financial "
    "Econometrics, 7(2), 174-196. https://doi.org/10.1093/jjfinec/nbp001",
    "Glosten, L. R., Jagannathan, R., & Runkle, D. E. (1993). On the relation between the expected value and "
    "the volatility of the nominal excess return on stocks. Journal of Finance, 48(5), 1779-1801. "
    "https://doi.org/10.1111/j.1540-6261.1993.tb05128.x",
    "Montiel Olea, J. L., & Pflueger, C. (2013). A robust test for weak instruments. Journal of Business & "
    "Economic Statistics, 31(3), 358-369.",
]


def primary(df: pd.DataFrame) -> pd.DataFrame:
    return df[df.apply(lambda r: r["span"] == PRIMARY.get(r["market"], "test half"), axis=1)]


def t2(v) -> str:
    return f"{float(v):+.2f}".replace("-", "−")


def load() -> dict:
    """Every figure this round quotes, read from the tables, with each claim asserted first."""
    n = {}
    v = pd.read_csv(TAB / "table126_m20_verdict_changes.csv")
    n["verdicts"], n["changed"] = len(v), int(v["changed"].sum())
    pv = primary(v)
    full_cls = pv[(pv.estimator == "Anam") & pv.rival.isin(CLASSICAL)]
    of_cls = pv[(pv.estimator == VARIANT) & pv.rival.isin(CLASSICAL)]
    assert len(full_cls) == len(of_cls)
    n["cls_n"] = len(full_cls)
    lost = full_cls[full_cls.verdict_corrected == "loses to"]
    assert len(lost) == 1 and (of_cls.verdict_corrected == "loses to").sum() == 0
    r = lost.iloc[0]
    assert (r.market, r.window, r.rival) == ("DSE 2023-2026", 5, "P")
    n["lost_t"] = t2(r.t_corrected)
    n["full_wins"] = int((full_cls.verdict_corrected == "beats").sum())
    n["of_wins"] = int((of_cls.verdict_corrected == "beats").sum())

    cl = pd.read_csv(TAB / "table129_m20_claims.csv")
    b3 = cl[cl.rule == "B3"]
    of_holm = b3[b3.detail.str.startswith(VARIANT)]
    full_holm = b3[b3.detail.str.startswith("Anam beats")]
    assert len(of_holm) == len(full_holm) == 7
    of_beats = set(of_holm[of_holm.verdict == "beats after Holm"].market)
    full_beats = set(full_holm[full_holm.verdict == "beats after Holm"].market)
    assert of_beats == {"DSE 2009-2021", "SP500", "Vietnam 2007-2020", "NIFTY50", "Morocco 2012-2026", "DSE 2023-2026"}
    assert full_beats == {"DSE 2009-2021", "SP500", "NIFTY50"}
    n["of_holm"], n["full_holm"] = WORDS[len(of_beats)], WORDS[len(full_beats)]

    b1 = cl[(cl.rule == "B1")]
    pb1 = primary(b1)
    adds = sorted(set(pb1[pb1.verdict == "range adds information"].market))
    suff = sorted(set(pb1[pb1.verdict == "returns suffice"].market))
    assert adds == ["DSE 2009-2021", "Morocco 2012-2026"] and suff == ["DSE 2023-2026"]
    assert (pb1.groupby("market").verdict.nunique() == 1).all(), "each sample's verdict is the same at both horizons"
    c_b1 = b1[(b1.market == "NEPSE") & (b1.span == "C")]
    assert set(c_b1.verdict) == {"returns suffice"}
    n["b1_adds"] = len(adds)

    m = primary(pd.read_csv(TAB / "table128_m20_mcs.csv"))
    cells = m.groupby(["market", "window"]).ngroups
    best = m.loc[m.groupby(["market", "window"])["loss"].idxmin(), "model"]
    n["cells"] = cells
    n["harof_best"] = int((best == "HAR-open-free").sum())
    inn = m.groupby("model")["in_mcs_90"].sum()
    assert inn["HAR-open-free"] == cells and inn["GJR"] == cells
    n["cc_mcs"] = int(inn["CC"])
    assert not (best == VARIANT).any(), "the open-free form never has the lowest loss of the seventeen"

    a = primary(pd.read_csv(TAB / "table130_m20_ablations.csv"))
    ab = lambda mdl, ref: a[(a.model == mdl) & (a.reference == ref)]
    full_of = ab("Anam", VARIANT)
    assert (full_of.verdict == "beats").sum() == 0
    n["of_over_full"] = int((full_of.verdict == "loses to").sum())
    assert set(full_of[full_of.verdict == "loses to"].market) <= set(FRONTIER)
    n["full_over_b1"] = int((ab("Anam", "o2+P").verdict == "beats").sum())
    n["post_loses"] = int((ab("Anam posterior (exploratory)", "Anam").verdict == "loses to").sum())
    n["har_cc"] = int((ab("HAR-CC", "CC").verdict == "beats").sum())
    assert (ab("P raw", "P").verdict == "beats").sum() == 0 and (ab("open-free raw", VARIANT).verdict == "beats").sum() == 0

    cov = pd.read_csv(TAB / "table131_m20_coverage.csv")
    low = cov[(cov.market == "Morocco 2012-2026") & (cov.window == 5) & (cov.liquidity == "low")].iloc[0]
    n["ma_low"] = f"{100 * low['eligible share']:.0f}%"

    s = pd.read_csv(TAB / "table135_audit_sensitivities.csv").set_index("statistic")["value"]
    n["F_conv"] = f"{s['first-stage F, conventional (instruments dated t-1 (primary))']:.0f}"
    n["F_eff1"] = f"{s['effective F, Montiel Olea-Pflueger, two-way (instruments dated t-1 (primary))']:.1f}"
    n["F_eff2"] = f"{s['effective F, Montiel Olea-Pflueger, two-way (instruments dated t-2)']:.1f}"
    assert float(n["F_eff1"]) < 23.1 < float(n["F_eff2"])

    rs = pd.read_csv(TAB / "table137_frozen_residue_check.csv")
    r5 = rs[rs.window == 5]
    infl = (r5.QLIKE_Anam_frozen - r5.QLIKE_Anam_zero)
    infl = infl[infl > 1e-9]
    n["infl_lo"], n["infl_hi"] = f"{infl.min():.2f}", f"{infl.max():.2f}"
    ch = rs[[c for c in rs.columns if c.endswith("_changed")]].any(axis=1)
    assert int(ch.sum()) == 1

    steps = pd.read_csv(TAB / "table124_theory_proof_steps.csv")
    assert bool(steps["pass"].all())
    n["steps"] = f"{len(steps)}"
    n["symbolic"] = f"{int(steps['method'].isin(['symbolic', 'symbolic-50dp']).sum())}"
    k = pd.read_csv(TAB / "table133_theory_kernel_checks.csv")
    assert bool(k["pass"].all())
    n["kchecks"] = f"{len(k)}"

    cal = pd.read_csv(TAB / "table78_calibration_full.csv").set_index("measure")
    assert cal.loc["P", "iv_slope_lo"] < 1 < cal.loc["P", "iv_slope_hi"]
    n["atten"] = f"{100 * (1 - cal.loc['P', 'iv_slope_lo']):.0f}%"
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(DOCX))
    ap.add_argument("--out", default=str(DOCX))
    a = ap.parse_args()
    n = load()
    doc = docx.Document(a.base)
    if any(p.text.startswith("Table 39.") for p in doc.paragraphs):
        sys.exit("round 19 has already been applied to this document")
    if not any(f"({n['steps']} steps" in p.text or "(251 steps, 138 of them symbolic" in p.text for p in doc.paragraphs):
        sys.exit("round 18 must be applied first")

    p = para_with(doc, "Data and reproducibility note.")
    edit(p, "through apply_round18_revisions.py)", "through apply_round19_revisions.py)")
    edit(p, "the forward India VIX test of Section 6.3 and the analyses of Sections 6.6 and 6.7 follow analysis plans "
            "frozen before their results existed",
         "the forward India VIX test of Section 6.3, the analyses of Sections 6.6 and 6.7 and the forecast "
         "evaluations of Section 6.8 (plans M16-M18 and the corrected plan M20) follow analysis plans frozen before "
         "their results existed")

    # ── abstract and keywords ────────────────────────────────────────────────────────────────
    edit(para_with(doc, "Design/methodology/approach:"),
         "Instrumented calibration slopes separate calibration from offsetting distortions, and NEPSE's 2026 widening "
         "of its pre-open band from ±2% to ±5% serves as a natural experiment. A new estimator, designed on NEPSE's "
         "first two rule regimes, is tested on its later regimes, two indices and stocks from Bangladesh, Vietnam and "
         "Morocco.",
         "Instrumented calibration slopes test for offsetting distortions, and an event study examines the 2026 rule "
         "package that widened NEPSE's pre-open band from ±2% to ±5%. A new estimator, designed on NEPSE's first two "
         "rule regimes, is tested on later regimes, two indices and stocks from Bangladesh, Vietnam and Morocco, and "
         "retested against return-only forecasts.")
    edit(para_with(doc, "Purpose:"), "what the bar's opening price contributes to it,", "what the opening price contributes,")
    p = para_with(doc, "Findings:")
    edit(p, "Range estimators are calibrated to the open-to-close proxy (Parkinson slope",
         "Unit calibration slopes against the open-to-close proxy are not rejected (Parkinson")
    edit(p, "and after the band widening the share surviving fell by", "and after the rule package the share surviving "
                                                                     "fell by")
    edit(p, "No classical range estimator forecasts significantly better than it in any test sample, but it does not beat "
            "close-to-close at short horizons in Nepal, Vietnam or recent Dhaka data, and both comparisons depend partly on "
            "the loss function. Its open-free form passed a prespecified test in Morocco.",
         f"After correction of the evaluation, its open-free form beats close-to-close at five sessions in {n['of_holm']} "
         f"of seven samples, but the best range-based forecast beats the best return-only one in only "
         f"{WORDS[n['b1_adds']]}, and comparisons with close-to-close depend partly on the loss function.")
    edit(para_with(doc, "Originality/value:"),
         "A market-design rule change altered what daily bars measure; an estimator built on that evidence is tested out "
         "of sample in four frontier markets.",
         "Opening-auction rule changes coincided with a change in what daily bars measure; an estimator built on that "
         "evidence is tested out of sample in four frontier markets.")
    edit(para_with(doc, "Keywords:"), "natural experiment;", "event study;")
    print("  abstract and keywords")

    # ── introduction ─────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "This paper asks five questions")
    edit(p, "and evidence, from a natural experiment in the exchange's own opening rules, on what the daily bar's opening "
            "price measures.",
         "and evidence, from a change in the exchange's own opening rules, on what the daily bar's opening price "
         "measures.")
    edit(p, "in Nepal, two benchmark indices and three other frontier markets.",
         "in Nepal, two benchmark indices and three other frontier markets, and retested against return-only forecasts "
         "after an independent audit corrected the forecast evaluation.")
    p = para_with(doc, "The fourth answer turns out to matter most.")
    edit(p, "When the exchange widened its pre-open price band on 20 April 2026, the share",
         "When the exchange widened its pre-open price band on 20 April 2026, in a package of rule changes made on the "
         "same date, the share")
    edit(p, "so the narrow band had been capping overreaction rather than delaying price discovery.",
         "which is consistent with the narrow band capping overreaction rather than delaying price discovery, although "
         "the band's separate effect is not identified.")
    edit(p, "The range estimators' agreement with the open-to-close proxy is genuine calibration, but calibration to a "
            "benchmark that shares the same error.",
         "A unit calibration slope of the range estimators on the open-to-close proxy is not rejected, under instruments "
         "whose validity is assumed, but that is calibration to a benchmark that shares the same error.")
    p = para_with(doc, "The fifth answer builds on the fourth.")
    edit(p, "Under the loss function the plans fixed, no classical range estimator has significantly lower loss than it in "
            "any of the seven test samples.",
         "Under the loss function the plans fixed, no classical range estimator had significantly lower loss than it in "
         "any of the seven test samples.")
    edit(p, "had the lowest five-session forecast loss in every frontier-market panel of the second plan",
         "had the lowest five-session forecast loss of the plans' nine estimators in every frontier-market panel of the "
         "second plan")
    edit(p, "and those with close-to-close dependent on the loss function (Table 37).",
         "and those with close-to-close dependent on the loss function (Table 37). An independent audit then found four "
         "defects in the plans' forecast evaluation, and a corrected evaluation, frozen before it was run, narrows the "
         f"record (Table 39). A classical range estimator now has significantly lower loss than the estimator in one of "
         f"{n['cls_n']} comparisons, and than its open-free form in none, and the open-free form beats close-to-close at "
         f"five sessions in {n['of_holm']} of the seven samples. But forecasts built from returns alone, GARCH-type "
         "models or a HAR model of squared returns, are about as accurate: the best range-based forecast beats the best "
         "of them only in the long Dhaka history and in Morocco.")
    print("  introduction")

    # ── Section 6.6 ──────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "Every comparison so far is a ratio of means")
    edit(p, "Lagged realised measures predict a session's variance but are uncorrelated with its measurement error, so "
            "they are valid instruments however strongly the estimators' same-day errors are correlated.",
         "Lagged realised measures predict a session's variance and, if measurement errors are not serially correlated, "
         "are uncorrelated with its measurement error; under that assumption, which persistence alone does not "
         "guarantee, they are valid instruments however strongly the estimators' same-day errors are correlated.")
    p = para_with(doc, "The near-unit ratios survive the test")
    edit(p, "and Parkinson's slope stays between 0.910 and 1.042 across the sensitivity specifications.",
         "and Parkinson's slope stays between 0.910 and 1.042 across the sensitivity specifications. Containing one is "
         f"not equivalence: Parkinson's interval allows attenuation of up to {n['atten']}. The instruments are also "
         f"weaker than the conventional first-stage statistic (F = {n['F_conv']}) suggests: with errors clustered by "
         f"security and date, the primary specification's effective F (Montiel Olea & Pflueger, 2013) is {n['F_eff1']}, "
         "below the threshold of 23.1 for a worst-case bias of 10%, while instruments dated two sessions back reach "
         f"{n['F_eff2']} (a post hoc check).")
    print("  Section 6.6")

    # ── Section 6.7 ──────────────────────────────────────────────────────────────────────────
    edit(para_with(doc, "NEPSE's opening price is mostly transient (Table 30)."),
         "the session undoes between 64% and 78% of the overnight move.",
         "the session undoes between 64% and 78% of the overnight move, in the sense of 1 - b, a projection pooled "
         "across securities and dates in which large opening moves weigh most.")
    print("  Section 6.7")

    # ── Section 6.8 ──────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "Sections 6.6 and 6.7 say what an estimator for this market needs.")
    edit(p, "b·o is then the part of the overnight move that the session keeps, and PC·exp(b o) the effective open.",
         "b·o is then a shrinkage predictor of the efficient overnight log move, the part of the overnight move the "
         "session is expected to keep given o, and PC·exp(b o) the anchor it implies, which we call the effective open.")
    edit(p, f"We refer to it as {NAME}.",
         f"We refer to it as {NAME}. The construction is a heuristic whose level the calibration sets: the squared "
         "shrinkage predictor understates the efficient overnight second moment unless the open's error is proportional "
         "to the move, and the extended range cannot remove an opening error that is already the day's high or low "
         "(theory supplement, Proposition 7).")
    p = para_with(doc, "The estimator was designed on NEPSE's first two rule regimes (A1 and B)")
    edit(p, "every estimator forecasts the mean squared close-to-close return over the next 5 or 21 sessions, a "
            "conditionally unbiased target, so ranking by expected QLIKE loss matches the ranking that the true variance "
            "would give (Patton, 2011).",
         "every estimator forecasts the mean squared close-to-close return over the next 5 or 21 sessions, and QLIKE "
         "loss ranks such forecasts as the conditional mean of that target would (Patton, 2011). That conditional mean is "
         "the second moment of observed close-to-close returns, not integrated variance: the comparison is between "
         "procedures for forecasting observed return variation.")
    edit(p, "loss differences are tested with Newey-West statistics on the per-date difference",
         "in the plans, loss differences were tested with Newey-West statistics on the per-date difference")
    p_frame = para_after(
        p,
        "The next three paragraphs report the plans' evaluation as frozen (Tables 34-38); the corrected evaluation "
        "follows them (Table 39). An independent audit of the package (9 October 2026) found four defects in the plans' "
        "evaluation: a training origin could have its outcome inside the test span, a target of 5 or 21 sessions could "
        "stitch sessions across a security's trading gaps, zero targets were dropped, and the reported mean difference "
        "weighted forecast origins differently from its t statistic. A further plan, M20, frozen before any corrected "
        "loss was computed, removes them; where the two disagree, the corrected evaluation is the record. In the "
        "Bangladeshi, Vietnamese and Moroccan panels the frozen loss levels also include targets that are "
        "floating-point residues of equal prices, which the plans meant to drop; they raise the full form's "
        f"five-session loss by {n['infl_lo']} to {n['infl_hi']} but change one frozen verdict (audit register M-033).",
        "Normal")
    assert p_frame is not None
    edit(para_with(doc, "Against the classical estimators the result is uniform under the plans' loss function."),
         "Against the classical estimators the result is uniform under the plans' loss function.",
         "In the plans' evaluation, the result against the classical estimators is uniform under their loss function.")
    edit(para_with(doc, "Against close-to-close the record is mixed, and frozen predictions failed."),
         "Against close-to-close the record is mixed, and frozen predictions failed.",
         "In the plans' evaluation, the record against close-to-close is mixed, and frozen predictions failed.")
    p = para_with(doc, "The open-free form was reported, but not decided on, in the first two plans.")
    new68 = [
        "The corrected evaluation (plan M20, script 47) keeps the plans' samples, horizons and estimators. A training "
        "origin is used only if its outcome ends before the test span begins; a target spans h consecutive exchange "
        "sessions and exists only if the security has a return on each; every candidate is scored with QLIKE in the "
        "form y/f + ln f, so that zero targets count, on one common sample; and inference uses the mean over "
        "stock-days, the quantity reported, with a standard error clustered by date and a Bartlett bandwidth of twice "
        "the horizon. It adds forecasts built from returns alone (an exponentially weighted average, variance-targeted "
        "GARCH(1,1) and GJR-GARCH(1,1) run in calendar time, and a HAR model of squared returns; Bollerslev, 1986; "
        "Glosten, Jagannathan & Runkle, 1993; Corsi, 2009), true-range Parkinson, a HAR model of the open-free kernel, "
        "and the model confidence set of Hansen, Lunde and Nason (2011) over all seventeen forecasts.",
        f"Before correcting anything, the script reproduces the frozen tables exactly. Of the {n['verdicts']} frozen "
        f"comparisons between the two forms and the other estimators, {n['changed']} then change verdict, most of them "
        "wins over a classical range estimator that are no longer significant. A classical range estimator now has "
        f"significantly lower loss than the full form in one of {n['cls_n']} comparisons on the primary test spans "
        f"(Parkinson in Dhaka 2023-2026 at five sessions, t = {n['lost_t']}) and than the open-free form in none. "
        f"Against close-to-close, the open-free form's five-session advantage survives a Holm adjustment across the seven "
        f"samples, fixed in the plan, in every sample except NEPSE, and the full form's in {n['full_holm']}: Dhaka "
        "2009-2021 and the two indices (Table 39). Close-to-close still beats both forms after NEPSE's reform.",
        "The return-only forecasts change the reading most. Taking the best return-only and the best range-based "
        "forecast by training loss, the range-based one has significantly lower test loss in Dhaka 2009-2021 and Morocco "
        "at both horizons, the return-only one in Dhaka 2023-2026 at both horizons and after NEPSE's reform, and neither "
        "elsewhere: on NEPSE's holdout, the indices and Vietnam the range added no detectable forecasting information "
        "beyond returns. The Moroccan verdict is fragile to how securities and dates are weighted. The most accurate "
        "single forecast pairs the open-free measure with HAR dynamics: it has the lowest test loss in "
        f"{WORDS[n['harof_best']]} of the {WORDS[n['cells']]} sample-horizon cells and is in every 90% model confidence "
        f"set, but so is GJR-GARCH, and close-to-close with the plans' shrinkage is in only {WORDS[n['cc_mcs']]}. Among "
        "the seventeen, the open-free form never has the lowest loss. Much of the gain over the plans' benchmark is the "
        f"dynamics: a HAR model of squared returns beats it in {WORDS[n['har_cc']]} of the {WORDS[n['cells']]} cells.",
        "Switching off one ingredient at a time locates what helps. Calibration does: no uncalibrated kernel beats its "
        "calibrated version. In the frontier panels, anchoring the range at the previous close and blending in 0.2 r² "
        "do. Estimating the open's coefficient does not: the full form never beats the open-free form and loses to it "
        f"in {WORDS[n['of_over_full']]} of the {WORDS[n['cells']]} cells, all in frontier panels, although it beats the "
        f"form that trusts the open fully (b = 1) in {WORDS[n['full_over_b1']]}. The overnight term with residual "
        "uncertainty that Proposition 7 of the theory supplement motivates does not improve on the frozen kernel, and "
        f"loses to it in {WORDS[n['post_loses']]} cells. The corrected comparison also covers fewer thin securities than the plans' did, because a target over "
        "sessions on which a security did not trade cannot be scored: in Morocco's least liquid tercile only "
        f"{n['ma_low']} of five-session origins have one.",
    ]
    anchor = p
    for text in new68:
        anchor = para_after(anchor, text, "Normal")
    print("  Section 6.8: the frozen record framed, the corrected evaluation added")

    # ── table captions ───────────────────────────────────────────────────────────────────────
    edit(para_with(doc, "Table 31. "), "The pre-open band reform as a natural experiment:",
         "The April 2026 rule package as an event:")
    edit(para_with(doc, "Table 34. "), "Plans M16-M18, frozen before testing (Section 6.8).",
         "Plans M16-M18, frozen before testing (Section 6.8). These are the plans' results, with the defects described in "
         "Section 6.8; Table 39 gives the corrected evaluation. In the Bangladeshi, Vietnamese and Moroccan panels the "
         "levels include targets that are floating-point residues of equal prices, which the plans meant to drop.")

    # ── Table 39, after Table 38 ─────────────────────────────────────────────────────────────
    doc.save(a.out)
    doc = docx.Document(a.out)
    anchor = spacer_after(table_of(doc, "Table 38."))
    t = pd.read_csv(TAB / "paper_table39_m20_corrected.csv", dtype=str).fillna("")
    cap = para_after(anchor, "Table 39. The corrected forecast evaluation (plan M20, frozen before it was run; script "
                             "47), on each test sample's primary span: the t of each form's loss minus close-to-close's "
                             "(negative favours the form; the mean over stock-days with a standard error clustered by "
                             "date), the Holm-adjusted one-sided p of 'beats close-to-close' across the seven samples, the "
                             "best return-only and range-based forecasts chosen on the training span with the t of their "
                             "test-loss difference, the lowest test loss of the seventeen forecasts, and membership of the "
                             "90% model confidence set.", "Normal")
    new_t = new_table_after(cap, doc, list(t.columns), t.values.tolist())
    set_repeat_header_row(new_t)
    spacer_after(new_t)
    print("  added Table 39")

    # ── Section 7 ────────────────────────────────────────────────────────────────────────────
    edit(para_with(doc, f"In NEPSE neither form of {NAME} (Section 6.8)"),
         "use the estimator's open-free form where the open's unbiasedness coefficient is well below one, as in every "
         "frontier market examined here, and its full form where the open is close to unbiased; its level is on the "
         "close-to-close scale by construction of its calibration.",
         "use the estimator's open-free form where the open's unbiasedness coefficient is well below one, as in every "
         "frontier market examined here; its level is on the close-to-close scale by construction of its calibration. "
         "For forecasting, give it HAR-type dynamics and report a GARCH-type forecast of returns beside it, which the "
         "corrected evaluation found about as accurate in most samples.")
    edit(para_with(doc, "where v̂ is the chosen daily variance estimator"),
         f"{NAME} fits the same form, with v̂ = κA, and needs no further adjustment of level, because κ already sets it",
         f"{NAME} fits the same form, with v̂ₜ₋ⱼ = κₜAₜ₋ⱼ, the calibration of the window's last session applied to every "
         "session in it, and needs no further adjustment of level, because κₜ already sets it")
    p = para_with(doc, "The evidence in this project does not support a single ranking")
    edit(p, "and higher than the 1.288 obtained by matching rows alone.",
         "and slightly lower than the 1.288 obtained by matching rows alone.")
    edit(p, f"and under it no classical range estimator has significantly lower loss than {NAME} in any market tested; even "
            "so it yields no universal ordering, because close-to-close is not beaten everywhere and the comparison with "
            "it changes under a different loss function.",
         f"and under it, in the corrected evaluation, a classical range estimator has significantly lower loss than {NAME} "
         f"in one comparison of {n['cls_n']}; even so it yields no universal ordering, because close-to-close is not "
         "beaten everywhere, forecasts built from returns alone are about as accurate in most samples, and the "
         "comparison with close-to-close changes under a different loss function.")
    print("  Sections 7.1-7.2")

    # ── Discussion ───────────────────────────────────────────────────────────────────────────
    edit(para_with(doc, "The opening price is the second main result"),
         "which Section 6.6 shows to be calibration rather than cancellation,",
         "which Section 6.6 finds consistent with calibration rather than cancellation,")
    edit(para_with(doc, "The band reform adds a market-design reading."),
         "Widening it let transient opening moves grow, and a stock",
         "After the package that widened it, transient opening moves grew, and a stock")
    p = para_with(doc, "The estimator of Section 6.8 is the constructive side of these findings")
    edit(p, "the range can add information that close-to-close alone does not have: under the plans' loss no classical "
            "range estimator had significantly lower loss than the estimator anywhere, and it beat close-to-close in the "
            "long Dhaka history, on the indices, as the classical range estimators also did there, and, less securely, in "
            "Morocco. That the open-free form had the lowest five-session loss of all nine estimators in Bangladesh, Vietnam "
            "and Morocco suggests something simpler:",
         "the range can add information that close-to-close alone does not have, but the corrected evaluation shows how "
         "much depends on the comparison. Against close-to-close with the plans' simple shrinkage, the open-free form wins "
         f"at five sessions in {n['of_holm']} of seven samples; against GARCH-type and HAR forecasts of returns, a "
         "range-based forecast wins only in the long Dhaka history and in Morocco, and loses in recent Dhaka data. That "
         "the open-free form beats the full form wherever the open is unreliable, and that the full form never beats it, "
         "suggests something simpler:")
    edit(p, "Close-to-close was not beaten at short horizons in the primary panels of three of the four frontier markets, it "
            "beat both forms immediately after NEPSE's rule change, which is when a regulator or a risk manager most needs "
            "a reliable number, and the comparison with it turns on the loss function.",
         "Close-to-close beat both forms immediately after NEPSE's rule change, which is when a regulator or a risk manager "
         "most needs a reliable number, forecasts built from returns alone matched the range-based forecasts in most "
         "samples, and the comparison with close-to-close turns on the loss function.")
    print("  Discussion")

    # ── Section 9 ────────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "The estimator of Section 6.8 was developed and tested under three further frozen plans")
    edit(p, "six propositions with proofs, derived after the plans above were run.",
         "seven propositions with proofs, derived after the plans above were run, the seventh after the audit described "
         "below.")
    edit(p, "(251 steps, 138 of them symbolic, all passing).",
         f"({n['steps']} steps, {n['symbolic']} of them symbolic, all passing). Script 48 checks the seventh "
         f"proposition, on how much of the opening error each kernel absorbs ({n['kchecks']} checks, all passing).")
    para_after(
        p,
        "An independent audit of the package (9 October 2026) found four defects in the forecast evaluation of plans "
        "M16-M18, statements that went beyond the evidence, and gaps in the reproducibility statements. The evaluation "
        "was corrected under plan M20, frozen before it was run (script 47; Section 6.8 and Table 39). Its first run "
        "exposed floating-point residues of equal prices, which also inflate the frozen loss levels (post hoc, script "
        "51). The calibration's weight floor and first-stage strength were measured (post hoc, script 49), and every "
        "correction is registered (audit register M-028 to M-034). A prospective test is frozen as plan M21: every "
        "forecast's parameters are fixed on the current data (script 50) and will be scored, unchanged, on sessions "
        "after 9 October 2026. The package reproduces every result on the NEPSE panels and the two indices; the "
        "Bangladeshi, Vietnamese and Moroccan results need third-party files that it documents and pins by digest but "
        "does not distribute, and a run without them reports itself as partial.",
        "Normal")
    print("  Section 9")

    # ── limitations ──────────────────────────────────────────────────────────────────────────
    edit(para_with(doc, "Fourth, the external India VIX exercise"),
         "Neither establishes that a NEPSE volatility estimate would forecast NEPSE volatility, because Nepal has no options "
         "market against which such a test could be run — which is the paper's motivating problem, not a gap in its "
         "execution.",
         "Neither establishes that a NEPSE volatility estimate would track NEPSE's implied volatility, because Nepal has no "
         "options market against which such a test could be run; Section 6.8 tests forecasts of NEPSE's realised return "
         "variation instead, which needs no options.")
    edit(para_with(doc, "Ninth, the intervals reported here"),
         "They do not model the measurement error in the proxy itself, so they should be read as a lower bound on total "
         "uncertainty rather than as a complete accounting of it.",
         "They quantify sampling uncertainty for the stated observable statistics; they do not model the measurement error "
         "in the proxy, and so say nothing about uncertainty concerning latent variance.")
    edit(para_with(doc, "Tenth, on data provenance."),
         "A reader can therefore reproduce every reported result from the frozen panels, and can repeat the rebuild only "
         "with independent access to the sources.",
         "A reader can therefore reproduce every NEPSE and index result from the frozen panels, and can repeat the rebuild "
         "only with independent access to the sources; the Bangladeshi, Vietnamese and Moroccan results of Section 6.8 need "
         "third-party files that the package documents and pins by digest but does not distribute.")
    edit(para_with(doc, "Thirteenth, the calibration slopes of Section 6.6"),
         "They establish calibration relative to the proxy, not accuracy relative to latent variance.",
         "They are evidence about calibration relative to the proxy, not about accuracy relative to latent variance, and "
         "their identification assumes that the lagged instruments are uncorrelated with the measurement error. With "
         "errors clustered by security and date, the primary specification's instruments are weak by the Montiel "
         f"Olea-Pflueger criterion (effective F {n['F_eff1']}), though those dated two sessions back are not "
         f"({n['F_eff2']}), a post hoc check.")
    p16 = para_with(doc, "Sixteenth, the estimator's record against close-to-close")
    para_after(
        p16,
        "Seventeenth, the forecast evaluation of the three plans had defects that an audit found after their results "
        "were known, and the corrected evaluation that replaces it was designed after the audit had reported some of "
        "their effects. It covers fewer thin securities, because a target over sessions on which a security did not "
        "trade cannot be scored, and some of its verdicts, Morocco's in particular, depend on how securities and dates "
        "are weighted. Only the prospective test of plan M21, on sessions that did not exist when its parameters were "
        "fixed, is free of that history.",
        "Normal")
    print("  limitations: fourth, ninth, tenth, thirteenth, and a seventeenth")

    # ── Conclusion ───────────────────────────────────────────────────────────────────────────
    edit(para_with(doc, "The paper's second finding qualifies its first."),
         "A natural experiment analysed under a frozen plan ties part of this to market design. Widening the pre-open band "
         "from ±2% to ±5% produced a sharp break in how much of the open survives to the close,",
         "An event study under a frozen plan links part of this to market design: the rule package that widened the "
         "pre-open band from ±2% to ±5% coincided with a sharp break in how much of the open survives to the close,")
    p = para_with(doc, "The third finding is constructive, and narrower than it first looks.")
    edit(p, "under the loss function the plans fixed.",
         "under the loss function the plans fixed; in a corrected evaluation one such comparison in "
         f"{n['cls_n']} goes against it and none against its open-free form, but forecasts built from returns alone match "
         f"or beat the best range-based forecast in {WORDS[7 - n['b1_adds']]} of the seven samples.")
    edit(p, "It did not beat close-to-close at short horizons in the primary panels of three of the four frontier markets,",
         "Its full form did not beat close-to-close at short horizons in the primary panel of any of the four frontier "
         "markets once the evaluation was corrected,")
    edit(para_with(doc, "The claims should stop there"),
         "a test that separates calibration from offsetting distortions, evidence that the market's opening rules shape "
         "what its daily bars measure, and an estimator built on that evidence and tested out of sample under frozen plans.",
         "a test of calibration against offsetting distortions, evidence that a change in the market's opening rules "
         "coincided with a change in what its daily bars measure, and an estimator built on that evidence, tested out of "
         "sample under frozen plans and retested after an audit corrected their evaluation.")
    print("  Conclusion")

    # ── Declarations ─────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "Data availability statement:")
    edit(p, "The processed data supporting this study's findings, together with",
         "The processed data supporting this study's NEPSE and index findings, together with")
    edit(p, "the package documents their sources and pins each by its SHA-256 digest.",
         "the package documents their sources and pins each by its SHA-256 digest, and a run without them reproduces the "
         "NEPSE and index results and reports itself as partial.")

    # ── References, kept alphabetical ────────────────────────────────────────────────────────
    paras = list(doc.paragraphs)
    first = find(paras, "Alizadeh, S., Brandt, M. W.")
    j = next(k for k, q in enumerate(paras) if q.text.startswith("Data and reproducibility note"))
    last = max(k for k in range(first, j) if paras[k].text.strip())
    existing = [paras[i].text.strip() for i in range(first, last + 1) if paras[i].text.strip()]
    assert not (set(existing) & set(REFS)), "a reference is already listed"
    merged = sorted(set(existing) | set(REFS), key=lambda r: re.sub(r"^(The )", "", r).lower())
    slots = [i for i in range(first, last + 1) if paras[i].text.strip()]
    for kk, ref in enumerate(merged[:len(slots)]):
        set_text(paras[slots[kk]], ref)
    p_last = paras[slots[-1]]
    for ref in merged[len(slots):]:
        p_last = para_after(p_last, ref, "Normal")
    print(f"  reference list now {len(merged)} entries, alphabetical")

    doc.save(a.out)
    verify(a.out, n)


def verify(path, n) -> None:
    doc = docx.Document(path)
    paras = list(doc.paragraphs)
    body = "\n".join(p.text for p in paras)
    low = body.lower()
    bad = {k: v for k, v in BANNED.items() if k in low}
    assert not bad, f"banned phrases present: {bad}"
    assert paras[0].text == TITLE and paras[1].text == SUBTITLE
    assert len(doc.tables) == 39, f"expected 39 tables, found {len(doc.tables)}"
    assert len(doc.inline_shapes) == 8, f"expected 8 figures, found {len(doc.inline_shapes)}"
    words = abstract_words(doc)
    assert words <= 255, f"abstract has {words} words"
    findings = next(p.text for p in paras if p.text.startswith("Findings:"))
    assert "NIFTY" not in findings and NAME in findings and "depend partly on the loss function" in findings
    for gone in ("natural experiment;", "as a natural experiment", "A natural experiment analysed", "genuine calibration",
                 "had been capping overreaction", "a conditionally unbiased target", "matches the ranking that the true "
                 "variance would give", "the part of the overnight move that the session keeps", "lower bound on total "
                 "uncertainty", "can therefore reproduce every reported result", "higher than the 1.288", "v̂ = κA",
                 "shows to be calibration rather than cancellation", "Widening it let transient opening moves grow",
                 "no classical range estimator has significantly lower loss than it in any",
                 "in the primary panels of three of the four frontier markets"):
        assert gone not in body, f"corrected wording survives round 19: {gone!r}"
    for needle in ("Table 39.", "Seventeenth,", "plan M20", "plan M21", "apply_round19_revisions.py",
                   f"({n['steps']} steps, {n['symbolic']} of them symbolic, all passing)",
                   f"effective F (Montiel Olea & Pflueger, 2013) is {n['F_eff1']}", "so close-to-close remains the primary "
                   "measure here", "the failed predictions are reported as failures", "the calibration's doing",
                   "Proposition 7", f"t = {n['lost_t']}"):
        assert needle in body, f"missing after round 19: {needle!r}"
    for sentence in re.split(r"(?<=[.!?])\s+", body):
        if "MSE" in sentence or "Holm" in sentence:
            assert ("post hoc" in sentence.lower() or "Table 37" in sentence or "Tables 37 and 38" in sentence
                    or "Table 39" in sentence or "plan M20" in sentence), sentence[:100]
    i = find(paras, "Several limitations")
    j = find(paras, "11. Conclusion", i)
    found = [p.text.split(",")[0] for p in paras[i + 1:j] if p.text.split(",")[0] in ORD17]
    assert found == ORD17[1:len(found) + 1] and found[-1] == "Seventeenth", f"limitation ordinals: {found}"
    refs_i = paras.index(next(p for p in paras if p.text == "References"))
    refs_j = next(k for k, p in enumerate(paras) if p.text.startswith("Data and reproducibility note"))
    refs = [p.text for p in paras[refs_i + 1:refs_j] if p.text.strip()]
    keys = [re.sub(r"^(The )", "", r).lower() for r in refs]
    assert keys == sorted(keys), "references must stay alphabetical"
    for r in REFS:
        assert r in refs, r[:40]
    t = pd.read_csv(TAB / "paper_table39_m20_corrected.csv", dtype=str).fillna("")
    cells = [[c.text for c in row.cells] for row in doc.tables[38].rows]
    assert cells[0] == list(t.columns) and cells[1:] == t.values.tolist(), "Table 39 must be the paper table"
    print(f"verification: {len(doc.tables)} tables, {len(doc.inline_shapes)} figures, abstract {words} words; the "
          "audit's corrections are in, the frozen record is labelled, Table 39 is the corrected evaluation")


if __name__ == "__main__":
    main()
