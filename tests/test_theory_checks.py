"""The theory supplement (paper/theory/) and its checks (plan M19, scripts/45_theory_checks.py; Proposition 7,
added after the 9 October 2026 audit, scripts/48_kernel_theory.py).

The full check run takes minutes, and its Part C needs the third-party frontier inputs. These tests
therefore read the committed outputs. They also re-verify the inexpensive closed forms directly, and
check that every number the LaTeX quotes is a generated macro, that the frozen verdicts follow
M19's rules, and that the round-17 correction of Appendix A is in the manuscript.
"""
from __future__ import annotations

import importlib.util
import math
import pathlib
import re
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"
TH = ROOT / "paper" / "theory"
GEN = TH / "generated"


@pytest.fixture(scope="module")
def s45():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("s45_under_test", ROOT / "scripts" / "45_theory_checks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def numbers() -> dict[str, str]:
    """The generated macros: script 45's numbers and script 46's step counts."""
    pat = re.compile(r"\\csname thn@(.+?)\\endcsname\{(.*)\}$")
    out = {}
    for f in ("numbers.tex", "proofs.tex", "kernel.tex"):
        for line in (GEN / f).read_text().splitlines():
            m = pat.search(line)
            if m:
                out[m.group(1)] = m.group(2)
    return out


def num(v: str) -> float:
    return float(v.replace(r"\ensuremath{-}", "-").replace("{,}", ""))


# ── Part A ledger ──────────────────────────────────────────────────────────────────────────────

def test_every_check_of_the_six_propositions_passes():
    led = pd.read_csv(TAB / "table121_theory_checks.csv")
    assert len(led) >= 150
    assert set(led["proposition"].astype(str)) == {"1", "2", "3", "4", "5", "6"}
    assert led["pass"].all(), led[~led["pass"]][["proposition", "check", "design"]].to_string()
    mc = led[led["rule"].str.startswith("|value - theory|")]
    assert len(mc) > 50 and (mc["se"] > 0).all(), "every Monte Carlo comparison carries its standard error"


# ── closed forms, re-verified directly ─────────────────────────────────────────────────────────

def test_censoring_factor_matches_its_definition_and_decreases(s45):
    from scipy import integrate
    from scipy.stats import norm
    for k in (0.5, 1.1, 2.0):
        g = lambda z: max(-k, min(k, z))
        num_ = integrate.quad(lambda z: g(z) * z * norm.pdf(z), -12, 12, points=[-k, k])[0]
        den = integrate.quad(lambda z: g(z) ** 2 * norm.pdf(z), -12, 12, points=[-k, k])[0]
        assert s45.F_gauss(k) == pytest.approx(num_ / den, rel=1e-9)
    ks = np.linspace(0.05, 5, 300)
    assert (np.diff(s45.F_gauss(ks)) < 0).all()


def test_rogers_satchell_and_extreme_closed_forms(s45):
    for r in (0.1, 0.5, 1.0, 3.0):
        assert s45.bias_RS(r) == pytest.approx(r * r / 2 - s45.t1(r), abs=1e-14)
        assert s45.p_extreme(r) == pytest.approx(2 * math.atan(r) / math.pi)
    assert s45.p_extreme(1.0) == pytest.approx(0.5)


def test_parkinson_absorbs_half_the_error_variance_when_it_is_small(s45):
    r = 0.1
    assert s45.delta_R(r) / (2 * math.log(2) * r * r) == pytest.approx(1.0, abs=2e-3)
    assert 0 <= s45.delta_R(1.0) <= 8 / math.pi + 1.0


def test_sharp_bound_beats_the_published_one(s45):
    for b in np.linspace(0, 0.99, 100):
        assert (1 - b) ** 2 > s45.g_appendix_a(b)


# ── every number in the LaTeX is generated ─────────────────────────────────────────────────────

def test_every_number_the_latex_quotes_is_defined():
    defined = numbers()
    used = set()
    for f in ("theory.tex", "section_theory.tex", "appendix_proofs.tex"):
        text = "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in (TH / f).read_text().splitlines())
        used |= set(re.findall(r"\\thn\{([^}]+)\}", text))
    assert used, "the LaTeX quotes no generated numbers"
    missing = sorted(used - set(defined))
    assert not missing, f"undefined generated numbers: {missing}"
    for frag in ("tab_bounds.tex", "tab_censoring.tex", "tab_checks.tex", "tab_pooling.tex", "tab_proofs.tex",
                 "tab_kernel.tex"):
        assert (GEN / frag).exists(), frag


def test_generated_numbers_equal_the_tables():
    n = numbers()
    led = pd.read_csv(TAB / "table121_theory_checks.csv")
    ap = pd.read_csv(TAB / "table122_theory_applications.csv")
    pool = pd.read_csv(TAB / "table123_theory_pooling.csv")
    assert n["checks-n"] == str(len(led)) and n["checks-pass"] == str(int(led["pass"].sum()))
    v = ap[(ap.part == "B1") & (ap["sample"] == "NEPSE A1") & (ap.statistic.str.startswith("sharp"))]["value"].iloc[0]
    assert num(n["b1-A1-sharp"]) == pytest.approx(round(v, 3))
    assert n["c-p4b"] == pool["P4b_overall"].iloc[0] and n["c-p4a"] == pool["P4a_overall"].iloc[0]
    assert n["c-n-confirmed"] == str(int((pool.P4b_verdict == "confirmed").sum()))


# ── Part B and Part C follow the frozen plan ──────────────────────────────────────────────────

def test_the_published_bound_is_reproduced_before_it_is_sharpened():
    ap = pd.read_csv(TAB / "table122_theory_applications.csv")
    t97 = pd.read_csv(TAB / "table97_m15_posthoc.csv")
    for reg in ("A1", "B", "A2", "C"):
        pub = ap[(ap["sample"] == f"NEPSE {reg}") & ap.statistic.str.startswith("published")]["value"].iloc[0]
        sharp = ap[(ap["sample"] == f"NEPSE {reg}") & ap.statistic.str.startswith("sharp")]["value"].iloc[0]
        ref = t97[(t97.regime == reg) & (t97.statistic == "lower bound on E[eta^2]/E[OC], any correlation with news")]["value"].iloc[0]
        assert pub == pytest.approx(ref, abs=1e-9)
        assert sharp > pub


def test_the_decomposition_of_the_fall_in_b_adds_up():
    ap = pd.read_csv(TAB / "table122_theory_applications.csv")
    d = ap[(ap.part == "B3") & (ap["sample"] == "NEPSE A2 -> C")].set_index("statistic")["value"]
    assert len(d) == 4
    assert d.drop("ln(b_A2/b_C)").sum() == pytest.approx(d["ln(b_A2/b_C)"], abs=1e-9)   # tables keep 10 digits


def test_pooling_verdicts_follow_the_frozen_rules():
    pool = pd.read_csv(TAB / "table123_theory_pooling.csv")
    assert len(pool) == 10
    for r in pool.itertuples():
        want = "confirmed" if r.hi < 0 else ("reversed" if r.lo > 0 else "not detected")
        assert r.P4b_verdict == want
        assert r.d_total == pytest.approx(r.d_level + r.d_shape, abs=1e-9)    # tables keep 10 digits
    conf, rev = (pool.P4b_verdict == "confirmed").sum(), (pool.P4b_verdict == "reversed").sum()
    assert pool.P4b_overall.iloc[0] == ("supported" if conf > len(pool) / 2 and rev == 0 else "not supported")
    pos = pool[pool.d_total > 0]
    held = (pos.P4a_mechanism == "level advantage").sum()
    want = "supported" if held == len(pos) else ("partly supported" if held > len(pos) / 2 else "not supported")
    assert pool.P4a_overall.iloc[0] == want


def test_the_plan_was_committed_before_the_script():
    if not (ROOT / ".git").exists() or shutil.which("git") is None:
        pytest.skip("no git history")
    def first(path):
        out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%H", "--", path], cwd=ROOT,
                             capture_output=True, text=True).stdout.split()
        return out[-1] if out else None
    plan, script = first("M19_THEORY_CHECKS_PLAN.md"), first("scripts/45_theory_checks.py")
    if plan is None or script is None:
        pytest.skip("not yet committed")
    assert plan != script, "the plan and the script were added in the same commit"
    assert subprocess.run(["git", "merge-base", "--is-ancestor", plan, script], cwd=ROOT).returncode == 0


# ── the correction of Appendix A (M-026) ──────────────────────────────────────────────────────

def test_appendix_a_is_corrected_in_the_manuscript_and_the_register():
    docx = pytest.importorskip("docx")
    body = "\n".join(p.text for p in docx.Document(
        ROOT / "paper" / "NEPSE_Volatility_Manuscript_Revised_2026-09.docx").paragraphs)
    assert "It is attained when η is perfectly correlated" not in body
    assert "E[η²] = (1 - b)²E[o²] + E[(o* - b o)²] ≥ (1 - b)²E[o²]" in body
    ap = pd.read_csv(TAB / "table122_theory_applications.csv")
    sharp = ap[(ap["sample"] == "NEPSE A1") & ap.statistic.str.startswith("sharp")]["value"].iloc[0]
    pub = ap[(ap["sample"] == "NEPSE A1") & ap.statistic.str.startswith("published")]["value"].iloc[0]
    assert f"{100 * sharp:.1f}%" in body
    reg = (ROOT / "AUDIT-REGISTER.md").read_text()
    row = next(line for line in reg.splitlines() if line.startswith("| `M-026`"))
    assert f"{100 * sharp:.1f}% of the open-to-close proxy against {100 * pub:.1f}%" in row
    readme = (ROOT / "README.md").read_text()
    led = pd.read_csv(TAB / "table121_theory_checks.csv")
    assert f"({len(led)} checks, all passing)" in readme


@pytest.mark.skipif(shutil.which("pdflatex") is None or shutil.which("bibtex") is None, reason="no TeX installation")
def test_the_latex_compiles(tmp_path):
    work = tmp_path / "theory"
    shutil.copytree(TH, work, ignore=shutil.ignore_patterns("*.pdf", "*.aux", "*.log", "*.bbl", "*.blg"))
    run = lambda *cmd: subprocess.run(cmd, cwd=work, capture_output=True, text=True)
    r = run("pdflatex", "-interaction=nonstopmode", "-halt-on-error", "theory.tex")
    assert r.returncode == 0, r.stdout[-3000:]
    run("bibtex", "theory")
    run("pdflatex", "-interaction=nonstopmode", "-halt-on-error", "theory.tex")
    r = run("pdflatex", "-interaction=nonstopmode", "-halt-on-error", "theory.tex")
    assert r.returncode == 0, r.stdout[-3000:]
    log = (work / "theory.log").read_text(errors="ignore")
    assert not re.search(r"Citation `[^']+' on page \d+ undefined", log), "undefined citations"
    assert not re.search(r"Reference `[^']+' on page \d+ undefined", log), "undefined references"
    assert "There were undefined references" not in log


def test_the_results_document_quotes_the_tables():
    doc = (ROOT / "M19_THEORY_CHECKS_RESULTS.md").read_text()
    led = pd.read_csv(TAB / "table121_theory_checks.csv")
    ap = pd.read_csv(TAB / "table122_theory_applications.csv")
    pool = pd.read_csv(TAB / "table123_theory_pooling.csv")
    assert f"All {len(led)} checks pass" in doc
    r = ap[(ap["sample"] == "NEPSE A1") & ap.statistic.str.startswith("sharp")].iloc[0]
    assert f"{100 * r.value:.1f}% [{100 * r.lo:.1f}%, {100 * r.hi:.1f}%]" in doc
    for x in pool.itertuples():
        assert f"| {x.n_with_b} | {x.d_total:.4f} |" in doc
    assert f"**P4a (mechanism): {pool.P4a_overall.iloc[0]}.**" in doc
    assert f"**P4b (cross-section): {pool.P4b_overall.iloc[0]}.**" in doc


# ── Proposition 7 (post hoc, after the audit): scripts/48_kernel_theory.py ─────────────────────────

@pytest.fixture(scope="module")
def s48():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("s48_under_test", ROOT / "scripts" / "48_kernel_theory.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_check_of_proposition_7_passes_and_the_macros_match():
    led = pd.read_csv(TAB / "table133_theory_kernel_checks.csv")
    assert len(led) >= 50 and led["pass"].all(), led[~led["pass"]][["check", "design"]].to_string()
    assert set(led["proposition"].astype(str)) == {"7"}
    n = numbers()
    assert n["k7-checks-n"] == str(len(led)) and n["k7-checks-pass"] == str(int(led["pass"].sum()))
    ex = pd.read_csv(TAB / "table134_theory_kernel_exposure.csv")
    C = ex[ex["part"] == "C"].dropna(subset=["s"])
    assert num(n["k7-xOF-min"]) == pytest.approx(round(C["exact_open_free"].min(), 2))
    assert num(n["k7-xOF-max"]) == pytest.approx(round(C["exact_open_free"].max(), 2))


def test_the_true_range_loading_closed_form(s48):
    # the meander's mean, the limits and the bounds of gamma_TR, re-derived directly
    assert s48.meander_mean() == pytest.approx(math.sqrt(2 * math.pi) * math.log(2), rel=1e-9)
    assert s48.gamma_tr(1e-4) == pytest.approx(0.25, abs=1e-7)
    for s in (0.2, 1.0, 5.0):
        g = s48.gamma_tr(s)
        assert max(0.25, s / (4 * math.pi * math.log(2))) - 1e-12 <= g <= 0.25 + s / (4 * math.pi * math.log(2)) + 1e-12
    assert s48.gamma_tr(2.0) > s48.gamma_tr(1.0) > s48.gamma_tr(0.5)


def test_the_audit_bar_is_contaminated_through_the_high():
    # C_- = C = L = 100, O = H = 105, b = 0: the extended range keeps the erroneous high
    h, l, b, o = math.log(1.05), 0.0, 0.0, math.log(1.05)
    Rs = max(h, b * o) - min(l, b * o)
    assert Rs == pytest.approx(math.log(1.05))
    n = numbers()
    assert num(n["k7-ex-kernel"]) == pytest.approx(round(0.8 * Rs ** 2 / (4 * math.log(2)) * 1e4, 2))
