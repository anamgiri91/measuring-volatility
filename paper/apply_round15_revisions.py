"""Round 15: Anam's estimator (plans M16-M18) moves into the manuscript.

    python paper/apply_round15_revisions.py [--base BASE.docx] [--out OUT.docx]

The estimator was designed on NEPSE regimes A1 and B and evaluated under three plans frozen and
committed before their results existed: ``M16_ANAM_ESTIMATOR_PLAN.md`` (NEPSE's later regimes, the
NIFTY 50 and the S&P 500), ``M17_ANAM_FRONTIER_PLAN.md`` (Bangladesh and Vietnam) and
``M18_ANAM_MOROCCO_PLAN.md`` (Morocco, with the open-free form as a hypothesis fixed in advance).
This script adds Section 6.8 and Tables 33-36 and makes the changes they force in the title,
abstract, introduction, protocol, discussion, reproducibility statement, limitations, conclusion,
declarations and references.

RULES ENFORCED HERE
  * Every number is interpolated from a frozen table; nothing is typed. Every summary claim the text
    makes ("no classical range estimator beats it in any test sample", "within x% of close-to-close")
    is asserted against the tables before it is written.
  * Frozen verdicts are quoted from the decision ledgers (table105, table111, table116), never
    re-derived; failed predictions are reported as failed (M16 H1-H3; M17 F1 in both primary panels
    and G).
  * The open-free form's M16-M17 record was read after those verdicts and is labelled post hoc
    wherever it is quoted; only M18 tested it under a frozen rule.
  * Antecedents are credited and nothing is claimed as first: Parkinson (1980), Yang and Zhang (2000),
    Wilder (1978) for the true range, Hansen and Lunde (2005) for scaling a partial measure to the
    whole day; the forecast comparison follows Patton (2011), Diebold and Mariano (1995) and Newey and
    West (1987).
  * The estimator is named "Anam's estimator" here; paper/build_submission_set.py replaces the name
    in the anonymous copy, because it is the author's own.
  * The round-14 rules still bind: BANNED phrases, NIFTY 50 compared only as an index (M-014), the
    M13 statements, the 255-word abstract cap.
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
sys.path.insert(0, str(ROOT / "src"))
from apply_referee_revisions import find, new_table_after, para_after, set_text  # noqa: E402
from apply_round4_revisions import set_repeat_header_row  # noqa: E402
from apply_round14_revisions import (BANNED, ORDINALS, para_with, renumber_limitations,  # noqa: E402
                                     replace_in, spacer_after, table_of)
from nepsevol.estimators import anam as AN  # noqa: E402

DOCX = ROOT / "paper" / "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"

TITLE = "When the Open Overreacts: Measuring Daily Volatility in Frontier Markets without Options"
SUBTITLE = "Evidence from Nepal's Pre-Open Band Reform and an Estimator Tested in Four Frontier Markets"
NAME = "Anam's estimator"
VARIANT = "Anam, open-free special case (b=0)"
RANGE = ["P", "GK", "RS", "o2+P", "o2+GK", "YZ (daily form)"]

# Checked against indexing records found by web search (AUDIT-REGISTER M-019). The house style gives a
# DOI only where one was confirmed: Newey and West's is; Diebold and Mariano's and Hansen and Lunde's
# were not, and are given without one.
REFS = [
    "Diebold, F. X., & Mariano, R. S. (1995). Comparing predictive accuracy. Journal of Business & "
    "Economic Statistics, 13(3), 253-263.",
    "Hansen, P. R., & Lunde, A. (2005). A realized variance for the whole day based on intermittent "
    "high-frequency data. Journal of Financial Econometrics, 3(4), 525-554.",
    "Newey, W. K., & West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and "
    "autocorrelation consistent covariance matrix. Econometrica, 55(3), 703-708. "
    "https://doi.org/10.2307/1913610",
    "Wilder, J. W. (1978). New concepts in technical trading systems. Trend Research.",
]


# ─────────────────────────────────────────────────────────────────── numbers from the package

def f3(v) -> str:
    return f"{float(v):.3f}"


def f4(v) -> str:
    return f"{float(v):.4f}"


def tt(v) -> str:
    """A t statistic as the text prints it: signed, two decimals, U+2212 for minus."""
    return f"{float(v):+.2f}".replace("-", "−")


def load() -> dict:
    n: dict = {}
    f101 = pd.read_csv(TAB / "table101_anam_holdout_forecast.csv")
    f108 = pd.read_csv(TAB / "table108_anam_frontier_forecast.csv")
    f113 = pd.read_csv(TAB / "table113_anam_morocco_forecast.csv")

    def g(fr, market, span, win):
        return fr[(fr.market == market) & (fr.test_span == span) & (fr.window == win)].set_index("estimator")

    samples = {"NEPSE": (f101, "NEPSE", "A2+C"), "NIFTY": (f101, "NIFTY50", "test half"),
               "SP": (f101, "SP500", "test half"), "D23": (f108, "DSE 2023-2026", "test half"),
               "VN": (f108, "Vietnam 2007-2020", "test half"), "D09": (f108, "DSE 2009-2021", "test half"),
               "MA": (f113, "Morocco 2012-2026", "test half")}
    frontier = ["NEPSE", "D23", "VN", "D09", "MA"]
    for k, (fr, mk, sp) in samples.items():
        for w in (5, 21):
            t = g(fr, mk, sp, w)
            n[f"{k}{w}_anam"], n[f"{k}{w}_cc"] = f4(t.loc["Anam", "QLIKE"]), f4(t.loc["CC", "QLIKE"])
            n[f"{k}{w}_of"] = f4(t.loc[VARIANT, "QLIKE"])
            n[f"{k}{w}_t"] = tt(t.loc["Anam", "t_vs_CC"])
            n[f"{k}{w}_of_t"] = tt(t.loc[VARIANT, "t_vs_CC"])
            n[f"{k}{w}_tP"] = tt(t.loc["Anam", "t_vs_P"])
            n[f"{k}{w}_P"] = f4(t.loc["P", "QLIKE"])
            n[f"_{k}{w}"] = t
    # the regime-C split of the NEPSE holdout, and A2 alone
    for w in (5, 21):
        c = g(f101, "NEPSE", "C", w)
        n[f"C{w}_t"], n[f"C{w}_of_t"] = tt(c.loc["Anam", "t_vs_CC"]), tt(c.loc[VARIANT, "t_vs_CC"])
        assert c.loc["Anam", "t_vs_CC"] > 1.96, "the text says close-to-close beats it in regime C"
        assert c.loc[VARIANT, "t_vs_CC"] > 1.96 or w == 21, "the text says close-to-close beats the open-free form in C"
        assert c.loc[VARIANT, "QLIKE"] < c.loc["Anam", "QLIKE"], "open-free form above the full form in C"
        a2 = g(f101, "NEPSE", "A2", w)
        assert a2.loc[VARIANT, "QLIKE"] < a2.loc["Anam", "QLIKE"], "open-free form above the full form in A2"
    assert n["_VN21"].loc["Anam", "t_vs_CC"] > 1.96, "the text says close-to-close beats it in Vietnam at 21"
    # Morocco: the open-free form against the full estimator
    m5 = n["_MA5"]
    # row "Anam", reference the open-free form: t of (full minus open-free); the text quotes open-free minus full
    n["MA5_of_vs_anam_t"] = tt(-m5.loc["Anam", f"t_vs_{VARIANT}"])
    assert m5.loc["Anam", f"t_vs_{VARIANT}"] > 1.96, "the text says the open-free form beats the full one in Morocco"

    # ledgers: who beats whom, and the verdicts quoted
    d105 = pd.read_csv(TAB / "table105_anam_holdout_decisions.csv")
    d111 = pd.read_csv(TAB / "table111_anam_frontier_decisions.csv")
    d116 = pd.read_csv(TAB / "table116_anam_morocco_decisions.csv")
    riv = pd.concat([
        d105[d105.rule == "rival"].assign(rv=lambda x: x.rival, v=lambda x: x.verdict.str.split().str[1]),
        d111[d111.rule == "rival"].assign(rv=lambda x: x.rival, v=lambda x: x.verdict.str.split().str[1]),
        d116[(d116.rule == "rival") & (d116.estimator == "Anam")].assign(rv=lambda x: x.rival, v=lambda x: x.verdict.str.split().str[0]),
    ])
    # "No classical range estimator beats it in any test sample at either horizon"
    assert not ((riv.rv.isin(RANGE)) & (riv.v == "loses")).any(), "a range estimator beats Anam somewhere"
    # "in every frontier-market sample it beats all six at five sessions"
    fr5 = riv[(riv.window == 5) & riv.rv.isin(RANGE) & (riv.span.isin(["A2+C", "test half"]))
              & riv.market.isin(["NEPSE", "DSE 2023-2026", "Vietnam 2007-2020", "DSE 2009-2021", "Morocco 2012-2026"])]
    assert (fr5.v == "beats").all() and len(fr5) == 6 * 5, "the text says it beats all six at 5 in every frontier sample"
    led = {}
    for r in d105[d105.rule != "rival"].itertuples():
        led[("M16", r.rule, r.market)] = r.verdict
    for r in d111[d111.rule != "rival"].itertuples():
        led[("M17", r.rule, r.market)] = r.verdict
    for r in d116[d116.rule != "rival"].itertuples():
        led[("M18", r.rule)] = r.verdict
    assert [led[("M16", h, "NEPSE")] for h in ("H1", "H2", "H3")] == ["does not hold"] * 3
    assert led[("M16", "H4", "NIFTY50")] == led[("M16", "H5", "SP500")] == "holds"
    assert led[("M17", "F1", "DSE 2023-2026")] == led[("M17", "F1", "Vietnam 2007-2020")] == "does not hold"
    assert led[("M17", "G", "DSE 2023-2026 + Vietnam 2007-2020")] == "does not hold"
    assert all(led[("M18", r)] in ("holds", "yes") for r in ("F1", "F2", "F3", "best in panel", "V1", "V2", "V3", "O"))
    n["ledger"] = led

    # levels
    lv = pd.concat([pd.read_csv(TAB / "table102_anam_holdout_level.csv"),
                    pd.read_csv(TAB / "table109_anam_frontier_level.csv"),
                    pd.read_csv(TAB / "table114_anam_morocco_level.csv")])
    lv = lv[lv.span.isin(["A2", "C", "test half"])]
    cal = lv[lv.estimator == "Anam (calibrated)"].set_index(["market", "span"])["ratio_to_close_to_close"]
    stable = cal.drop(("NEPSE", "C"))
    n["lev_dev"] = f"{100 * (stable - 1).abs().max():.1f}"
    n["lev_C"] = f3(cal[("NEPSE", "C")])
    classical = lv[lv.estimator.isin(RANGE + ["YZ (window form)"])
                   & ~((lv.market == "NEPSE") & (lv.span == "C"))]
    n["over_max"] = f"{100 * (classical.ratio_to_close_to_close.max() - 1):.0f}"
    n["under_max"] = f"{100 * (1 - classical.ratio_to_close_to_close.min()):.0f}"
    lvl = lv.set_index(["market", "span", "estimator"])["ratio_to_close_to_close"]
    n["yz_D23"] = f3(lvl[("DSE 2023-2026", "test half", "YZ (daily form)")])
    n["gk_MA"], n["p_MA"] = f3(lvl[("Morocco 2012-2026", "test half", "GK")]), f3(lvl[("Morocco 2012-2026", "test half", "P")])

    # open quality on the new samples (pooled, security level), and NEPSE's by regime (M15)
    p107 = pd.read_csv(TAB / "table107_anam_frontier_panels.csv").set_index("panel")["b median (test span)"]
    p112 = pd.read_csv(TAB / "table112_anam_morocco_panel.csv").iloc[0]["b median (test span)"]
    bs = list(p107.values) + [p112]
    n["b_new_lo"], n["b_new_hi"] = f"{min(bs):.2f}", f"{max(bs):.2f}"
    u = pd.read_csv(TAB / "table89_m15_unbiasedness.csv")
    bn = u[(u.group == "all") & u.statistic.str.startswith("unbiasedness")].value
    n["b_nepse_lo"], n["b_nepse_hi"] = f3(bn.min()), f3(bn.max())

    # the open-free form, read after the M16-M17 verdicts (post hoc) and tested in M18
    for k in frontier:
        for w in (5, 21):
            t = n[f"_{k}{w}"]
            assert t.loc[VARIANT, "QLIKE"] < t.loc["Anam", "QLIKE"], (k, w, "open-free form above the full form")
    dev = pd.read_csv(TAB / "table98_anam_dev_forecast.csv")
    dev = dev[dev.calibration == f"pool{AN.POOL_SESSIONS}"].set_index(["window", "train", "estimator"])["QLIKE"]
    for w in (5, 21):
        for trn in ("A1", "B"):
            assert dev[(w, trn, VARIANT)] < dev[(w, trn, "Anam")], ("development", w, trn)
    for k in ("D23", "VN", "D09", "MA"):
        t = n[f"_{k}5"]
        assert t["QLIKE"].idxmin() == VARIANT, (k, "open-free form not lowest at 5")
        assert t.loc[VARIANT, "t_vs_CC"] < -1.96, (k, "open-free form does not beat CC at 5")
    for k in ("NIFTY", "SP"):
        for w in (5, 21):
            t = n[f"_{k}{w}"]
            assert t.loc[VARIANT, "QLIKE"] > t.loc["Anam", "QLIKE"] and abs(t.loc[VARIANT, "t_vs_Anam"]) < 1.96, (k, w)
    assert n["_MA21"]["QLIKE"].idxmin() == VARIANT

    # post hoc Y1: a faster calibration in regime C
    y1 = pd.read_csv(TAB / "table106_anam_posthoc_calibration.csv")
    y = y1[(y1.span == "C") & (y1.window == 5)].set_index("estimator")
    n["y1_60"], n["y1_10"] = f4(y.loc["Anam, calibration 60 dates", "QLIKE"]), f4(y.loc["Anam, calibration 10 dates", "QLIKE"])
    n["y1_cc"], n["y1_t10"] = f4(y.loc["CC", "QLIKE"]), tt(y.loc["Anam, calibration 10 dates", "t_vs_CC"])
    assert abs(y.loc["Anam, calibration 10 dates", "t_vs_CC"]) < 1.96
    n["pool"], n["lam"] = AN.POOL_SESSIONS, AN.LAMBDA0
    return n


# ─────────────────────────────────────────────────────────────────── docx utilities

def set_body(p, text: str) -> None:
    """Replace the body of a labelled paragraph (a bold label run, then the body), keeping the label."""
    assert len(p.runs) >= 2, f"not a labelled paragraph: {p.text[:50]!r}"
    p.runs[1].text = text
    for r in p.runs[2:]:
        r.text = ""


def abstract_words(doc) -> int:
    ps = doc.paragraphs
    i = next(k for k, p in enumerate(ps) if p.text.strip() == "Abstract")
    return sum(len(p.text.split()) for p in ps[i + 1:i + 5])


# ─────────────────────────────────────────────────────────────────── the revision

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(DOCX))
    ap.add_argument("--out", default=str(DOCX))
    a = ap.parse_args()
    n = load()
    doc = docx.Document(a.base)
    if any(p.text.startswith("6.8 ") for p in doc.paragraphs):
        sys.exit("round 15 has already been applied to this document")

    # ── title and front matter ───────────────────────────────────────────────────────────────
    paras = list(doc.paragraphs)
    set_text(paras[0], TITLE)
    set_text(paras[1], SUBTITLE)
    p = para_with(doc, "Data and reproducibility note.")
    replace_in(p, "through apply_round14_revisions.py)", "through apply_round15_revisions.py)")

    # ── abstract (255-word cap, labels included) ─────────────────────────────────────────────
    p = para_with(doc, "Purpose: ")
    set_body(p, "Nepal has no exchange-traded options and no public intraday data, so volatility must be "
                "measured from the daily open-high-low-close bar. This paper asks how reliable that "
                "measurement is, what the bar's opening price contributes to it, and how an estimator "
                "should treat an overreacting open.")
    p = para_with(doc, "Design/methodology/approach: ")
    sample = re.search(r"\d[\d,]* ordinary-equity stock-days \([^)]*\)", p.text).group(0)
    set_body(p, f"Six estimators are evaluated on {sample} against matched proxies. Instrumented "
                "calibration slopes separate calibration from offsetting distortions, and NEPSE's 2026 "
                "widening of its pre-open band from ±2% to ±5% serves as a natural experiment. A new "
                "estimator, designed on NEPSE's first two rule regimes, is tested on its later regimes, "
                "two indices and stocks from Bangladesh, Vietnam and Morocco. Every analysis "
                "follows a plan frozen before testing.")
    p = para_with(doc, "Findings: ")
    old = p.text
    slope = re.search(r"Parkinson slope \d\.\d{3} \[\d\.\d{3}, \d\.\d{3}\]", old).group(0)
    undo = re.search(r"undoes \d+-\d+% of the overnight move", old).group(0)
    fell = re.search(r"fell by \d\.\d{3}, more than at any of \d+ placebo dates", old).group(0)
    set_body(p, f"Range estimators are calibrated to the open-to-close proxy ({slope}), but the open is "
                f"mostly transient: the session {undo}, and after the band widening the share surviving "
                f"{fell}. {NAME} weights the overnight move by the open's measured "
                "reliability and calibrates to close-to-close variance. No classical range estimator beats "
                f"it in any test sample, and its level is within {n['lev_dev']}% of close-to-close outside "
                "NEPSE's post-reform regime, but it does not beat close-to-close at short horizons in "
                "Nepal, Bangladesh or Vietnam. Its open-free form passed a pre-registered test in Morocco.")
    p = para_with(doc, "Originality/value: ")
    set_body(p, "A market-design rule determines what daily bars measure, and an estimator built on that "
                "evidence is validated out of sample in four frontier markets.")
    p = para_with(doc, "Keywords: ")
    p.runs[0].text = p.runs[0].text.rstrip() + "; volatility estimator; out-of-sample evaluation"
    words = abstract_words(doc)
    assert words <= 255, f"abstract is {words} words"
    print(f"  rewrote the abstract ({words} words with its labels)")

    # ── introduction ─────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "This paper asks four questions, and the empirical sections answer them in order.")
    replace_in(p, "This paper asks four questions,", "This paper asks five questions,")
    replace_in(p, "Fourth, what does the opening price, which every within-session estimator and the proxy "
                  "itself read, actually measure?",
               "Fourth, what does the opening price, which every within-session estimator and the proxy "
               "itself read, actually measure? Fifth, can an estimator built for an unreliable open "
               "measure volatility better than the classical ones, in Nepal and in other frontier markets?")
    replace_in(p, "on what the daily bar's opening price measures.",
               "on what the daily bar's opening price measures. The fifth adds a constructive answer: an "
               "estimator designed on part of the NEPSE sample and tested out of sample, under frozen "
               "plans, in Nepal, two benchmark indices and three other frontier markets.")
    p = para_with(doc, "The fourth answer turns out to matter most.")
    para_after(p, (
        "The fifth answer builds on the fourth. If the open is mostly transient, an estimator should read "
        "it only as far as it is reliable, and should measure how far that is. The estimator of Section "
        f"6.8, which we call {NAME}, estimates the open's unbiasedness coefficient from the "
        "cross-section's recent history, weights the overnight move by it, extends the day's range to the "
        "effective open that the coefficient implies, blends in close-to-close variance as the open "
        "degrades, and calibrates the result to close-to-close variance across the cross-section. It was "
        "designed on NEPSE's first two rule regimes alone and then evaluated under three plans frozen "
        "before their results existed: on NEPSE's later regimes, the NIFTY 50 and S&P 500 indices, and "
        "stock panels from Bangladesh, Vietnam and Morocco. No classical range estimator beats it in any "
        f"of the seven test samples, and its calibrated level stays within {n['lev_dev']}% of "
        "close-to-close variance everywhere except NEPSE's post-reform regime, while the classical "
        f"estimators overstate it by up to {n['over_max']}% and understate it by up to {n['under_max']}% "
        "on the same samples. It does not beat close-to-close itself at short horizons in Nepal, "
        "Bangladesh or Vietnam, as the plans had predicted it would, and close-to-close beats it after "
        "NEPSE's band reform; the failed predictions are reported as failures. Its open-free form, which reads only the previous close, "
        "the high, the low and the close, had the lowest five-session forecast loss in every "
        "frontier-market panel of the second plan, a post hoc reading, and then passed a test fixed in "
        "advance in Morocco."), "Normal")

    # ── Section 6.8, after Figure 8 and before the table block ───────────────────────────────
    cap8 = para_with(doc, "Figure 8. What the opening price anticipates.")
    h = para_after(cap8, f"6.8 An estimator for an overreacting open: {NAME}", "Heading 2")
    s1 = para_after(h, (
        "Sections 6.6 and 6.7 say what an estimator for this market needs. The open carries a transient "
        "error that the session mostly reverses, so its overnight move should count only in proportion to "
        "how much of it survives. The range still carries the information that makes range estimators "
        "efficient, but it should be measured from where the efficient open lies rather than from the "
        "printed one. Close-to-close variance, the one measure the open cannot contaminate, should carry "
        "more weight as the open degrades. And the level should be set on the close-to-close scale rather "
        "than inherited from a formula derived for a continuously observed price path. Table 33 states the "
        "estimator that follows. The open's quality is the unbiasedness coefficient b = Σ o r / Σ o² of "
        f"Section 6.7, pooled over the cross-section and the last {n['pool']} dates and clipped to [0, 1]; "
        "b·o is then the part of the overnight move that the session keeps, and PC·exp(b o) the "
        "effective open. The range is extended to reach it, R* = R + max(0, b o - h) + max(0, l - b o), "
        "and the daily kernel A = (1 - w)[(b o)² + R*²/(4 ln 2)] + w r² blends in close-to-close variance "
        f"with weight w = {n['lam']}(1 - b). Its level is set by κ = Σ r² / Σ A over the same trailing set, "
        f"so that κ times the window mean of A is on the close-to-close scale. We refer to it as {NAME}. "
        "Each ingredient has an antecedent: the range is Parkinson's (1980), the sum of an overnight and a "
        "range term follows Yang and Zhang (2000), the range extended to the previous close is Wilder's "
        "(1978) true range, and scaling a partial measure to the close-to-close scale follows the "
        "whole-day scaling of Hansen and Lunde (2005). What is added is that the open's weight is "
        "measured from the data rather than assumed to be one. With b = 1 the kernel is the "
        "overnight-plus-Parkinson estimator; with b = 0, its open-free form, it is 0.8 times true-range "
        "Parkinson plus 0.2 r², which reads only the previous close, the high, the low and the close."),
        "Normal")
    s2 = para_after(s1, (
        "The estimator was designed on NEPSE's first two rule regimes (A1 and B) and on simulated panels "
        "where the truth is known, each design choice scored by tuning on one regime and forecasting the "
        "other, and its constants were fixed in a plan frozen before any later observation was read. The "
        "evaluation is a forecast comparison that does not need latent variance: every estimator forecasts "
        "the mean squared close-to-close return over the next 5 or 21 sessions, a conditionally unbiased "
        "target, so ranking by QLIKE loss matches the ranking that the true variance would give (Patton, "
        "2011). Every estimator is put on the close-to-close scale by the same pooled calibration, is given "
        "its own shrinkage toward its long-run level, chosen on a training span, and is scored on a common "
        "set of forecast origins; loss differences are tested with Newey-West statistics on the per-date "
        "difference (Diebold & Mariano, 1995; Newey & West, 1987). Three frozen plans supplied the test "
        "samples (Tables 34-36): NEPSE's later regimes A2 and C, the NIFTY 50 and the S&P 500; stock "
        "panels from Dhaka for 2023-2026 and Vietnam for 2007-2020, with a secondary Dhaka panel for "
        "2009-2021 whose dates had to be repaired; and the Casablanca Stock Exchange for 2012-2026. The "
        "three new markets were chosen because their daily stock data could be obtained, not for any "
        "property of their prices."), "Normal")
    s3 = para_after(s2, (
        "Against the classical estimators the result is uniform. No classical range estimator beats "
        f"{NAME} in any of the seven test samples at either horizon (Table 34), and in every "
        "frontier-market sample it beats all six at five sessions. Its calibrated level is within "
        f"{n['lev_dev']}% of close-to-close variance in every sample except NEPSE's post-reform regime, "
        f"where it is {n['lev_C']} (Table 35), while the classical estimators err in both directions: the "
        f"Yang-Zhang daily form is {n['yz_D23']} times close-to-close variance in Dhaka 2023-2026, and "
        f"Parkinson and Garman-Klass are {n['p_MA']} and {n['gk_MA']} times it in Morocco, a thin market in "
        "which many bars have no range at all. No classical formula is right in every market, which is the "
        "case for setting the level on each market's own close-to-close scale."), "Normal")
    s4 = para_after(s3, (
        "Against close-to-close the record is mixed, and frozen predictions failed. At five sessions "
        f"{NAME} beats close-to-close on the NIFTY 50 and S&P 500 indices (t = {n['NIFTY5_t']} and "
        f"{n['SP5_t']}), in Morocco (t = {n['MA5_t']}) and in the repaired Dhaka history (t = "
        f"{n['D095_t']}), but not on NEPSE's holdout (t = {n['NEPSE5_t']}), in Dhaka 2023-2026 (t = "
        f"{n['D235_t']}) or in Vietnam (t = {n['VN5_t']}), where the plans had predicted that it would. "
        "Close-to-close is significantly better in two places: in NEPSE's sessions after the band reform "
        f"(t = {n['C5_t']} at five sessions and {n['C21_t']} at 21) and in Vietnam at 21 sessions (t = "
        f"{n['VN21_t']}). The first of these has a mechanical part. The calibration pools the last "
        f"{n['pool']} dates, so after a sudden rule change it lags: in a post hoc check, a ten-date "
        f"calibration lowers the estimator's five-session loss in that regime from {n['y1_60']} to "
        f"{n['y1_10']}, against {n['y1_cc']} for close-to-close, and the difference is no longer "
        f"significant (t = {n['y1_t10']})."), "Normal")
    s5 = para_after(s4, (
        "The open-free form was reported, but not decided on, in the first two plans. Read after their "
        "verdicts, in a post hoc comparison, its loss was below the full estimator's in every NEPSE and "
        "every second-plan comparison, and it had the lowest five-session loss of all nine estimators in "
        "each panel of the second plan. Because that reading came after the results, the third plan tested "
        "it as a hypothesis fixed before the Moroccan data were read, and every frozen rule held: at five "
        f"sessions it beat close-to-close ({n['MA5_of']} against {n['MA5_cc']}, t = {n['MA5_of_t']}) and "
        f"the full estimator (t = {n['MA5_of_vs_anam_t']}), it had the lowest loss of all nine estimators "
        "at both horizons, and no estimator beat it. On the two indices, where the open is close to "
        "efficient, the full form had the lower loss, though not significantly. The evidence therefore "
        "supports the open-free form for markets whose open overreacts, with b well below one, as it is in "
        "every frontier market examined here (pooled medians between "
        f"{n['b_new_lo']} and {n['b_new_hi']} on the new test spans, against {n['b_nepse_lo']} to "
        f"{n['b_nepse_hi']} across NEPSE's regimes), and the full form where the open is reliable. It does "
        "not displace the paper's benchmark: after a sudden change in market rules, close-to-close beat "
        f"both forms (for the open-free form, t = {n['C5_of_t']} at five sessions in NEPSE's post-reform "
        "regime)."), "Normal")
    del s5
    print("  added Section 6.8")

    # ── Tables 33-36, after Table 32 ─────────────────────────────────────────────────────────
    doc.save(a.out)
    doc = docx.Document(a.out)
    anchor = spacer_after(table_of(doc, "Table 32."))
    for caption, csv_name in [
        (f"Table 33. {NAME}: the definition frozen in plan M16 before any holdout observation was read "
         "(Section 6.8). The constants are read from the estimator module the package runs.",
         "paper_table33_anam_definition.csv"),
        ("Table 34. Out-of-sample forecasts of future close-to-close variance: QLIKE loss (lower is "
         "better) on each test sample, with every estimator calibrated by the same pooled scheme, given its "
         "own shrinkage and scored on common origins, and the Newey-West t of each loss minus "
         "close-to-close's (negative favours the estimator). Plans M16-M18, frozen before testing "
         "(Section 6.8).", "paper_table34_anam_forecasts.csv"),
        ("Table 35. Level: each estimator's 21-session window mean divided by the 21-session mean of r² "
         f"on each test span; {NAME} enters calibrated and the classical estimators raw (Section 6.8).",
         "paper_table35_anam_level.csv"),
        (f"Table 36. Every frozen verdict for {NAME} and its open-free form, applied mechanically from "
         "the decision ledgers of plans M16-M18. Failed predictions are listed with the ones that held.",
         "paper_table36_anam_verdicts.csv"),
    ]:
        t = pd.read_csv(TAB / csv_name, dtype=str).fillna("")
        cap = para_after(anchor, caption, "Normal")
        new_t = new_table_after(cap, doc, list(t.columns), t.values.tolist())
        set_repeat_header_row(new_t)
        anchor = spacer_after(new_t)
    print("  added Tables 33-36")

    # ── Section 7: the protocol, the reporting formula and the estimator choice ─────────────
    p = para_with(doc, "Treat a change in opening rules as a break.")
    para_after(p, (
        f"Where one daily estimator must serve, use {NAME} (Section 6.8): its open-free form where the "
        "open's unbiasedness coefficient is well below one, as in every frontier market examined here, and "
        "its full form where the open is close to unbiased. Its calibrated level is on the close-to-close "
        "scale by construction. Report close-to-close beside it, and after a change in market rules rely "
        "on close-to-close until the estimator's calibration window has passed the change."), p.style)
    p = para_with(doc, "where v̂ is the chosen daily variance estimator and A is the market's own annual")
    p.runs[-1].text = p.runs[-1].text.rstrip() + (
        f" {NAME} fits the same form, with v̂ = κA, and needs no further adjustment of level, because κ "
        "already sets it on the close-to-close scale.")
    p = para_with(doc, "Proximity to a proxy is one criterion; it is not the only one,")
    replace_in(p, "and the paper states no formal loss function, so it cannot produce a universal ordering,",
               "and Sections 6.1-6.7 state no formal loss function, so they cannot produce a universal "
               "ordering,")
    p.runs[-1].text = p.runs[-1].text.rstrip() + (
        " Section 6.8 does state a formal loss function, the QLIKE loss of forecasts of future close-to-close "
        f"variance, and under it no classical range estimator beats {NAME} in any market tested; even so "
        "it yields no universal ordering, because close-to-close is not beaten everywhere.")
    print("  revised the protocol (Section 7), the reporting formula (7.1) and the estimator choice (7.2)")

    # ── Discussion ───────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "The band reform adds a market-design reading.")
    para_after(p, (
        "The estimator of Section 6.8 is the constructive side of these findings, and its record says "
        "something about the classical estimators as well as about itself. Every classical formula fixes "
        "how far the open is trusted; the data say that trust should be measured, because it varies "
        f"across NEPSE's own rule regimes ({n['b_nepse_lo']} to {n['b_nepse_hi']}) and across the frontier "
        f"markets examined (pooled medians between {n['b_new_lo']} and {n['b_new_hi']}). Once the open is "
        "discounted by its measured reliability and the level is set on the close-to-close scale, the "
        "range can add information that close-to-close alone does not have: no classical range estimator "
        "beat the estimator anywhere, and on the indices, in Morocco and in the long Dhaka history it beat "
        "close-to-close too. That the open-free form had the lowest loss of all nine estimators in "
        "Bangladesh, Vietnam and Morocco suggests something simpler: where the open overreacts, the most useful thing an estimator can do with it is to leave "
        "it out and measure the range from the previous close. The limits are the benchmark's. "
        "Close-to-close was not beaten at short horizons in three of the four frontier markets, and it beat "
        "both forms immediately after NEPSE's rule change, which is when a regulator or a risk manager most "
        "needs a reliable number."), "Normal")
    print("  added a Discussion paragraph")

    # ── Section 9 ────────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "Two further analyses were run under plans frozen and committed before their results")
    para_after(p, (
        "The estimator of Section 6.8 was developed and validated under three further frozen plans: M16 "
        "for its design on NEPSE's first two regimes and its holdout on NEPSE's later regimes, the NIFTY 50 "
        "and the S&P 500 (scripts 39 and 40, with post hoc follow-ups confined to script 41); M17 for "
        "Bangladesh and Vietnam (script 42); and M18 for Morocco (script 43). Each plan was committed to the "
        "package's history before the script that executes it existed, and its decision rules are applied "
        "mechanically to decision ledgers. The S&P 500 series is read from a public software package at a "
        "pinned version; the Dhaka, Vietnamese and Casablanca stock files are third-party files that the "
        "package does not redistribute but documents and pins by checksum, including the repair of the "
        "Dhaka file's dates. Corrections made after these results were seen are recorded in the audit "
        "register."), "Normal")

    # ── Limitations ──────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "Fourteenth, the noise-robust kernel of Section 6.7 is unbiased only if")
    para_after(p, (
        "Fifteenth, the estimator of Section 6.8 was designed on NEPSE data and has been tested in a finite "
        f"set of samples. Its {n['pool']}-date calibration lags a sudden change in rules, and in NEPSE's "
        "post-reform regime close-to-close beat it; a faster calibration closes most of that gap, but only "
        "in a post hoc check. Its open-free form was singled out after the second plan's results and has "
        "passed one frozen test since, in Morocco. The three new markets rest on third-party files whose "
        "provenance is weaker than NEPSE's: the Dhaka file's dates had to be repaired, the Vietnamese and "
        "Moroccan files do not document their original source, and the Moroccan prices are not adjusted for "
        "dividends."), "Normal")
    k = renumber_limitations(doc)
    print(f"  extended the limitations (now {k})")

    # ── Conclusion ───────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "The paper's second finding qualifies its first.")
    para_after(p, (
        "The third finding is constructive. An estimator that measures how far the open can be trusted, "
        f"reads it only that far and calibrates to close-to-close variance ({NAME}, Section 6.8) was "
        "beaten by no classical range estimator in any of seven out-of-sample tests across Nepal, "
        "Bangladesh, Vietnam, Morocco and two benchmark indices, and outside NEPSE's post-reform regime its "
        f"level stayed within {n['lev_dev']}% of close-to-close variance, where the classical formulas "
        "missed it by tens of percent in both directions. It did not "
        "beat close-to-close at short horizons in three of the four frontier markets, and its open-free "
        "form, which leaves the open out altogether, is the version the frontier-market evidence supports."),
        "Normal")
    p = para_with(doc, "The claims should stop there, including the claim to novelty.")
    replace_in(p, "and evidence that the market's opening rules shape what its daily bars measure.",
               "evidence that the market's opening rules shape what its daily bars measure, and an "
               "estimator built on that evidence and tested out of sample under frozen plans.")
    print("  revised the Conclusion")

    # ── Declarations ─────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "Data availability statement:")
    p.runs[-1].text = p.runs[-1].text.rstrip() + (
        " The analysis of Section 6.8 also uses the S&P 500 series distributed with the arch Python "
        "package (version 8.0.0) and stock-level files for the Dhaka, Vietnamese and Casablanca exchanges "
        "that are not redistributed; the package documents their sources and pins each by its SHA-256 "
        "digest.")

    # ── References, kept alphabetical ────────────────────────────────────────────────────────
    paras = list(doc.paragraphs)
    first = find(paras, "Alizadeh, S., Brandt, M. W.")
    last = find(paras, "Zhang, L., Mykland, P. A.")
    existing = [paras[i].text.strip() for i in range(first, last + 1) if paras[i].text.strip()]
    merged = sorted(set(existing) | set(REFS), key=lambda r: re.sub(r"^(The )", "", r).lower())
    slots = list(range(first, last + 1))
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
    assert len(doc.tables) == 36, f"expected 36 tables, found {len(doc.tables)}"
    assert len(doc.inline_shapes) == 8, f"expected 8 figures, found {len(doc.inline_shapes)}"
    assert abstract_words(doc) <= 255
    findings = next(p.text for p in paras if p.text.startswith("Findings:"))
    assert "NIFTY" not in findings, "M-014: no index figure in the abstract's findings"
    for needle in (f"6.8 An estimator for an overreacting open: {NAME}", "Table 33.", "Table 34.",
                   "Table 35.", "Table 36.", "This paper asks five questions",
                   "Parkinson's (1980)", "Yang and Zhang (2000)", "Wilder's (1978) true range",
                   "Hansen and Lunde (2005)", "Diebold & Mariano, 1995", "Newey & West, 1987",
                   "no claim is made to introduce security-level",
                   "makes no claim to introduce security-level",
                   "addresses a measurement question not identified in the targeted search"):
        assert needle in body, f"missing after round 15: {needle!r}"
    for k in ("NIFTY5_t", "SP5_t", "MA5_t", "D095_t", "NEPSE5_t", "D235_t", "VN5_t", "C5_t", "C21_t",
              "VN21_t", "MA5_of", "MA5_cc", "MA5_of_t", "MA5_of_vs_anam_t", "y1_60", "y1_10", "lev_dev"):
        assert str(n[k]) in body, f"interpolated figure missing: {k} = {n[k]}"
    # the open-free form's M16-M17 record is post hoc wherever it is quoted
    for sentence in re.split(r"(?<=[.!?])\s+", body):
        if "lowest five-session" in sentence and "second plan" in sentence:
            assert "post hoc" in sentence, f"unlabelled post hoc reading: {sentence[:90]!r}"
    i = find(paras, "Several limitations")
    j = find(paras, "11. Conclusion", i)
    found = [p.text.split(",")[0] for p in paras[i + 1:j] if p.text.split(",")[0] in ORDINALS]
    assert found == ORDINALS[1:len(found) + 1] and found[-1] == "Fifteenth", f"limitation ordinals: {found}"
    i_refs = next(k for k, p in enumerate(paras) if p.text.strip() == "References")
    j_refs = find(paras, "Data and reproducibility note", i_refs)
    refs = [p.text for p in paras[i_refs + 1:j_refs] if p.text.strip()]
    keys = [re.sub(r"^(The )", "", r).lower() for r in refs]
    assert keys == sorted(keys), "reference list is not alphabetical"
    for r in REFS:
        assert r in refs, r[:40]
    print(f"verification: {len(doc.tables)} tables, {len(doc.inline_shapes)} figures, {len(refs)} "
          f"references, abstract {abstract_words(doc)} words; no banned phrase; post hoc readings labelled")


if __name__ == "__main__":
    main()
