"""Every part of every proposition, and every step of every proof, in the theory supplement has a
verified row in ``output/tables/table124_theory_proof_steps.csv``, written by
``scripts/46_theory_proofs.py``, and every row passes.

The parts and steps are read from the LaTeX itself, so a proposition part or a proof step added
later without a verification fails here. A few symbolic steps are re-derived directly, so the
ledger cannot pass on stale rows alone.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"
TH = ROOT / "paper" / "theory"
GEN = TH / "generated"
METHODS = {"symbolic", "symbolic-50dp", "numerical", "Monte Carlo", "pathwise", "data"}


def steps() -> pd.DataFrame:
    return pd.read_csv(TAB / "table124_theory_proof_steps.csv", dtype=str, keep_default_na=False).assign(
        **{"pass": lambda d: d["pass"] == "True"})


def proposition_parts() -> dict[str, list[str]]:
    """{proposition: [part letters]}, from the top-level items of each proposition's enumerate lists."""
    text = (TH / "section_theory.tex").read_text()
    out = {}
    for i, body in enumerate(re.findall(r"\\begin\{proposition\}(.*?)\\end\{proposition\}", text, re.S), start=1):
        enum = item = n = 0
        for tok in re.findall(r"\\begin\{enumerate\}|\\end\{enumerate\}|\\begin\{itemize\}|\\end\{itemize\}|\\item\b", body):
            if tok == r"\begin{enumerate}":
                enum += 1
            elif tok == r"\end{enumerate}":
                enum -= 1
            elif tok == r"\begin{itemize}":
                item += 1
            elif tok == r"\end{itemize}":
                item -= 1
            elif enum and not item:
                n += 1
        out[str(i)] = [chr(ord("a") + j) for j in range(n)]
    return out


def appendix_parts() -> dict[str, set[str]]:
    """{B.k: labels}, from the \\emph{(x)...} paragraph labels of each proof."""
    text = (TH / "appendix_proofs.tex").read_text()
    out = {}
    for sec, body in re.findall(r"\\subsection\*\{(B\.\d) Proof[^}]*\}\}?(.*?)(?=\\subsection\*|\Z)", text, re.S):
        labels = set(re.findall(r"\\emph\{\(([a-g])\)", body))
        if r"\emph{The published bound.}" in body:
            labels.add("bound")
        out[sec] = labels
    return out


def test_every_step_passes_and_says_how_it_was_verified():
    t = steps()
    assert len(t) >= 200
    assert t["pass"].all(), t[~t["pass"]][["proposition", "part", "step"]].to_string()
    assert set(t["method"]) <= METHODS
    assert (t["method"].isin(["symbolic", "symbolic-50dp"])).sum() >= 100, "the algebra is verified symbolically"
    assert (t["detail"].str.len() > 0).sum() >= len(t) - 20


def test_every_part_of_every_proposition_is_verified():
    parts = proposition_parts()
    assert parts == {"1": list("abcde"), "2": list("abcdefg"), "3": list("abcd"), "4": list("abcd"),
                     "5": list("abc"), "6": list("abcde"), "7": list("abc")}, parts
    have = set(zip(steps()["proposition"], steps()["part"]))
    missing = [(p, x) for p, xs in parts.items() for x in xs if (p, x) not in have]
    assert not missing, f"proposition parts without a verified step: {missing}"


def test_every_step_of_every_proof_is_verified():
    parts = appendix_parts()
    assert set(parts) == {"B.1", "B.2", "B.3", "B.4", "B.5", "B.6", "B.7"}, parts
    assert parts["B.1"] >= {"a", "b", "c", "d", "e", "bound"} and parts["B.2"] >= set("abcdefg")
    assert parts["B.7"] == {"a", "b", "c"}
    have = set(zip(steps()["appendix"], steps()["appendix_part"]))
    missing = [(s, x) for s, xs in parts.items() for x in sorted(xs) if (s, x) not in have]
    assert not missing, f"proof steps without a verified row: {missing}"


def test_the_papers_own_claims_are_verified():
    t = steps()
    paper = t[t["proposition"] == "paper"]
    for part in ("4.3", "4.5", "6.7", "6.8", "Appendix A", "M15"):
        assert (paper["part"] == part).any(), part
    assert (paper["method"] == "data").sum() >= 4, "the kernel's special cases and the identities hold on the data"


def macros(path) -> dict[str, str]:
    out = {}
    for line in path.read_text().splitlines():
        if "\\csname thn@" in line:
            key = line.split("thn@", 1)[1].split("\\endcsname", 1)[0]
            out[key] = line.split("\\endcsname{", 1)[1][:-1]
    return out


def test_the_generated_counts_match_the_ledger():
    t = steps()
    m = {k: int(v.replace("{,}", "")) for k, v in macros(GEN / "proofs.tex").items()}
    assert m["proofs-n"] == len(t) and m["proofs-pass"] == int(t["pass"].sum()) and m["proofs-fail"] == 0
    assert m["proofs-symbolic"] == int(t["method"].isin(["symbolic", "symbolic-50dp"]).sum())
    assert m["proofs-sym50"] == int((t["method"] == "symbolic-50dp").sum())
    assert m["proofs-mc"] == int((t["method"] == "Monte Carlo").sum())
    assert sum(m[k] for k in ("proofs-symbolic", "proofs-numerical", "proofs-mc", "proofs-path", "proofs-data")) == len(t)


def test_the_manuscript_cites_the_verification_and_states_the_exact_condition():
    docx = pytest.importorskip("docx")
    body = "\n".join(p.text for p in docx.Document(
        ROOT / "paper" / "NEPSE_Volatility_Manuscript_Revised_2026-09.docx").paragraphs)
    t = steps()
    nsym = int(t["method"].isin(["symbolic", "symbolic-50dp"]).sum())
    assert f"({len(t)} steps, {nsym} of them symbolic, all passing)" in body
    assert "It is attained exactly when o* = b o, which for b > 0 means that η is proportional to o*" in body
    assert "It is attained exactly when η is proportional to o*, and" not in body
    reg = (ROOT / "AUDIT-REGISTER.md").read_text()
    assert "| `M-027` |" in reg


@pytest.fixture(scope="module")
def s46():
    pytest.importorskip("sympy")
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("s46_under_test", ROOT / "scripts" / "46_theory_proofs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_symbolic_steps_rederive(s46):
    sp = s46.sp
    k, z = s46.kp, s46.z
    stein = sp.integrate(z ** 2 * s46.phi(z), (z, -k, k)) + 2 * k * sp.integrate(z * s46.phi(z), (z, k, sp.oo))
    assert s46.zero(stein - (2 * s46.PHI(k) - 1))[0]
    r = s46.rp
    t1 = ((1 + r ** 2) * sp.atan(r) - r) / sp.pi
    assert s46.zero(sp.limit((r ** 2 / 2 - t1) / r ** 2, r, 0) - sp.Rational(1, 2))[0]
    L = sp.symbols("L", integer=True, positive=True)
    j = sp.symbols("j", integer=True, nonnegative=True)
    assert s46.zero(sp.summation((1 - (j + 1) / L) ** 2, (j, 0, L - 1)) - (L - 1) * (2 * L - 1) / (6 * L))[0]
    b = sp.symbols("b", real=True)
    assert s46.zero((3 - 2 * b) ** 2 - (5 - 4 * b) - 4 * (1 - b) ** 2)[0]


def test_the_zero_test_rejects_a_false_identity(s46):
    sp = s46.sp
    x = sp.symbols("x", positive=True)
    ok, _, _ = s46.zero(sp.atan(x) - x / (1 + x ** 2))
    assert not ok
