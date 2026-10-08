"""Round 14: the instrumented calibration (M14) and what the opening price measures (M15).

    python paper/apply_round14_revisions.py [--base BASE.docx] [--out OUT.docx]

Both analyses ran under plans frozen and committed before their results existed:
``M14_CALIBRATION_ANALYSIS_PLAN.md`` (results in ``M14_CALIBRATION_RESULTS.md``) and
``M15_OPENING_PRICE_ANALYSIS_PLAN.md`` (results in ``M15_OPENING_PRICE_RESULTS.md``). This script
moves them into the manuscript: a new Section 6.6 (calibration slopes rather than ratios), a new
Section 6.7 (what the opening price measures, with NEPSE's 20 April 2026 pre-open band reform as
a natural experiment), Tables 29-32, Figures 7-8, and the changes they force in the title,
abstract, introduction, protocol, discussion, limitations, conclusion and references.

RULES ENFORCED HERE
  * Every number is interpolated from a frozen table; nothing is typed.
  * Frozen verdicts are quoted from the decision ledgers (table86, table96), never re-derived.
  * Post hoc results (M14's E1/E2, M15's X1-X5) are labelled post hoc wherever they are quoted.
  * Failed predictions are reported as failed (M14: H2, H4, H5 slopes; M15: H8, H9(a), H10).
  * The identification devices are credited and not claimed (Christensen & Prabhala 1998;
    Hansen & Lunde 2014; Biais, Hillion & Spatt 1999; Barclay & Hendershott 2003; Zhou 1996);
    no "first"; the reform is evidence about a rule package, with its confounds named.
  * "Transient opening error" or "overreaction", never unqualified "noise".
  * The M13 statements survive: no claim to introduce security-level analysis to Nepal, and the
    measurement question "not identified in the targeted search".
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

import pandas as pd

try:
    import docx
    from docx.oxml import OxmlElement
    from docx.shared import Inches
    from docx.text.paragraph import Paragraph
except ImportError:
    sys.exit("python-docx is required:  pip install python-docx")

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"
FIG = ROOT / "output" / "figures"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from apply_referee_revisions import find, new_table_after, para_after, set_text  # noqa: E402
from apply_round4_revisions import set_repeat_header_row  # noqa: E402

DOCX = ROOT / "paper" / "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"

TITLE = "When the Open Overreacts: Measuring Daily Volatility in a Frontier Market without Options"
SUBTITLE = "Evidence from a Pre-Open Band Reform on the Nepal Stock Exchange"

BANNED = {
    "primarily index-level": "retired by M13",
    "fills a gap": "M13 wording rule",
    "no prior study": "a search cannot establish absence",
    "first study": "no first claims",
    "the first to": "no first claims",
    "systematic review": "a targeted search, not a systematic review",
    "is noise": "M15 wording rule: transient opening error or overreaction",
    "proves that": "evidence, not proof",
}

WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
         8: "eight", 9: "nine", 10: "ten"}
ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth",
            "Tenth", "Eleventh", "Twelfth", "Thirteenth", "Fourteenth", "Fifteenth"]

# New references, alphabetised into the list. Their bibliographic records are checked against
# publisher-deposited metadata, and the outcome is recorded in AUDIT-REGISTER.md (M-012).
REFS = [
    "Amihud, Y., & Mendelson, H. (1987). Trading mechanisms and stock returns: An empirical "
    "investigation. Journal of Finance, 42(3), 533-553. "
    "https://doi.org/10.1111/j.1540-6261.1987.tb02582.x",
    "Arellano, M., & Bover, O. (1995). Another look at the instrumental variable estimation of "
    "error-components models. Journal of Econometrics, 68(1), 29-51. "
    "https://doi.org/10.1016/0304-4076(94)01642-D",
    "Barclay, M. J., & Hendershott, T. (2003). Price discovery and trading after hours. Review of "
    "Financial Studies, 16(4), 1041-1073. https://doi.org/10.1093/rfs/hhg030",
    "Biais, B., Hillion, P., & Spatt, C. (1999). Price discovery and learning during the "
    "preopening period in the Paris Bourse. Journal of Political Economy, 107(6), 1218-1248. "
    "https://doi.org/10.1086/250095",
    "Christensen, B. J., & Prabhala, N. R. (1998). The relation between implied and realized "
    "volatility. Journal of Financial Economics, 50(2), 125-150. "
    "https://doi.org/10.1016/S0304-405X(98)00034-8",
    "Hansen, P. R., & Lunde, A. (2014). Estimating the persistence and the autocorrelation "
    "function of a time series that is measured with error. Econometric Theory, 30(1), 60-93. "
    "https://doi.org/10.1017/S0266466613000121",
    "Kim, K. A., & Rhee, S. G. (1997). Price limit performance: Evidence from the Tokyo Stock "
    "Exchange. Journal of Finance, 52(2), 885-901. "
    "https://doi.org/10.1111/j.1540-6261.1997.tb04827.x",
    "Stoll, H. R., & Whaley, R. E. (1990). Stock market structure and volatility. Review of "
    "Financial Studies, 3(1), 37-71. https://doi.org/10.1093/rfs/3.1.37",
    "Zhou, B. (1996). High-frequency data and volatility in foreign-exchange rates. Journal of "
    "Business & Economic Statistics, 14(1), 45-52. https://doi.org/10.1080/07350015.1996.10524628",
]


# ─────────────────────────────────────────────────────────────────── numbers from the package

def f3(v) -> str:
    return f"{float(v):.3f}"


def ci(lo, hi) -> str:
    return f"[{float(lo):.3f}, {float(hi):.3f}]"


def pct(v, dp=0) -> str:
    return f"{100 * float(v):.{dp}f}%"


def load() -> dict:
    n: dict = {}
    # M14
    t78 = pd.read_csv(TAB / "table78_calibration_full.csv").set_index("measure")
    for k in ["P", "GK", "RS", "AddRS", "AP"]:
        r = t78.loc[k]
        n[f"{k}_slope"], n[f"{k}_ci"] = f3(r.iv_slope), ci(r.iv_slope_lo, r.iv_slope_hi)
        n[f"{k}_ratio"], n[f"{k}_delta"] = f3(r.mean_ratio_var), f3(r.additive_share)
    rng = t78.loc[["P", "GK", "RS"]]
    n["ols_lo"], n["ols_hi"] = f"{rng.ols_slope.min():.2f}", f"{rng.ols_slope.max():.2f}"
    n["corr_lo"], n["corr_hi"] = f"{rng.corr_with_ref.min():.2f}", f"{rng.corr_with_ref.max():.2f}"
    t85 = pd.read_csv(TAB / "table85_calibration_sensitivity.csv")
    p85 = t85[t85.measure == "P"].iv_slope
    n["P_sens_lo"], n["P_sens_hi"] = f3(p85.min()), f3(p85.max())
    t86 = pd.read_csv(TAB / "table86_m14_decisions.csv")
    n["m14_verdicts"] = t86
    h2 = t86[t86.hypothesis == "H2"].iloc[0]
    n["H2_est"], n["H2_verdict"] = h2.estimate, h2.verdict
    n["H1_verdicts"] = set(t86[t86.hypothesis == "H1"].verdict)
    t84 = pd.read_csv(TAB / "table84_nifty_vix.csv")
    ex = t84[t84["sample"].str.startswith("excl")]
    n["nifty_P_lag"] = f3(ex[(ex.instruments == "(i) lagged OC, P") & (ex.measure == "P")].iv_slope.iloc[0])
    n["nifty_P_vix"] = f3(ex[(ex.instruments == "(ii) India VIX only") & (ex.measure == "P")].iv_slope.iloc[0])
    n["H6_verdicts"] = set(t86[t86.hypothesis == "H6"].verdict)

    # M15
    u = pd.read_csv(TAB / "table89_m15_unbiasedness.csv")

    def u_(regime, group, prefix):
        q = u[(u.regime == regime) & (u.group == group) & u.statistic.str.startswith(prefix)]
        return q.iloc[0]
    for g in ["A1", "B", "A2", "C"]:
        r = u_(g, "all", "unbiasedness")
        n[f"b_{g}"], n[f"bci_{g}"], n[f"bv_{g}"] = f3(r.value), ci(r.lo, r.hi), float(r.value)
        n[f"oa_{g}"] = float(u_(g, "all", "E[o a]").value)
        n[f"oq_{g}"] = float(u_(g, "all", "E[o q]").value)
    for g, z in [("A1", "pinned"), ("B", "pinned"), ("A2", "pinned"), ("C", "pinned"),
                 ("C", "old-band zone"), ("C", "interior"), ("A2", "interior")]:
        r = u_(g, z, "b")
        key = z.replace(" ", "_").replace("-", "_")
        n[f"b_{key}_{g}"], n[f"bci_{key}_{g}"] = f3(r.value), ci(r.lo, r.hi)
    undo = {g: 1 - n[f"bv_{g}"] for g in ["A1", "B", "A2", "C"]}
    n["undo_lo"], n["undo_hi"] = f"{100 * min(undo.values()):.0f}", f"{100 * max(undo.values()):.0f}"
    n["undo_A1"] = f"{100 * undo['A1']:.0f}"
    n["early_A1"] = f"{-100 * n['oa_A1']:.0f}"
    n["late_A1"] = f"{-100 * n['oq_A1']:.0f}"
    liq = u[u.block == "liquidity quintile"]
    n["liq_all_below_one"] = bool((liq.value < 1).all())
    n["liq_pre_lo"], n["liq_pre_hi"] = (f"{liq[liq.regime != 'C'].value.min():.2f}",
                                        f"{liq[liq.regime != 'C'].value.max():.2f}")
    n["liq_C_lo"], n["liq_C_hi"] = (f"{liq[liq.regime == 'C'].value.min():.2f}",
                                    f"{liq[liq.regime == 'C'].value.max():.2f}")
    n["stale_A2"] = pct(u_("A2", "all", "share of opens equal").value, 1)
    n["stale_C"] = pct(u_("C", "all", "share of opens equal").value, 1)
    n["pinned_A1"] = pct(u_("A1", "all", "share of opens pinned").value)
    n["pinned_C"] = pct(u_("C", "all", "share of opens pinned").value)

    w = pd.read_csv(TAB / "table90_m15_event_window.csv")

    def w_(window, stat):
        return w[(w.window == window) & (w.statistic == stat)].iloc[0]
    n["b_pre"], n["b_gap"], n["b_post"] = (f3(w_("pre", "b").value), f3(w_("gap", "b").value),
                                           f3(w_("post", "b").value))
    n["n_gap"] = int(w_("gap", "b").sessions)
    j = w_("jump: post - pre", "difference in b")
    n["jump"], n["jump_ci"] = f3(j.value), ci(j.lo, j.hi)
    jl = w_("jump, post window starting at the 6th session", "difference in b")
    n["jump_late"] = f3(jl.value)
    pl = pd.read_csv(TAB / "table90b_m15_placebo_breaks.csv")
    n["n_plac"], n["plac_min"] = len(pl), f3(pl.jump.min())
    n["plac_at_or_below"] = int((pl.jump <= float(j.value)).sum())
    m = pd.read_csv(TAB / "table91_m15_monthly.csv")
    pre_m = m[m.month <= "2026-03"]
    post_m = m[m.month >= "2026-05"]
    n["m_pre_hi"], n["m_pre_lo"] = f"{pre_m.oc_over_P.max():.2f}", f"{pre_m.oc_over_P.min():.2f}"
    n["m_post_hi"], n["m_post_lo"] = f"{post_m.oc_over_P.max():.2f}", f"{post_m.oc_over_P.min():.2f}"
    cal = pd.read_csv(ROOT / "data" / "processed" / "nepse_trading_calendar.csv",
                      parse_dates=["date"])
    sess = cal[cal["is_session"]]
    n["n_C"] = int(((sess.date >= "2026-04-20") & (sess.date <= "2026-08-26")).sum())
    dr = pd.read_csv(TAB / "table92_m15_dose_response.csv")
    did = dr[(dr.grouping == "terciles") & dr.period.str.startswith("DiD: (high")].iloc[0]
    n["did"], n["did_ci"] = f3(did.value), ci(did.lo, did.hi)
    t3 = dr[(dr.grouping == "terciles") & dr.group.isin(["T1", "T2", "T3"])]
    n["terc_A2"] = ", ".join(f3(v) for v in t3[t3.period == "A2"].sort_values("group").value)
    n["terc_C"] = ", ".join(f3(v) for v in t3[t3.period == "C"].sort_values("group").value)

    e = pd.read_csv(TAB / "table93_m15_estimator_evaluation.csv")

    def e_(regime, measure, stat):
        return e[(e.regime == regime) & (e.measure == measure) & (e.statistic == stat)].iloc[0]
    for g in ["A2", "C"]:
        n[f"P_OC_{g}"] = f3(e_(g, "P", "E[X]/E[OC]").value)
        n[f"P_K_{g}"] = f3(e_(g, "P", "E[X]/E[K]").value)
    d1, d2 = e_("C - A2", "P", "change in E[X]/E[OC]"), e_("C - A2", "P", "change in E[X]/E[K]")
    n["dP_OC"], n["dP_OC_ci"] = f3(d1.value), ci(d1.lo, d1.hi)
    n["dP_K"], n["dP_K_ci"] = f3(d2.value), ci(d2.lo, d2.hi)

    y = pd.read_csv(TAB / "table94_m15_yang_zhang.csv")

    def y_(win, prefix):
        return y[(y.windows == win) & y.statistic.str.startswith(prefix)].iloc[0]
    r = y_("all windows", "sum YZ / sum Var21")
    n["yz_all"], n["yz_all_ci"], n["yz_sd"] = f3(r.value), ci(r.lo, r.hi), f"{float(r.value) ** 0.5:.3f}"
    n["n_yz_windows"] = f"{int(r.n_windows):,}"
    r = y_("all windows", "share of sum(YZ")
    n["cov_share"], n["cov_share_ci"] = pct(r.value, 1), f"[{100 * r.lo:.1f}%, {100 * r.hi:.1f}%]"
    for g in ["A1", "B", "A2", "C"]:
        n[f"yz_{g}"] = f3(y_(g, "sum YZ / sum Var21").value)
    r = y[(y.windows == "C - A2")].iloc[0]
    n["dyz"], n["dyz_ci"] = f3(r.value), ci(r.lo, r.hi)

    nf = pd.read_csv(TAB / "table95_m15_nifty.csv")
    nx = nf[nf["sample"].str.startswith("excl")].set_index("statistic")
    n["b_N"], n["bci_N"] = f3(nx.loc["b", "value"]), ci(nx.loc["b", "lo"], nx.loc["b", "hi"])
    n["undo_N"] = f"{100 * (1 - float(nx.loc['b', 'value'])):.0f}"
    n["yz_N"], n["yz_N_ci"] = f3(nx.loc["YZ/Var21(r)", "value"]), ci(nx.loc["YZ/Var21(r)", "lo"], nx.loc["YZ/Var21(r)", "hi"])
    n["kshare_N"] = f3(nx.loc["transient share 1 - E[K]/E[OC]", "value"])

    led = pd.read_csv(TAB / "table96_m15_decisions.csv").set_index("hypothesis")
    n["m15_ledger"] = led
    for h in ["H7", "H8", "H9(a)", "H9(b)", "H9", "H10 (consequence)", "H11"]:
        n[f"v_{h}"] = led.loc[h, "verdict"]

    x = pd.read_csv(TAB / "table97_m15_posthoc.csv")

    def x_(regime, prefix):
        return x[(x.regime == regime) & x.statistic.str.startswith(prefix)].iloc[0]
    n["lb_A1"], n["lb_C"] = pct(x_("A1", "lower bound").value, 1), pct(x_("C", "lower bound").value, 1)
    n["lb_C_ci"] = f"[{100 * x_('C', 'lower bound').lo:.1f}%, {100 * x_('C', 'lower bound').hi:.1f}%]"
    n["ind_C"] = pct(x_("C", "E[eta^2]/E[OC] if eta").value, 1)
    n["ext_A1"], n["ext_C"] = (pct(x_("A1", "share of non-stale").value),
                               pct(x_("C", "share of non-stale").value))
    up = x_("C", "upward band-pinned opens: mean intraday")
    n["c_up5"] = f"{100 * up.value:.2f}%"
    o_up = x_("C", "upward band-pinned opens: mean opening")
    n["o_up5"] = f"+{100 * o_up.value:.2f}%"
    ret = x_("C", "upward band-pinned opens: share of the opening move retained")
    n["ret_up5"], n["ret_up5_ci"] = pct(ret.value, 1), f"[{100 * ret.lo:.1f}%, {100 * ret.hi:.1f}%]"
    n["offgrid_B"] = pct(x_("B", "share of closes off").value, 1)
    other = [x_(g, "share of closes off").value for g in ["A1", "A2", "C"]]
    n["offgrid_other_max"] = pct(max(other), 2)
    n["excl_pinned"] = pct(x_("2025-09-18 (excluded)", "share of opens pinned").value)
    return n


# ─────────────────────────────────────────────────────────────────── docx utilities

def replace_in(p, old: str, new: str) -> None:
    t = p.text
    assert t.count(old) == 1, f"expected exactly one {old[:60]!r} in paragraph"
    set_text(p, t.replace(old, new))


def para_with(doc, needle: str):
    paras = list(doc.paragraphs)
    return paras[find(paras, needle)]


def heading_after(anchor, text, style="Heading 2"):
    return para_after(anchor, text, style)


def picture_after(anchor, png: pathlib.Path, width_in: float = 6.0):
    p = para_after(anchor, "", "Normal")
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    p.add_run().add_picture(str(png), width=Inches(width_in))
    return p


def spacer_after(tbl):
    el = OxmlElement("w:p")
    tbl._tbl.addnext(el)
    return Paragraph(el, tbl._parent)


def table_of(doc, caption_start: str):
    """The docx table immediately after the paragraph whose text starts with ``caption_start``."""
    paras = list(doc.paragraphs)
    cap = next(p for p in paras if p.text.startswith(caption_start))
    children = list(doc.element.body)
    pos = children.index(cap._p)
    n_before = sum(1 for el in children[:pos] if el.tag.endswith("}tbl"))
    return doc.tables[n_before]


def renumber_limitations(doc) -> int:
    paras = list(doc.paragraphs)
    start = find(paras, "Several limitations should keep the conclusions")
    end = find(paras, "11. Conclusion", start)
    pat = re.compile(r"^(" + "|".join(ORDINALS) + r")(,)")
    k = 1
    for i in range(start + 1, end):
        t = paras[i].text.strip()
        mt = pat.match(t)
        if not mt:
            continue
        if mt.group(1) != ORDINALS[k]:
            set_text(paras[i], pat.sub(ORDINALS[k] + ",", t, count=1))
        k += 1
    return k


# ─────────────────────────────────────────────────────────────────── the revision

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(DOCX))
    ap.add_argument("--out", default=str(DOCX))
    a = ap.parse_args()
    n = load()
    doc = docx.Document(a.base)
    if any(p.text.startswith("6.7 What the opening price measures") for p in doc.paragraphs):
        sys.exit("round 14 has already been applied to this document")

    # ── title ────────────────────────────────────────────────────────────────────────────────
    paras = list(doc.paragraphs)
    set_text(paras[0], TITLE)
    set_text(paras[1], SUBTITLE)
    p = para_with(doc, "Revised manuscript ·")
    set_text(p, "Revised manuscript · October 2026")
    p = para_with(doc, "Data and reproducibility note.")
    replace_in(p, "by paper/apply_referee_revisions.py rather than transcribed.",
               "by the revision scripts in paper/ (apply_referee_revisions.py through "
               "apply_round14_revisions.py) rather than transcribed.")
    replace_in(p, "The empirical analyses are descriptive and exploratory unless explicitly stated "
                  "otherwise.",
               "The empirical analyses are descriptive and exploratory unless explicitly stated "
               "otherwise; the forward India VIX test of Section 6.3 and the analyses of Sections "
               "6.6 and 6.7 follow analysis plans frozen before their results existed, and their "
               "post hoc follow-ups are labelled as such.")

    # ── abstract, rebuilt to the 250-word cap around the new contribution ───────────────────
    SECTIONS = {
        "Purpose": (
            "Nepal has no exchange-traded options and no public intraday data, so volatility "
            "must be measured from the daily open-high-low-close bar. This paper asks how "
            "reliable that measurement is, and what the bar's opening price contributes to it."),
        "Design/methodology/approach": (
            "Six estimators are evaluated on 143,718 ordinary-equity stock-days (292 securities, "
            "March 2024-August 2026) against proxies matched in scope, sample and horizon. "
            "Instrumented calibration slopes, identified from volatility persistence without a "
            "high-frequency benchmark, separate calibration from offsetting distortions. NEPSE's "
            "20 April 2026 widening of the pre-open band from ±2% to ±5% serves as a natural "
            "experiment. Both analyses follow plans frozen before testing."),
        "Findings": (
            f"Range estimators are calibrated to the open-to-close proxy (Parkinson slope "
            f"{n['P_slope']} {n['P_ci']}), but the proxy shares the opening price, and the open "
            f"is mostly transient: the session undoes {n['undo_lo']}-{n['undo_hi']}% of the "
            f"overnight move (unbiasedness coefficient {n['b_C']}-{n['b_A2']}; NIFTY 50: "
            f"{n['b_N']}). The band widening produced a sharp break: the coefficient fell by "
            f"{n['jump'].lstrip('-')}, more than at any of {n['n_plac']} placebo dates. Opens "
            "pinned at the old band had already been reversed, so the narrow band capped "
            "overreaction without detectably delaying price discovery. Three-quarters of "
            "Yang-Zhang's excess over close-to-close variance is the overnight-intraday "
            "covariance it assumes away."),
        "Originality/value": (
            "The contribution is evidence rather than a new estimator: a market-design rule "
            "determines what daily bars measure, ratio comparisons cannot see it, and close-to-"
            "close returns, which never read the open, are the robust benchmark where the open "
            "overreacts."),
    }
    total_words = sum(len(t.split()) for t in SECTIONS.values())
    assert total_words <= 250, f"abstract is {total_words} words, over the 250 cap"
    for p in list(doc.paragraphs):
        for label, text in SECTIONS.items():
            if p.text.startswith(label + ":"):
                for r in list(p.runs):
                    r._r.getparent().remove(r._r)
                lab = p.add_run(f"{label}: ")
                lab.bold = True
                p.add_run(text)
                break
    print(f"  title replaced; abstract rebuilt at {total_words} words (cap 250)")

    p = para_with(doc, "Keywords:")
    set_text(p, "Keywords: frontier markets; volatility measurement; opening auction; price "
                "limits; unbiasedness regression; natural experiment; instrumented calibration; "
                "range-based estimators; Yang-Zhang; Nepal Stock Exchange; imperfect volatility "
                "proxies; market microstructure")
    p = para_with(doc, "JEL Classification:")
    set_text(p, "JEL Classification: C26, C58, G12, G14, G15, G18, O16")

    # ── introduction: the questions, the contribution, and a preview of the results ─────────
    p = para_with(doc, "This paper asks three questions, and the empirical sections answer them")
    old_q = p.text[:p.text.index("Answering them yields a contribution")]
    new_q = (
        "This paper asks four questions, and the empirical sections answer them in order. "
        "First, do range estimators remain informative for ordinary NEPSE equities as liquidity "
        "declines? Second, how much of the apparent estimator failure in a frontier market "
        "arises from instrument composition and from benchmark mismatch rather than from "
        "illiquidity? Third, when an estimator agrees with its matched proxy, is that agreement "
        "calibration, or two distortions cancelling? Fourth, what does the opening price, which "
        "every within-session estimator and the proxy itself read, actually measure? ")
    replace_in(p, old_q, new_q)
    replace_in(p, "That addresses a measurement question not identified in the targeted search, "
                  "which is a weaker and more honest statement than a claim of novelty. ",
               "That addresses a measurement question not identified in the targeted search, "
               "which is a weaker and more honest statement than a claim of novelty. The third "
               "and fourth questions add two things the comparison alone could not supply: a "
               "calibration test that identifies how each estimator responds to latent variance "
               "without a high-frequency benchmark, and evidence, from a natural experiment in "
               "the exchange's own opening rules, on what the daily bar's opening price "
               "measures. ")
    para_after(p, (
        "The fourth answer turns out to matter most. NEPSE's opening price is mostly transient: "
        f"the trading session undoes between {n['undo_lo']}% and {n['undo_hi']}% of the "
        "overnight move under every rule regime in the sample, against "
        f"{n['undo_N']}% on NIFTY 50. When the exchange widened its pre-open price band on 20 "
        "April 2026, the share of the opening move that survives to the close fell sharply, by "
        f"more than at any of {n['n_plac']} placebo dates; and opens pinned at the old band had "
        "been reversed rather than continued, so the narrow band had been capping overreaction "
        "rather than delaying price discovery. For measurement, this means that every estimator "
        "reading the open inherits its error. The range estimators' agreement with the "
        "open-to-close proxy is genuine calibration, but calibration to a benchmark that shares "
        "the same error. Three-quarters of Yang-Zhang's excess over close-to-close variance is "
        "the overnight-intraday covariance it assumes away. And the close-to-close return, which "
        "never reads the open, is the benchmark that survives. Both analyses were run under "
        "plans frozen before their results existed, and the predictions that failed are "
        "reported with the ones that held."), "Normal")
    print("  rewrote the Introduction's questions and contribution; added a results preview")

    # ── Section 3: date the closing-rule regime from the data ───────────────────────────────
    p = para_with(doc, "The calendar also matters, and April 2026 contains two distinct reforms")
    replace_in(p, "Section 7.1 reports the value implied by NEPSE's own calendar.",
               "Section 7.1 reports the value implied by NEPSE's own calendar. A third rule "
               "change concerns the close. From 20 March to 21 September 2025 the official "
               "closing price was the volume-weighted average of the session's final fifteen "
               "minutes rather than the last trade; the regime is dated from the data, where "
               f"{n['offgrid_B']} of closes inside it lie off the exchange's 0.1-rupee price "
               f"grid, against at most {n['offgrid_other_max']} in any other period (a post hoc "
               "descriptive check). Sections 6.6 and 6.7 use the four regimes these dates "
               "define. They exclude one early-closing session, 18 September 2025, on which "
               "trading resumed after the September 2025 market halt and, in the same post hoc "
               f"check, {n['excl_pinned']} of opens sat at the band.")

    # ── Section 4.5: Yang-Zhang's independence assumption ───────────────────────────────────
    p = para_with(doc, "Yang and Zhang (2000) combine an overnight variance term")
    replace_in(p, "With an n-session window, its weight is k = 0.34/[1.34 + (n+1)/(n-1)].",
               "With an n-session window, its weight is k = 0.34/[1.34 + (n+1)/(n-1)]. The "
               "construction treats the overnight and open-to-close returns as independent; "
               "Section 6.7 shows that in NEPSE they are strongly negatively correlated, because "
               "the opening price overreacts, and that this covariance accounts for most of "
               "Yang-Zhang's distance from close-to-close variance.")

    # ── Section 5.3: the open, measured differently ─────────────────────────────────────────
    p = para_with(doc, "The project's attempted censored-normal recovery failed")
    replace_in(p, "is therefore not used in this paper.",
               "is therefore not used in this paper. Section 6.7 returns to the open with a "
               "question the data can answer: not what the latent opening return would have "
               "been, but how much of the observed opening move survives to the close.")

    # ── Section 6.5: point the Yang-Zhang figure at its explanation ──────────────────────────
    p = para_with(doc, "Close-to-close against itself is one by construction and anchors the scale.")
    replace_in(p, "Close-to-close against itself is one by construction and anchors the scale.",
               "Close-to-close against itself is one by construction and anchors the scale. "
               "Section 6.7 accounts for the Yang-Zhang figure: most of its excess is the "
               "overnight-intraday covariance the estimator assumes away.")

    # ── Sections 6.6 and 6.7, after the robustness list and before the table block ──────────
    anchor = para_with(doc, "Calendar and staleness. The data-detected trading calendar")
    h = heading_after(anchor, "6.6 Calibration slopes: what a ratio cannot see")
    p1 = para_after(h, (
        "Every comparison so far is a ratio of means, and a ratio cannot tell an estimator that "
        "tracks variance from one whose distortions cancel. A thin market produces two distortions "
        "that pull "
        "in opposite directions. With few trades the observed extremes come from a short sample, "
        "so a range estimator responds less than one-for-one to latent variance, a "
        "multiplicative distortion. Bid-ask bounce and transient auction errors add a component "
        "that does not scale with it, an additive one. Writing each estimator as X = α + β·IV + "
        "U, its mean ratio to the proxy is exactly β + δ, a calibration slope plus an additive "
        "share, so a ratio of one is consistent with a slope of 0.7 offset by an additive share "
        "of 0.3. The slope can be identified without a high-frequency benchmark from volatility "
        "persistence. Lagged realised measures predict a session's variance but are "
        "uncorrelated with its measurement error, so they are valid instruments however "
        "strongly the estimators' same-day errors are correlated. The device is the "
        "errors-in-variables remedy of Christensen and Prabhala (1998) and the lagged-instrument "
        "logic of Hansen and Lunde (2014); only its application to daily-bar estimators is new "
        "here. Security effects are removed by forward orthogonal deviations (Arellano & Bover, "
        "1995), so that no instrument sees the session it instruments. The specification, the "
        "decision rules and a Monte Carlo validation on simulated NEPSE-like panels were fixed "
        "before any slope was computed on the data."), "Normal")
    p2 = para_after(p1, (
        "The near-unit ratios survive the test (Table 29, Figure 7). Parkinson's calibration "
        f"slope is {n['P_slope']} {n['P_ci']}, Garman-Klass's {n['GK_slope']} {n['GK_ci']} and "
        f"Rogers-Satchell's {n['RS_slope']} {n['RS_ci']}. Every interval contains one, so the "
        "frozen verdict for all three is no detectable attenuation, and Parkinson's slope stays "
        f"between {n['P_sens_lo']} and {n['P_sens_hi']} across the sensitivity specifications. "
        f"The additive correction behaves differently. AddRS's ratio of {n['AddRS_ratio']} on "
        f"the variance scale decomposes into a slope of {n['AddRS_slope']} {n['AddRS_ci']} and "
        f"an additive share of {n['AddRS_delta']}, so its overshoot is mostly a slope problem: "
        "it rises about a third more than the proxy when predictable variance rises. An "
        "average-price estimator built from the session VWAP is amplified further "
        f"({n['AP_slope']} {n['AP_ci']}). The naive statistics a reader might have used instead "
        f"say nothing about calibration: the OLS slopes of the range estimators on the proxy run "
        f"from {n['ols_lo']} to {n['ols_hi']} and their correlations from {n['corr_lo']} to "
        f"{n['corr_hi']}. Three pre-specified predictions failed and are reported as such: no "
        f"liquidity gradient in the slope ({n['H2_est']}; {n['H2_verdict']}), no closing-rule "
        "effect, and no slope change at the band reform. On NIFTY 50, India VIX, an "
        "options-implied forecast unrelated to the daily bar's sampling error, identifies the "
        f"same slopes as the lagged realised measures (Parkinson {n['nifty_P_lag']} against "
        f"{n['nifty_P_vix']}), which corroborates the identification where it can be "
        "cross-checked."), "Normal")
    p3 = para_after(p2, (
        "What the test establishes is calibration relative to the open-to-close proxy. It "
        "cannot say whether the proxy itself measures efficient within-session variance, "
        "because every estimator in the comparison, and the proxy, reads the same opening "
        "price. That is the question of Section 6.7."), "Normal")
    pic = picture_after(p3, FIG / "fig22_calibration_masking.png", 6.0)
    cap7 = para_after(pic, (
        "Figure 7. Mean ratio to the open-to-close proxy against the instrumented calibration "
        "slope, by security-level liquidity quintile, for Parkinson, Garman-Klass and "
        "Rogers-Satchell; 95% stationary block-bootstrap intervals. A ratio and a slope are "
        "different quantities: the slope is identified from volatility persistence with "
        "instruments dated t-1 (Section 6.6). Generated by "
        "scripts/34_instrumented_calibration.py."), "Figure Caption")

    h7 = heading_after(cap7, "6.7 What the opening price measures: a pre-open band reform")
    q1 = para_after(h7, (
        "Every within-session estimator reads the opening price: the open-to-close proxy, "
        "Garman-Klass and Rogers-Satchell directly, and Parkinson whenever the open is the "
        "session's high or low. If the open carries a transient error, the estimators and "
        "their benchmark can agree because they share it, while the close-to-close return, "
        "which never reads the open, does not. That opening prices set by call auctions can be "
        "noisier than closing prices is long established (Amihud & Mendelson, 1987; Stoll & "
        "Whaley, 1990); how much of an opening price survives is measured in the "
        "price-discovery literature by the unbiasedness regression of the close-to-close return "
        "on the opening return (Biais, Hillion & Spatt, 1999; Barclay & Hendershott, 2003). Its "
        "slope, b = E[o r]/E[o²] with o = ln(O/C_prev) and r = ln(C/C_prev), equals one when "
        "the open anticipates the close. It falls below one when the session undoes part of "
        "the opening move, and rises above one when the session completes a move the open only "
        "began, as it should when a band truncates the open. Opens equal to the previous close "
        "contribute nothing to b, so it is unaffected by auctions that fail to match. The "
        "hypotheses and decision rules were frozen before any of these statistics was computed "
        "on the data, and the statistics were first checked on simulated panels where the truth "
        "is known."), "Normal")
    q2 = para_after(q1, (
        "NEPSE's opening price is mostly transient (Table 30). Under the ±2% pre-open band, b is "
        f"{n['b_A1']} {n['bci_A1']} with a last-trade close, {n['b_B']} {n['bci_B']} while the "
        f"close was a fifteen-minute VWAP, and {n['b_A2']} {n['bci_A2']} once the last-trade "
        f"close returned: the session undoes between {100 - round(100 * n['bv_A2'])}% and "
        f"{100 - round(100 * n['bv_B'])}% of the overnight move. On NIFTY 50, whose open comes "
        f"from a call auction among liquid constituents, b is {n['b_N']} {n['bci_N']}. The "
        "reversal is not confined to thin securities: b is below one in every security-level "
        f"liquidity quintile in every regime, between {n['liq_pre_lo']} and {n['liq_pre_hi']} "
        "under the ±2% band. It is also fast: of the "
        f"{n['undo_A1']} percentage points of the opening move undone in the first regime, "
        f"{n['early_A1']} are undone before the session's volume-weighted centre and "
        f"{n['late_A1']} after it."), "Normal")
    q3 = para_after(q2, (
        "On 20 April 2026 NEPSE widened the pre-open band from ±2% to ±5% and the daily limit "
        "from ±10% to ±15%, two weeks after moving to a Monday-Friday week. Over the 40 sessions "
        f"before the week reform b was {n['b_pre']}; over the 40 after the band reform it was "
        f"{n['b_post']}, a change of {n['jump']} {n['jump_ci']}. The {WORDS[n['n_gap']]} sessions between "
        f"the two reforms sit at {n['b_gap']}, with the earlier window, so the break belongs to "
        f"the band reform. None of {n['n_plac']} placebo splits of the two pre-reform years, "
        "including those straddling both closing-rule changes and the September 2025 market "
        f"halt, produces a change as large: the most negative is {n['plac_min']}. The frozen "
        "verdict is "
        "a sharp break (Table 31, Figure 8), and the jump is unchanged when the post-reform "
        f"window starts at its sixth session ({n['jump_late']}). The overnight-intraday reversal "
        f"E[o c]/E[P] lies between {n['m_pre_hi']} and {n['m_pre_lo']} in every full month "
        f"before the reform and between {n['m_post_hi']} and {n['m_post_lo']} in every full "
        "month after it."), "Normal")
    q4 = para_after(q3, (
        "The price-limit literature asks whether a binding limit delays the incorporation of "
        "information, in which case pinned opens are followed by continuation (Kim & Rhee, "
        "1997), or prevents an overreaction, in which case they are followed by reversal. The "
        "frozen test predicted delayed price discovery, and the data reject it: opens pinned at "
        f"the ±2% band were reversed like every other open (b = {n['b_pinned_A2']} "
        f"{n['bci_pinned_A2']} in the last pre-reform regime). After the widening, the opens "
        f"the old band would have pinned retain {n['b_old_band_zone_C']} "
        f"{n['bci_old_band_zone_C']} of their move and those pinned at the new band "
        f"{n['b_pinned_C']} {n['bci_pinned_C']}, while opens inside ±1.9% are unchanged "
        f"({n['b_interior_C']} against {n['b_interior_A2']}). In a post hoc tabulation, an open "
        f"pinned at the new upper band (mean {n['o_up5']}) is followed by an intraday return of "
        f"{n['c_up5']}, and the close retains {n['ret_up5']} {n['ret_up5_ci']} of the opening "
        "move: on average, the stock ends where it closed the previous session. The narrow band "
        "was capping transient opening moves, not holding back information, and widening it let "
        "the open travel further from where the session would close. Two qualifications bound "
        "this reading. The predicted dose-response, a larger effect for securities the old band "
        "bound more often, was not detected (difference-in-differences "
        f"{n['did']} {n['did_ci']}; from lowest to highest exposure, b fell from {n['terc_A2']} "
        f"to {n['terc_C']}), so the identification rests on timing alone. And the reform changed "
        "the "
        "band, the daily limit and the circuit breaker together, in a post-reform window of "
        f"{n['n_C']} sessions, so the evidence concerns that rule package rather than the band alone."),
        "Normal")
    q5 = para_after(q4, (
        "Three consequences follow for measurement. First, the exact identity YZ - Var(r) = "
        "(1 - k)[mean RS - Var(c)] - 2Cov(o, c) shows what Yang and Zhang's independence "
        f"assumption costs. Over all {n['n_yz_windows']} 21-session windows, Yang-Zhang is "
        f"{n['yz_all']} {n['yz_all_ci']} times the matched close-to-close variance, the "
        f"{n['yz_sd']} of Section 6.5 on the standard-deviation scale, and {n['cov_share']} "
        f"{n['cov_share_ci']} of the excess is the overnight-intraday covariance. The ratio "
        f"rises from {n['yz_A2']} to {n['yz_C']} across the reform (frozen verdict: "
        f"{n['v_H11']}), while on NIFTY 50 Yang-Zhang matches close-to-close ({n['yz_N']} "
        f"{n['yz_N_ci']}). Second, Parkinson inherits the open's error whenever the open is the "
        f"session's high or low, which a non-stale NEPSE open is on {n['ext_A1']} of sessions "
        f"in the first regime and {n['ext_C']} after the reform (post hoc). Third, a ratio to "
        "the open-to-close proxy cannot see this. Across the reform Parkinson's ratio to the "
        f"proxy moves from {n['P_OC_A2']} to {n['P_OC_C']}, a change of {n['dP_OC']} "
        f"{n['dP_OC_ci']} whose interval contains zero, while its ratio to the noise-robust "
        "kernel K = c² + oc + co′, the daily analogue of Zhou's (1996) first-order correction, "
        f"rises from {n['P_K_A2']} to {n['P_K_C']}, a change of {n['dP_K']} {n['dP_K_ci']} "
        "(Table 32). The frozen rule therefore "
        f"returns '{n['v_H10 (consequence)']}', but the asymmetry is the point. The kernel is "
        "unbiased only if the opening error is independent of overnight news, so its shares "
        "are estimates under that assumption. A post hoc bound that assumes nothing about that "
        f"correlation still puts the open's error at no less than {n['lb_A1']} of the "
        f"open-to-close proxy in the first regime and {n['lb_C']} {n['lb_C_ci']} after the "
        f"reform, against {n['ind_C']} if it is independent of news."), "Normal")
    q6 = para_after(q5, (
        "The close-to-close return is the one measure here that never reads the open, which is "
        "why it, rather than a range estimator, is the robust benchmark in a market whose "
        "opening auction overreacts. That is consistent with Section 6.3, where close-to-close "
        "is nominally ahead of Parkinson on every forward metric. It also accounts for the "
        "Yang-Zhang result of Section 6.5, which the earlier sections could only report: the "
        "distance from close-to-close is a property of NEPSE's opening price, not of the "
        "estimator's arithmetic."), "Normal")
    pic8 = picture_after(q6, FIG / "fig23_opening_price.png", 6.0)
    para_after(pic8, (
        "Figure 8. What the opening price anticipates. Panel A: the unbiasedness coefficient "
        "b = E[o r]/E[o²] by calendar month; Panel B: the overnight-intraday reversal "
        "E[o c]/E[P] by month; Panel C: b by tercile of pre-reform exposure to the band, before "
        "(A2) and after (C) the band reform; Panel D: the reform's jump in b against the "
        f"{n['n_plac']} placebo dates. Numbered lines mark the two closing-rule changes, the "
        "trading-week reform and, solid, the band reform; 95% stationary block-bootstrap "
        "intervals. Generated by scripts/37_opening_price.py."), "Figure Caption")
    print("  added Sections 6.6 and 6.7 with Figures 7 and 8")

    # ── Tables 29-32, after Table 28 ─────────────────────────────────────────────────────────
    doc.save(a.out)
    doc = docx.Document(a.out)
    anchor = spacer_after(table_of(doc, "Table 28."))
    for caption, csv_name in [
        ("Table 29. Calibration slopes against mean ratios: each estimator relative to the "
         "matched open-to-close proxy, instrumented by lagged realised measures (Section 6.6; "
         "plan M14, frozen before testing).", "paper_table29_calibration_slopes.csv"),
        ("Table 30. What the opening price anticipates: the unbiasedness coefficient of the open "
         "for the close by market-design regime and opening zone, with NIFTY 50 (Section 6.7; "
         "plan M15, frozen before testing).", "paper_table30_opening_unbiasedness.csv"),
        ("Table 31. The pre-open band reform as a natural experiment: the frozen M15 tests and "
         "their verdicts, applied mechanically.", "paper_table31_band_reform_tests.csv"),
        ("Table 32. What the open does to the estimators: Yang-Zhang's excess over matched "
         "close-to-close variance and the share of it that is the opening covariance, and "
         "Parkinson against the open-to-close proxy and against the noise-robust kernel. The "
         "post hoc columns are labelled.", "paper_table32_open_and_estimators.csv"),
    ]:
        t = pd.read_csv(TAB / csv_name, dtype=str).fillna("")
        cap = para_after(anchor, caption, "Normal")
        new_t = new_table_after(cap, doc, list(t.columns), t.values.tolist())
        set_repeat_header_row(new_t)
        anchor = spacer_after(new_t)
    print("  added Tables 29-32")

    # ── Section 7: the protocol ──────────────────────────────────────────────────────────────
    p = para_with(doc, "Compute at least two estimators. A practical pair is close-to-close")
    b1 = para_after(p, (
        "Diagnose the open before trusting any estimator that reads it. Report the unbiasedness "
        "coefficient b = E[o r]/E[o²] of the open for the close, by market-rule regime. In NEPSE "
        f"it lies between {n['b_C']} and {n['b_A2']}; on NIFTY 50 it is {n['b_N']}. Where b is "
        "well below one, the open-to-close proxy, Garman-Klass, Rogers-Satchell and Yang-Zhang "
        "all carry the open's transient error, and close-to-close variance is the benchmark."),
        p.style)
    para_after(b1, (
        "Treat a change in opening rules as a break. NEPSE's band widening moved every "
        "open-based quantity in this paper (Section 6.7); a volatility series that spans such "
        "a change should be split at it or built from close-to-close returns."), p.style)
    p = para_with(doc, "It should not be treated as interchangeable with close-to-close on that evidence.")
    replace_in(p, "It should not be treated as interchangeable with close-to-close on that evidence.",
               "It should not be treated as interchangeable with close-to-close on that "
               "evidence, and Section 6.7 shows why: three-quarters of the excess is the "
               "overnight-intraday covariance Yang and Zhang assume away.")
    replace_in(p, "We state no criterion-free ordering because these are deviations from an "
                  "imperfect proxy, classified against a stated (post hoc) margin, not accuracy "
                  "against latent variance.",
               "We state no criterion-free ordering because these are deviations from an "
               "imperfect proxy, classified against a stated (post hoc) margin, not accuracy "
               "against latent variance. Section 6.7 adds a condition to every recommendation "
               "above: each estimator that reads the open inherits its error, and NEPSE's "
               "opening price is mostly transient. The comparisons in this section are "
               "therefore comparisons among estimators that share that error; close-to-close "
               "does not share it, which is why it anchors the scale.")
    print("  revised the protocol (Section 7) and the estimator choice (Section 7.2)")

    # ── Discussion ───────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "The main result is more optimistic than the usual intuition")
    replace_in(p, "This is economically meaningful because it gives a low-data-cost approach to "
                  "risk measurement in a market where intraday databases and derivative prices "
                  "are not readily available.",
               "This is economically meaningful because it gives a low-data-cost approach to "
               "risk measurement in a market where intraday databases and derivative prices are "
               "not readily available. That benchmark, however, reads the opening price, and "
               "the open is where NEPSE's daily bar is least reliable.")
    p = para_with(doc, "At the same time, the study shows that frontier-market volatility")
    d1 = para_after(p, (
        "The opening price is the second main result, and it is less comfortable for the "
        "range-estimator literature than the first. Range-based estimators were derived for a "
        "continuously observed price path whose open is an efficient price (Garman & Klass, "
        "1980; Rogers & Satchell, 1991; Yang & Zhang, 2000). In NEPSE the open is mostly "
        f"transient: the session undoes {n['undo_lo']}% or more of the overnight move under "
        f"every rule regime, against {n['undo_N']}% on NIFTY 50. The estimators' agreement with "
        "the open-to-close proxy, which Section 6.6 shows to be calibration rather than "
        "cancellation, is therefore agreement among measures that share one error. Ratio "
        "comparisons cannot see it, including the ones in earlier versions of this paper. "
        "The diagnostic that exposes it, the unbiasedness coefficient of the open, needs "
        "nothing beyond the daily bar, so it can be computed wherever these estimators are "
        "used."), "Normal")
    para_after(d1, (
        "The band reform adds a market-design reading. Price limits are defended as a check on "
        "overreaction and criticised for delaying price discovery (Kim & Rhee, 1997). At "
        "NEPSE's opening auction the ±2% band showed no sign of the second cost: the opens it "
        "pinned were reversed, not continued. Widening it let transient opening moves grow, "
        "and a stock opening at the new upper band closed, on average, where it had closed the "
        f"day before. That is evidence about one rule package in one market over {n['n_C']} sessions, "
        "with the daily limit and the circuit breaker changed on the same date, and it says "
        "nothing about welfare. But it is the kind of evidence a regulator weighing the width "
        "of a pre-open band would want, and it can be updated as the post-reform sample "
        "grows."), "Normal")
    print("  added two Discussion paragraphs")

    # ── Section 9 ────────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "For input provenance, the package contains a processed-data BUILD-MANIFEST")
    para_after(p, (
        "Two further analyses were run under plans frozen and committed before their results "
        "existed, in the same manner as the forward India VIX test: the instrumented "
        "calibration of Section 6.6 (plan M14; scripts 34 and 36, with the Monte Carlo "
        "validation in script 35) and the opening-price analysis of Section 6.7 (plan M15; "
        "script 37, with its statistics validated on simulated panels in the test suite). Their "
        "decision rules are applied mechanically and written to decision ledgers. Their post "
        "hoc follow-ups are confined to separately labelled scripts (36 and 38). Every change "
        "made after their first results were seen is recorded in the audit register, including "
        "two readings of the calibration results that the opening-price analysis later "
        "overturned."), "Normal")

    # ── Limitations ──────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "Several limitations should keep the conclusions appropriately narrow.")
    replace_in(p, "rather than claiming that the true latent variance is known.",
               "rather than claiming that the true latent variance is known. Section 6.7 shows "
               "that the proxy is imperfect in one specific, measurable way: it reads an "
               "opening price that the session mostly reverses.")
    p = para_with(doc, "Second, market institutions constrain how prices are formed and recorded.")
    replace_in(p, "is excluded from the reported results.",
               "is excluded from the reported results. Section 6.7 measures what the opening "
               "price anticipates rather than what it would have been, but without pre-open "
               "order-book or auction-volume data it cannot say whether the transient error "
               "reflects retail overreaction, a thin pre-open match setting the print, or "
               "orders placed at the band by design.")
    p = para_with(doc, "Third, the market changed during the sample, including a 2026 trading-week")
    set_text(p, (
        "Third, the market changed during the sample. Sections 6.6 and 6.7 model the "
        "closing-rule and band regimes explicitly, but the post-reform regime contains only "
        f"{n['n_C']} sessions, and the band reform changed the pre-open band, the daily limit and the "
        "circuit breaker on one date, two weeks after a trading-week reform. The evidence "
        "concerns that rule package, and its dose-response leg was not detected."))
    p = para_with(doc, "whose own measurement error is not modelled here.")
    replace_in(p, "whose own measurement error is not modelled here.",
               "whose own measurement error Section 6.7 bounds but cannot fully identify.")
    p = para_with(doc, "a reader should not treat scale agreement as a stand-in for information content.")
    l13 = para_after(p, (
        "Thirteenth, the calibration slopes of Section 6.6 are linear-projection slopes on "
        "predictable variance, relative to the open-to-close proxy. The single-index restriction "
        "behind them is rejected by an overidentification test in the pooled sample, though not "
        "once the additive component may differ by market regime (a post hoc check). They "
        "establish calibration relative to the proxy, not accuracy relative to latent "
        "variance."), "Normal")
    para_after(l13, (
        "Fourteenth, the noise-robust kernel of Section 6.7 is unbiased only if the opening "
        "error is independent of overnight news: censoring biases it upward and news-"
        "proportional overreaction biases it downward. The kernel-based shares are therefore "
        "estimates under that assumption, and the bound reported beside them, which does not "
        "need it, is post hoc."), "Normal")
    k = renumber_limitations(doc)
    print(f"  revised and extended the limitations (now {k})")

    # ── Conclusion ───────────────────────────────────────────────────────────────────────────
    p = para_with(doc, "The NEPSE evidence shows that this is practical for the great majority")
    para_after(p, (
        "The paper's second finding qualifies its first. The opening price, which every "
        "within-session estimator and the open-to-close proxy read, is mostly transient in "
        f"NEPSE: the trading session undoes between {n['undo_lo']}% and {n['undo_hi']}% of the "
        f"overnight move, against {n['undo_N']}% on NIFTY 50. A natural experiment analysed "
        "under a frozen plan ties part of this to market design. Widening the pre-open band from "
        "±2% to ±5% produced a sharp break in how much of the open survives to the close, "
        "larger than at any placebo date, and the opens pinned at the old band had been "
        "reversed rather than continued. The open's error accounts for three-quarters of "
        "Yang-Zhang's excess over close-to-close variance. It leaves the range estimators' "
        "calibration to their benchmark intact but uninformative about efficient variance."),
        "Normal")
    p = para_with(doc, "The claims should stop there, including the claim to novelty.")
    replace_in(p, "so nothing here introduces security-level volatility analysis to Nepal; what it "
                  "contributes is a reproducible comparison of daily OHLC estimators under this "
                  "market's own calendar, staleness, thin-trading and closing-rule constraints.",
               "so no claim is made to introduce security-level volatility analysis to Nepal. "
               "What the paper contributes is a reproducible comparison of daily OHLC "
               "estimators under this market's own calendar, staleness, thin-trading and "
               "closing-rule constraints, a test that separates calibration from offsetting "
               "distortions, and evidence that the market's opening rules shape what its daily "
               "bars measure.")
    replace_in(p, "and justify any bias correction in the target sample before applying it.",
               "and justify any bias correction in the target sample before applying it; and, "
               "before trusting any estimator that reads the opening price, measure how much of "
               "that price survives to the close.")
    print("  revised the Conclusion")

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
    assert len(doc.tables) == 32, f"expected 32 tables, found {len(doc.tables)}"
    assert len(doc.inline_shapes) == 8, f"expected 8 figures, found {len(doc.inline_shapes)}"
    for needle in ("6.6 Calibration slopes", "6.7 What the opening price measures",
                   "Figure 7.", "Figure 8.", "Table 29.", "Table 30.", "Table 31.", "Table 32.",
                   "no claim is made to introduce security-level",
                   "makes no claim to introduce security-level",
                   "addresses a measurement question not identified in the targeted search",
                   "Christensen and Prabhala (1998)", "Hansen and Lunde (2014)",
                   "Biais, Hillion & Spatt, 1999", "Barclay & Hendershott, 2003",
                   "Kim & Rhee, 1997", "Zhou's (1996)", "Arellano & Bover"):
        assert needle in body, f"missing after round 14: {needle!r}"
    # every frozen verdict quoted is the ledger's
    assert n["v_H7"] == "sharp break" and "sharp break" in body
    assert n["v_H11"] in body and n["v_H10 (consequence)"] in body
    # post hoc results are labelled where they are quoted
    for sentence in re.split(r"(?<=[.!?])\s+", body):
        if ("no less than" in sentence and "open's error" in sentence) or "off the exchange's" in sentence:
            assert "post hoc" in sentence, f"unlabelled post hoc result: {sentence[:90]!r}"
    # the numbers this script interpolated are present
    for key in ("P_slope", "AddRS_slope", "b_A1", "b_B", "b_A2", "b_N", "jump", "b_pre",
                "b_post", "yz_all", "dP_K", "lb_C"):
        assert n[key] in body, f"interpolated figure missing: {key} = {n[key]}"
    # the limitations run contiguously
    i = find(paras, "Several limitations")
    j = find(paras, "11. Conclusion", i)
    found = [p.text.split(",")[0] for p in paras[i + 1:j] if p.text.split(",")[0] in ORDINALS]
    assert found == ORDINALS[1:len(found) + 1], f"limitation ordinals out of order: {found}"
    i_refs = next(k for k, p in enumerate(paras) if p.text.strip() == "References")
    j_refs = find(paras, "Data and reproducibility note", i_refs)
    refs = [p.text for p in paras[i_refs + 1:j_refs] if p.text.strip()]
    keys = [re.sub(r"^(The )", "", r).lower() for r in refs]
    assert keys == sorted(keys), "reference list is not alphabetical"
    print(f"verification: {len(doc.tables)} tables, {len(doc.inline_shapes)} figures, "
          f"{len(refs)} references; no banned phrase; post hoc results labelled")


if __name__ == "__main__":
    main()
