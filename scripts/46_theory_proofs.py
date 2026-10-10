"""Step-by-step verification of every proof in the theory supplement (paper/theory/), and of the
mathematical claims the paper makes elsewhere.

``scripts/45_theory_checks.py`` (plan M19) set each proposition's closed forms against simulation.
This script goes through the propositions part by part and Appendix B step by step. It writes one
row per step to ``output/tables/table124_theory_proof_steps.csv``, recording how the step was
verified:

  symbolic        SymPy reduces (left side - right side) to zero, or establishes the inequality
  symbolic-50dp   SymPy builds both sides exactly but its simplifier does not close; the
                  difference is then evaluated to 60 significant digits at 12 random points and must
                  vanish to 50
  numerical       quadrature or series, within a stated tolerance
  Monte Carlo     simulation, within four standard errors; Brownian extremes are drawn exactly from
                  the Brownian bridge within each step
  pathwise        an identity checked on every simulated path, to floating-point precision
  data            an identity checked on every NEPSE stock-day it applies to

Steps that invoke a theorem from the literature are verified where the proof uses them:
  * the reflection principle and the method of images, by simulation;
  * the convergence of Brownian motion conditioned on M < s to a meander, and the meander's mean
    maximum, by the series and by simulation;
  * generalised method of moments asymptotics, by the simulations of script 45.

The paper's own mathematical claims outside the supplement are verified too:
  * the Yang-Zhang identity of Section 6.7;
  * the non-negativity of Garman-Klass on a valid bar;
  * the special cases of Anam's kernel;
  * the old and the corrected Appendix A;
  * the M14 measurement-model algebra and the M15 maintained model.

Outputs
    output/tables/table124_theory_proof_steps.csv
    paper/theory/generated/proofs.tex          (the macros \\thn{proofs-*} the LaTeX quotes)
    paper/theory/generated/tab_proofs.tex      (steps by proposition and method)

Usage
    python scripts/46_theory_proofs.py            # about three minutes
    python scripts/46_theory_proofs.py --quick    # smaller simulations, no data checks
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap(["scipy", "sympy"])

import argparse
import importlib.util
import math
import random
import sys
import time
import warnings

import numpy as np
import pandas as pd
import sympy as sp
from scipy import integrate
from scipy.stats import norm

TAB = ROOT / "output" / "tables"
GEN = ROOT / "paper" / "theory" / "generated"
SEED = 20261010
LN2 = math.log(2.0)
FLOAT_FMT = "%.10g"


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


s45 = _load("s45_for_46", "45_theory_checks.py")


# =============================================================================================
# Ledger and symbolic helpers
# =============================================================================================

class Steps:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, prop: str, part: str, app: str, app_part: str, step: str, method: str, ok: bool,
            detail: str = "") -> None:
        self.rows.append({"proposition": prop, "part": part, "appendix": app, "appendix_part": app_part,
                          "step": step, "method": method, "detail": detail, "pass": bool(ok)})

    def sym(self, prop, part, app, app_part, step, lhs, rhs=0, ranges=None):
        if isinstance(rhs, dict):              # sym(..., lhs, {ranges}) for a one-sided identity
            ranges, rhs = rhs, 0
        if isinstance(rhs, int) and rhs == 0:
            diff = lhs
        else:
            diff = lhs - rhs
        ok, how, method = zero(diff, ranges)
        self.add(prop, part, app, app_part, step, method, ok, how)

    def mc(self, prop, part, app, app_part, step, theory, value, se, k=4.0):
        ok = abs(value - theory) <= k * se
        self.add(prop, part, app, app_part, step, "Monte Carlo", ok,
                 f"theory {theory:.6g}, simulated {value:.6g} (SE {se:.2g})")

    def num(self, prop, part, app, app_part, step, theory, value, tol):
        ok = abs(value - theory) <= tol
        self.add(prop, part, app, app_part, step, "numerical", ok,
                 f"target {theory:.10g}, computed {value:.10g}, tolerance {tol:g}")

    def path(self, prop, part, app, app_part, step, residual: np.ndarray, tol=1e-11):
        worst = float(np.max(np.abs(residual))) if len(residual) else 0.0
        self.add(prop, part, app, app_part, step, "pathwise", worst <= tol,
                 f"max |residual| over {len(residual):,} paths = {worst:.1e}")

    def data(self, prop, part, app, app_part, step, residual: np.ndarray, tol=1e-12, n_label="stock-days"):
        residual = residual[np.isfinite(residual)]
        worst = float(np.max(np.abs(residual))) if len(residual) else np.inf
        self.add(prop, part, app, app_part, step, "data", worst <= tol,
                 f"max |residual| over {len(residual):,} {n_label} = {worst:.1e}")

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def zero(expr, ranges=None):
    """(ok, detail, method): does ``expr`` vanish identically? Matrices are checked entry by entry."""
    if isinstance(expr, sp.MatrixBase):
        res = [zero(e, ranges) for e in expr]
        method = "symbolic" if all(r[2] == "symbolic" for r in res) else "symbolic-50dp"
        return all(r[0] for r in res), "; ".join(sorted({r[1] for r in res})), method
    expr = sp.sympify(expr)
    if expr == 0:
        return True, "simplifies to 0", "symbolic"
    for f in (sp.simplify, lambda z: sp.simplify(sp.expand(z)), sp.trigsimp, sp.cancel,
              lambda z: sp.simplify(sp.expand_log(z, force=True)), lambda z: sp.simplify(sp.radsimp(z))):
        try:
            if f(expr) == 0:
                return True, "simplifies to 0", "symbolic"
        except Exception:  # noqa: BLE001 -- a simplifier that fails is simply not used
            pass
    free = sorted(expr.free_symbols, key=str)
    rng = random.Random(SEED)
    ranges = ranges or {}
    worst = sp.Integer(0)
    for _ in range(12):
        subs = {}
        for s in free:
            lo, hi = ranges.get(str(s), (0.05, 3.0))
            subs[s] = sp.Rational(round((lo + (hi - lo) * rng.random()) * 10**6), 10**6)
        val = abs(sp.N(expr.subs(subs), 60))
        worst = max(worst, val)
    ok = bool(worst < sp.Float("1e-50", 60))
    return ok, f"zero to 50 digits at 12 random points (max |residual| {float(worst):.1e})", "symbolic-50dp"


def E(expr, rv: list, mom: dict):
    """Expectation of a polynomial of degree <= 2 in the random symbols ``rv`` (zero means), with
    second moments ``mom[frozenset({a, b})]`` and ``mom[frozenset({a})]`` for squares."""
    p = sp.Poly(sp.expand(expr), *rv)
    out = sp.Integer(0)
    for monom, coef in p.terms():
        deg = sum(monom)
        if deg == 0:
            out += coef
        elif deg == 1:
            continue
        elif deg == 2:
            idx = [i for i, k in enumerate(monom) for _ in range(k)]
            a, b = rv[idx[0]], rv[idx[1]]
            out += coef * mom[frozenset((a, b))]
        else:
            raise ValueError("degree > 2")
    return sp.simplify(out)


def macro(key: str) -> float:
    """A number the LaTeX quotes, as generated by script 45."""
    tag = "thn@" + key + "\\endcsname{"
    for line in (GEN / "numbers.tex").read_text().splitlines():
        if tag in line:
            v = line[line.index(tag) + len(tag):-1]
            return float(v.replace("\\ensuremath{-}", "-").replace("{,}", ""))
    raise KeyError(key)


z, t, k, s, rho, beta, a_, x_, y_ = sp.symbols("z t k s rho beta a x y", real=True)
kp, tp, rp = sp.symbols("k t rho", positive=True)
PHI = lambda v: (1 + sp.erf(v / sp.sqrt(2))) / 2                  # noqa: E731
PHIBAR = lambda v: sp.erfc(v / sp.sqrt(2)) / 2                    # noqa: E731
phi = lambda v: sp.exp(-v**2 / 2) / sp.sqrt(2 * sp.pi)            # noqa: E731


# =============================================================================================
# The model and Proposition 1 (Appendix B.1)
# =============================================================================================

def prop1(S: Steps) -> None:
    os_, eta, xx, nu, ec, eo, ep, ee = sp.symbols("ostar eta x nu e_c e_o eps_prev eps")
    so, ce, ve, q = sp.symbols("s_oo c_oe v_ee q_xx", real=True)
    # Assumption 1: E[o* x] = E[eta x] = 0; E[o* eta] = c_oe is free
    mom = {frozenset((os_,)): so, frozenset((os_, eta)): ce, frozenset((eta,)): ve,
           frozenset((os_, xx)): 0, frozenset((eta, xx)): 0, frozenset((xx,)): q}
    rv = [os_, eta, xx]
    o, r = os_ + eta, os_ + xx
    c = r - o
    Eoo, Eor, Eoos = E(o * o, rv, mom), E(o * r, rv, mom), E(o * os_, rv, mom)
    b = Eor / Eoo
    # the model's bookkeeping, from Appendix A's coordinates
    S.sym("model", "-", "", "", "o = e_o + eta - eps_prev = o* + eta with o* = e_o - eps_prev",
          (eo + eta - ep) - ((eo - ep) + eta))
    S.sym("model", "-", "", "", "r = e_o + e_c + eps - eps_prev = o* + x with x = e_c + eps",
          (eo + ec + ee - ep) - ((eo - ep) + (ec + ee)))
    S.sym("model", "-", "", "", "c = e_c - eta + eps equals r - o", (ec - eta + ee) - ((eo + ec + ee - ep) - (eo + eta - ep)))
    # (a)
    S.sym("1", "a", "B.1", "a", "E[o x] = E[o* x] + E[eta x] = 0 under Assumption 1", E(o * xx, rv, mom))
    S.sym("1", "a", "B.1", "a", "E[o r] = E[o o*] under Assumption 1", Eor - Eoos)
    gam = sp.symbols("gamma", real=True)
    mse = E((os_ - gam * o) ** 2, rv, mom)
    S.sym("1", "a", "B.1", "a", "E[(o* - g o)^2] = E[o*^2] - 2 g E[o o*] + g^2 E[o^2]",
          mse - (so - 2 * gam * Eoos + gam ** 2 * Eoo))
    S.sym("1", "a", "B.1", "a", "the quadratic's stationary point is g = E[o o*]/E[o^2] = b",
          sp.solve(sp.diff(mse, gam), gam)[0] - b)
    S.sym("1", "a", "B.1", "a", "its second derivative is 2 E[o^2] > 0, so b is the minimiser",
          sp.diff(mse, gam, 2) - 2 * Eoo)
    S.sym("1", "a", "B.1", "a", "if E[o*|o] = g o then E[o o*] = g E[o^2], so g = b (tower property)",
          sp.solve(sp.Eq(Eoos, gam * Eoo), gam)[0] - b)
    # (b) needs only the definition of b
    so2, eoc = sp.symbols("m_oo m_or", positive=True)
    S.sym("1", "b", "B.1", "b", "E[o c] = E[o r] - E[o^2] = (b - 1) E[o^2] for any joint law (definition of b)",
          (eoc - so2) - (eoc / so2 - 1) * so2)
    S.sym("1", "b", "B.1", "b", "the same under Assumption 1, in the model's moments", E(o * c, rv, mom) - (b - 1) * Eoo)
    # (c)
    S.sym("1", "c", "B.1", "c", "eta = (1 - b) o - (o* - b o) (pathwise algebra)", eta - ((1 - b) * o - (os_ - b * o)))
    expansion = (1 - b) ** 2 * Eoo - 2 * (1 - b) * E(o * (os_ - b * o), rv, mom) + E((os_ - b * o) ** 2, rv, mom)
    S.sym("1", "c", "B.1", "c", "E[eta^2] = (1-b)^2 E[o^2] - 2(1-b) E[o(o* - b o)] + E[(o* - b o)^2]",
          E(eta ** 2, rv, mom) - expansion)
    S.sym("1", "c", "B.1", "c", "the cross term E[o(o* - b o)] vanishes", E(o * (os_ - b * o), rv, mom))
    S.sym("1", "c", "B.1", "c", "E[eta^2] = (1-b)^2 E[o^2] + E[(o* - b o)^2] (the decomposition)",
          E(eta ** 2, rv, mom) - ((1 - b) ** 2 * Eoo + E((os_ - b * o) ** 2, rv, mom)))
    bb = sp.symbols("b", positive=True)
    S.sym("1", "c", "B.1", "c", "if o* = b o then eta = (1 - b) o = ((1 - b)/b) o* (b > 0)",
          ((1 - bb) * x_) - ((1 - bb) / bb) * (bb * x_))
    # equality case and the strict inequality, numerically on random admissible moment vectors
    g = np.random.default_rng(SEED)
    worst, strict = 0.0, True
    for _ in range(20000):
        A = g.standard_normal((2, 2))
        C = A @ A.T + 1e-9 * np.eye(2)          # covariance of (o*, eta)
        so_, ce_, ve_ = C[0, 0], C[0, 1], C[1, 1]
        moo, moos = so_ + 2 * ce_ + ve_, so_ + ce_
        bv = moos / moo
        resid = so_ - 2 * bv * moos + bv * bv * moo           # E[(o* - b o)^2]
        worst = min(worst, resid)
        strict &= ve_ >= (1 - bv) ** 2 * moo - 1e-12
    S.add("1", "c", "B.1", "c", "E[(o* - b o)^2] >= 0 and the bound holds on 20,000 random covariance matrices",
          "numerical", worst > -1e-12 and strict, f"min E[(o* - b o)^2] = {worst:.2e}")
    # (d)
    S.sym("1", "d", "B.1", "d", "independent error: b = E[o*^2]/(E[o*^2] + E[eta^2])", b.subs(ce, 0) - so / (so + ve))
    S.sym("1", "d", "B.1", "d", "independent error: E[eta^2] = (1 - b) E[o^2]", ((1 - b) * Eoo).subs(ce, 0) - ve)
    th, vn = sp.symbols("theta v_nu", real=True)
    mom2 = {frozenset((os_,)): so, frozenset((os_, nu)): 0, frozenset((nu,)): vn,
            frozenset((os_, xx)): 0, frozenset((nu, xx)): 0, frozenset((xx,)): q}
    o2 = (1 + th) * os_ + nu
    b2 = E(o2 * (os_ + xx), [os_, nu, xx], mom2) / E(o2 ** 2, [os_, nu, xx], mom2)
    S.sym("1", "d", "B.1", "d", "proportional error eta = theta o* + nu: b = (1+theta)E[o*^2]/{(1+theta)^2 E[o*^2] + E[nu^2]}",
          b2 - (1 + th) * so / ((1 + th) ** 2 * so + vn))
    lam = sp.symbols("lambda", positive=True)
    S.sym("1", "d", "B.1", "d", "stale open o = lambda o* (theta = lambda - 1, nu = 0): b = 1/lambda",
          b2.subs({th: lam - 1, vn: 0}) - 1 / lam)
    # (e)
    S.sym("1", "e", "B.1", "e", "E[r^2] = E[o*^2] + E[x^2] under Assumption 1", E(r * r, rv, mom) - (so + q))
    S.sym("1", "e", "B.1", "e", "necessity: E[(o* - b o)^2] = E[o*^2] - b^2 E[o^2]",
          E((os_ - b * o) ** 2, rv, mom) - (so - b ** 2 * Eoo))
    moo, mrr, bv, sv = sp.symbols("m_oo m_rr b s", positive=True)
    cov = sp.Matrix([[moo, bv * moo], [bv * moo, sv]])
    S.sym("1", "e", "B.1", "e", "sufficiency: det Cov(o, o*) = m_oo s - b^2 m_oo^2, so PSD iff s >= b^2 m_oo",
          cov.det() - moo * (sv - bv ** 2 * moo))
    # the construction reproduces the (o, r) moments for every s
    o_, osv, xv = sp.symbols("o_c ostar_c x_c")
    momc = {frozenset((o_,)): moo, frozenset((o_, osv)): bv * moo, frozenset((osv,)): sv,
            frozenset((o_, xv)): 0, frozenset((osv, xv)): 0, frozenset((xv,)): mrr - sv}
    rvc = [o_, osv, xv]
    S.sym("1", "e", "B.1", "e", "construction: E[o r] = b m_oo for every s", E(o_ * (osv + xv), rvc, momc) - bv * moo)
    S.sym("1", "e", "B.1", "e", "construction: E[r^2] = m_rr for every s", E((osv + xv) ** 2, rvc, momc) - mrr)
    S.sym("1", "e", "B.1", "e", "construction: E[x (o*, eta)] = 0 (Assumption 1 holds)",
          E(xv * osv, rvc, momc) + E(xv * (o_ - osv), rvc, momc))
    S.sym("1", "e", "B.1", "e", "range of E[eta^2]: (1-b)^2 m_oo + s - b^2 m_oo at s = b^2 m_oo and s = m_rr",
          sp.Matrix([(1 - bv) ** 2 * moo + s_ - bv ** 2 * moo for s_ in (bv ** 2 * moo, mrr)])
          - sp.Matrix([(1 - bv) ** 2 * moo, (1 - bv) ** 2 * moo + mrr - bv ** 2 * moo]))
    mor = sp.symbols("m_or", real=True)
    S.sym("1", "e", "B.1", "e", "the interval is non-empty: m_rr - b^2 m_oo = det[[m_oo, m_or],[m_or, m_rr]]/m_oo >= 0",
          (mrr - (mor / moo) ** 2 * moo) - sp.Matrix([[moo, mor], [mor, mrr]]).det() / moo)
    # the published bound, for every b < 1
    bq = sp.symbols("b", real=True)
    S.sym("1", "remark", "B.1", "bound", "(3 - 2b)^2 - (5 - 4b) = 4(1 - b)^2", (3 - 2 * bq) ** 2 - (5 - 4 * bq) - 4 * (1 - bq) ** 2)
    S.sym("1", "remark", "B.1", "bound", "(sqrt(5-4b) - 1)/2 < 1 - b <=> sqrt(5-4b) < 3 - 2b (algebra)",
          ((sp.sqrt(5 - 4 * bq) - 1) / 2 - (1 - bq)) - (sp.sqrt(5 - 4 * bq) - (3 - 2 * bq)) / 2, {"b": (-3, 0.99)})
    grid = np.concatenate([np.linspace(-20, 0.999, 4000), 1 - np.logspace(-6, -1, 200)])
    gap = (1 - grid) ** 2 - ((np.sqrt(5 - 4 * grid) - 1) / 2) ** 2
    S.add("1", "remark", "B.1", "bound", "strict gap (1-b)^2 > g(b) for every b < 1 (grid down to b = -20)",
          "numerical", bool((gap > 0).all()), f"min gap {gap.min():.2e} on {len(grid)} points")
    exact = sp.Rational(49, 100) / ((sp.sqrt(sp.Rational(38, 10)) - 1) / 2) ** 2
    S.num("1", "remark", "", "", "ratio of the bounds at b = 0.3, exact 0.49/((sqrt(3.8)-1)/2)^2, equals the code's", float(exact),
          0.49 / s45.g_appendix_a(0.3), 1e-13)
    S.num("1", "remark", "", "", "the quoted ratio (macro p1-ratio-at-03) is the exact ratio rounded", round(float(exact), 2),
          macro("p1-ratio-at-03"), 1e-12)
    # perfect correlation and the overnight term of the kernel
    thp = sp.symbols("theta", positive=True)
    S.sym("1", "remark", "", "", "perfect correlation eta = theta o*: b = 1/(1+theta)", b2.subs({th: thp, vn: 0}) - 1 / (1 + thp))
    S.sym("1", "remark", "", "", "perfect correlation: E[eta^2] = theta^2 E[o*^2] = (1-b)^2 E[o^2]",
          thp ** 2 * so - (1 - 1 / (1 + thp)) ** 2 * ((1 + thp) ** 2 * so))
    S.sym("1", "remark", "", "", "E[(b o)^2] = b^2 E[o^2], the lower end of the identified interval", (bv * 1) ** 2 * moo - bv ** 2 * moo)
    t120 = pd.read_csv(TAB / "table120_anam_recheck_data.csv")
    bsp = float(t120[(t120.market == "SP500") & (t120.check == "pooled b, whole span, unclipped")]["value"].iloc[0])
    S.add("1", "remark", "", "", "S&P 500 pooled b = 2.21 (table120) and 1/b = 45% (an open reflecting 45% of the move)",
          "data", round(bsp, 2) == 2.21 and round(100 / bsp) == 45, f"b = {bsp:.4f}, 1/b = {1 / bsp:.4f}")


# =============================================================================================
# Proposition 2 (Appendix B.2)
# =============================================================================================

def prop2(S: Steps, quick: bool) -> None:
    # (a)
    o, c = sp.symbols("o c", real=True)
    S.sym("2", "a", "B.2", "a", "o^2 + c^2 - r^2 = -2 o c with r = o + c (no assumption)", o ** 2 + c ** 2 - (o + c) ** 2 + 2 * o * c)
    moo, mor = sp.symbols("m_oo m_or", positive=True)
    S.sym("2", "a", "B.2", "a", "E[-2oc] = -2(E[or] - E[o^2]) = 2(1 - b)E[o^2]", -2 * (mor - moo) - 2 * (1 - mor / moo) * moo)
    # (b): independence algebra, sigma_c = 1
    os_, eta, D = sp.symbols("ostar eta D")
    so, se2 = sp.symbols("s_oo sigma_eta2", positive=True)
    mom = {frozenset((os_,)): so, frozenset((eta,)): se2, frozenset((D,)): 1,
           frozenset((os_, eta)): 0, frozenset((os_, D)): 0, frozenset((eta, D)): 0}
    rv = [os_, eta, D]
    S.sym("2", "b", "B.2", "b", "E[r^2] = E[o*^2] + sigma_c^2 (close-to-close unbiased)", E((os_ + D) ** 2, rv, mom) - (so + 1))
    S.sym("2", "b", "B.2", "b", "E[o^2] - E[o*^2] = sigma_eta^2", E((os_ + eta) ** 2, rv, mom) - so - se2)
    S.sym("2", "b", "B.2", "b", "E[c^2] - sigma_c^2 = sigma_eta^2 - 2E[D eta] = sigma_eta^2", E((D - eta) ** 2, rv, mom) - 1 - se2)
    sc, Mx = sp.symbols("sigma_c M_x", positive=True)
    S.sym("2", "-", "B.2", "scaling", "Brownian scaling: E[(sigma_c X)^2] = sigma_c^2 E[X^2] for every functional of degree one",
          (sc * Mx) ** 2 - sc ** 2 * Mx ** 2)

    # simulated sessions
    n, steps = (60_000, 64) if quick else (400_000, 256)
    rng = np.random.default_rng(SEED)
    Dv, M, m = s45.brownian_bars(n, steps, rng)
    ostar = rng.normal(0, math.sqrt(0.5), n)
    for rho_v in (0.5, 1.0):
        lab = f"rho = {rho_v:g}"
        e = rho_v * rng.standard_normal(n)
        hi, lo = np.maximum(e, M), np.minimum(e, m)
        # coordinates built from prices against the stated formulas
        pc = 100.0 * np.exp(rng.normal(0, 0.1, n))
        O, H, L, C = pc * np.exp(ostar + e), pc * np.exp(ostar + hi), pc * np.exp(ostar + lo), pc * np.exp(ostar + Dv)
        uu, dd, cc = np.log(H / O), np.log(L / O), np.log(C / O)
        RR, rr = np.log(H / L), np.log(C / pc)
        S.path("2", "-", "B.2", "coordinates", f"R = h~ - l~, u = h~ - eta, d = l~ - eta, c = D - eta, r = o* + D from prices ({lab})",
               np.concatenate([RR - (hi - lo), uu - (hi - e), dd - (lo - e), cc - (Dv - e), rr - (ostar + Dv)]), tol=1e-10)
        R0 = M - m
        S.path("2", "c", "B.2", "c", f"R = (M - m) + (eta - M)^+ + (m - eta)^+ ({lab})",
               (hi - lo) - (R0 + np.maximum(e - M, 0) + np.maximum(m - e, 0)))
        S.path("2", "c", "B.2", "c", f"at most one of (eta - M)^+, (m - eta)^+ is positive ({lab})",
               np.maximum(e - M, 0) * np.maximum(m - e, 0))
        S.add("2", "c", "B.2", "c", f"M - m <= R <= M - m + |eta| on every path ({lab})", "pathwise",
              bool(((hi - lo) >= R0 - 1e-14).all() and ((hi - lo) <= R0 + np.abs(e) + 1e-12).all()), f"{n:,} paths")
        term1 = (e - M) * (e + M - 2 * m) * (e > M)
        term2 = (m - e) * (2 * M - m - e) * (e < m)
        S.path("2", "c", "B.2", "c", f"R^2 - (M - m)^2 = term(eta > M) + term(eta < m) ({lab})", (hi - lo) ** 2 - R0 ** 2 - term1 - term2)
        S.path("2", "c", "B.2", "c", f"term(eta > M) = ((eta-M)^+)^2 + 2(eta-M)^+ M + 2(eta-M)^+(-m) ({lab})",
               term1 - (np.maximum(e - M, 0) ** 2 + 2 * np.maximum(e - M, 0) * M + 2 * np.maximum(e - M, 0) * (-m)))
        v, se = s45.batch_mean(term1 - term2)
        S.mc("2", "c", "B.2", "c", f"(W, eta) -> (-W, -eta): the two terms have equal means ({lab})", 0.0, v, se)
        v, se = s45.batch_mean(np.maximum(e - M, 0) * (-m))
        S.mc("2", "c", "B.2", "c", f"T3 = int_0^inf J(s) Phibar(s/rho) ds (Fubini; image series) against E[(eta-M)^+(-m)] ({lab})",
             s45.t3(rho_v), v, se)
        # (d) Rogers-Satchell: rewrite, cases, collection
        RS = uu * (uu - cc) + dd * (dd - cc)
        RS0 = M * (M - Dv) + m * (m - Dv)
        S.path("2", "d", "B.2", "d", f"RS = (h~ - eta)(h~ - D) + (l~ - eta)(l~ - D) ({lab})",
               RS - ((hi - e) * (hi - Dv) + (lo - e) * (lo - Dv)), tol=1e-10)
        inside, up, down = (e >= m) & (e <= M), e > M, e < m
        case = np.where(inside, -e * (M + m - 2 * Dv),
                        np.where(up, -e * (m - Dv) - M * (M - Dv), -e * (M - Dv) - m * (m - Dv)))
        S.path("2", "d", "B.2", "d", f"RS - RS_0 by case: -eta(M+m-2D), -eta(m-D) - M(M-D), mirror ({lab})", RS - RS0 - case, tol=1e-10)
        v, se = s45.batch_mean(e * (M + m - 2 * Dv))
        S.mc("2", "d", "B.2", "d", f"E[eta (M + m - 2D)] = 0 ({lab})", 0.0, v, se)
        v, se = s45.batch_mean((RS - RS0) - 2 * np.maximum(e - M, 0) * (M - Dv))
        S.mc("2", "d", "B.2", "d", f"E[RS] - 1 = 2E[(eta - M)^+ (M - D)] (collection with symmetry) ({lab})", 0.0, v, se)
        S.path("2", "f", "B.2", "f", f"the events eta > M and eta < m are disjoint ({lab})", (up & down).astype(float))
    v, se = s45.batch_mean((M - m) ** 2)
    S.mc("2", "c", "B.2", "c", "E[(M - m)^2] = 4 ln 2 (Feller 1951)", 4 * LN2, v, se)
    v, se = s45.batch_mean(M - m)
    S.mc("2", "c", "B.2", "c", "E[M - m] = 2 sqrt(2/pi)", 2 * math.sqrt(2 / math.pi), v, se)
    v, se = s45.batch_mean(M * (M - Dv) + m * (m - Dv))
    S.mc("2", "d", "B.2", "d", "E[RS_0] = 1 (Rogers and Satchell 1991)", 1.0, v, se)
    for sv in (0.3, 1.0):
        v, se = s45.batch_mean((M < sv).astype(float))
        S.mc("2", "c", "B.2", "c", f"P(M < s) = 2 Phi(s) - 1 (reflection), s = {sv:g}", 2 * norm.cdf(sv) - 1, v, se)
    for av, bvv in ((0.5, 0.5), (1.0, 0.3), (0.2, 1.5), (1.2, 1.2)):
        v, se = s45.batch_mean(((M < av) & (-m < bvv)).astype(float))
        S.mc("2", "c", "B.2", "c", f"image series G({av:g}, {bvv:g}) = P(M < a, -m < b)", s45.p_max_min(av, bvv), v, se)
    for sv in (0.3, 1.0, 2.0):
        v, se = s45.batch_mean((-m) * (M < sv))
        S.mc("2", "c", "B.2", "c", f"J({sv:g}) = int_0^inf [P(M<s) - G(s,t)] dt = E[(-m) 1{{M<s}}]", s45.J(sv), v, se)
    for av, xv in ((0.5, 0.2), (1.0, -0.5), (0.3, 0.3)):
        v, se = s45.batch_mean(((M <= av) & (Dv <= xv)).astype(float))
        S.mc("2", "d", "B.2", "d", f"reflection: P(M <= a, D <= x) = Phi(x) - Phi(x - 2a) at (a, x) = ({av:g}, {xv:g})",
             norm.cdf(xv) - norm.cdf(xv - 2 * av), v, se)
    for av in (0.5, 1.5):
        v, se = s45.batch_mean((M - Dv) * (M < av))
        S.mc("2", "d", "B.2", "d", f"E[(M - D) 1{{M < a}}] = 2 int_0^a Phibar = 2(a Phibar(a) - phi(a) + phi(0)), a = {av:g}",
             2 * (av * norm.sf(av) - norm.pdf(av) + norm.pdf(0)), v, se)
    # the meander: E[-m | M < s] -> sqrt(2 pi) ln 2
    sv = 0.05
    sel = M < sv
    v, se = s45.batch_mean((-m)[sel]) if sel.sum() > 400 else (np.nan, np.nan)
    S.mc("2", "c", "B.2", "c", f"E[-m | M < {sv}] = J(s)/P(M < s) (simulation against the series)", s45.J(sv) / (2 * norm.cdf(sv) - 1), v, se)

    # symmetry and limits of the image series
    S.num("2", "c", "B.2", "c", "G(a, b) = G(b, a) (series, a = 0.7, b = 1.3)", s45.p_max_min(0.7, 1.3), s45.p_max_min(1.3, 0.7), 1e-12)
    S.num("2", "c", "B.2", "c", "G(a, b) -> 2 Phi(a) - 1 as b -> infinity (a = 0.8)", 2 * norm.cdf(0.8) - 1, s45.p_max_min(0.8, 12.0), 1e-12)

    # T1, T2 by polar coordinates, symbolically
    ph = sp.symbols("varphi", real=True)
    al = sp.atan(rp)
    T1 = 2 / sp.pi * sp.integrate((rp * sp.cos(ph) - sp.sin(ph)) ** 2, (ph, 0, al))
    T2 = 2 / sp.pi * sp.integrate((rp * sp.cos(ph) - sp.sin(ph)) * sp.sin(ph), (ph, 0, al))
    T1_cf = ((1 + rp ** 2) * sp.atan(rp) - rp) / sp.pi
    S.sym("2", "c", "B.2", "c", "T1 = (2/pi) int_0^alpha (rho cos - sin)^2 = ((1+rho^2) atan rho - rho)/pi", T1, T1_cf)
    S.sym("2", "c", "B.2", "c", "T2 = (2/pi) int_0^alpha (rho cos - sin) sin = (rho - atan rho)/pi", T2, (rp - sp.atan(rp)) / sp.pi)
    S.sym("2", "c", "B.2", "c", "sin^2(atan rho) = rho^2/(1 + rho^2)", sp.sin(al) ** 2, rp ** 2 / (1 + rp ** 2))
    S.sym("2", "c", "B.2", "c", "sin(2 atan rho) = 2 rho/(1 + rho^2)", sp.sin(2 * al), 2 * rp / (1 + rp ** 2))
    # the polar representation itself: E[((rho Z - |Z'|)^+)^2] by two-dimensional quadrature
    for rv_ in (0.5, 2.0):
        val = integrate.dblquad(lambda zp, zz: max(rv_ * zz - abs(zp), 0.0) ** 2 * norm.pdf(zz) * norm.pdf(zp),
                                -10, 10, -10, 10, epsabs=1e-11)[0]
        S.num("2", "c", "B.2", "c", f"polar representation: E[((rho Z - |Z'|)^+)^2] by quadrature = T1 (rho = {rv_:g})",
              s45.t1(rv_), val, 1e-7)
    # Fubini step
    Mv = sp.symbols("M", positive=True)
    yv = sp.symbols("y", positive=True)
    lhs = sp.integrate(sp.Heaviside(s - Mv), (s, 0, yv))
    S.sym("2", "c", "B.2", "c", "(y - M)^+ = int_0^y 1{M < s} ds for y, M > 0",
          sp.simplify(lhs.rewrite(sp.Piecewise)) - sp.Piecewise((yv - Mv, yv > Mv), (0, True)), {"y": (0.05, 3), "M": (0.05, 3)})
    # bounds
    S.sym("2", "c", "B.2", "c", "E|eta| = rho sqrt(2/pi)", 2 * sp.integrate(rp * z * phi(z), (z, 0, sp.oo)), rp * sp.sqrt(2 / sp.pi))
    S.sym("2", "c", "B.2", "c", "E|Z'| = sqrt(2/pi), so E[M - m] = 2 sqrt(2/pi)", 2 * sp.integrate(z * phi(z), (z, 0, sp.oo)), sp.sqrt(2 / sp.pi))
    S.sym("2", "c", "B.2", "c", "E[(M - m + |eta|)^2] = 4 ln 2 + (8/pi) rho + rho^2 (independence)",
          4 * sp.log(2) + 2 * (2 * sp.sqrt(2 / sp.pi)) * (rp * sp.sqrt(2 / sp.pi)) + rp ** 2, 4 * sp.log(2) + 8 * rp / sp.pi + rp ** 2)
    for rv_ in (0.25, 0.5, 1.0, 2.0, 4.0):
        dr = s45.delta_R(rv_)
        S.add("2", "c", "B.2", "c", f"0 <= Delta_R <= (8/pi) rho + rho^2 (rho = {rv_:g})", "numerical",
              0 <= dr <= 8 / math.pi * rv_ + rv_ ** 2, f"Delta_R = {dr:.6f}")
    # small-error limit
    S.sym("2", "c", "B.2", "c", "(1 + rho^2) atan rho - rho = (2/3) rho^3 + O(rho^5)",
          sp.series((1 + rp ** 2) * sp.atan(rp) - rp, rp, 0, 5).removeO(), sp.Rational(2, 3) * rp ** 3)
    S.sym("2", "c", "B.2", "c", "rho - atan rho = rho^3/3 + O(rho^5)",
          sp.series(rp - sp.atan(rp), rp, 0, 5).removeO(), rp ** 3 / 3)
    rv_ = 0.5
    lhs_ = s45.t3(rv_)
    rhs_ = rv_ ** 2 * integrate.quad(lambda vv: s45.J(rv_ * vv) / (rv_ * vv) * vv * norm.sf(vv), 1e-9, 12, limit=300)[0]
    S.num("2", "c", "B.2", "c", "substitution s = rho v: T3 = rho^2 int (J(rho v)/(rho v)) v Phibar(v) dv (rho = 0.5)", lhs_, rhs_, 1e-7)
    S.sym("2", "c", "B.2", "c", "f_M(0) = 2 phi(0) = sqrt(2/pi)", 2 * phi(0), sp.sqrt(2 / sp.pi))
    S.sym("2", "c", "B.2", "c", "f_M(0) sqrt(2 pi) ln 2 = 2 ln 2", sp.sqrt(2 / sp.pi) * sp.sqrt(2 * sp.pi) * sp.log(2), 2 * sp.log(2))
    meander = math.sqrt(2 * math.pi) * LN2
    for sv in (0.01, 0.005):
        S.num("2", "c", "B.2", "c", f"E[-m | M < s] = J(s)/P(M < s) -> sqrt(2 pi) ln 2 (meander mean), s = {sv:g}",
              meander, s45.J(sv) / (2 * norm.cdf(sv) - 1), 3 * sv)
    jr = [s45.J(sv) / sv for sv in np.linspace(0.02, 1.0, 50)]
    S.add("2", "c", "B.2", "c", "J(s)/s is bounded on (0, 1] (grid of 50 points)", "numerical", bool(np.isfinite(jr).all() and max(jr) < 2),
          f"max {max(jr):.4f}, min {min(jr):.4f}")
    jg = [s45.J(sv) for sv in (1.0, 1.5, 2.0, 3.0, 5.0)]
    S.add("2", "c", "B.2", "c", "J(s) <= E[-m] = sqrt(2/pi) for s > 1, and J increases towards it", "numerical",
          bool(max(jg) <= math.sqrt(2 / math.pi) + 1e-12 and np.all(np.diff(jg) >= -1e-12)),
          f"J(1..5) = {', '.join(f'{v:.5f}' for v in jg)}; sqrt(2/pi) = {math.sqrt(2 / math.pi):.5f}")
    S.sym("2", "c", "B.2", "c", "int_0^inf v Phibar(v) dv = 1/4", sp.integrate(z * PHIBAR(z), (z, 0, sp.oo)), sp.Rational(1, 4))
    S.sym("2", "c", "B.2", "c", "2 ln 2 x 1/4 = (1/2) ln 2", 2 * sp.log(2) / 4, sp.log(2) / 2)
    for rv_ in (0.1, 0.05):
        S.num("2", "c", "B.2", "c", f"T3/rho^2 -> (ln 2)/2 (rho = {rv_:g})", LN2 / 2, s45.t3(rv_) / rv_ ** 2, 2 * rv_)
    S.num("2", "c", "", "", "the code's Delta_R is the displayed formula: 2T1 + (4/pi)(rho - atan rho) + 4 T3 (rho = 0.7)",
          2 * s45.t1(0.7) + 4 / math.pi * (0.7 - math.atan(0.7)) + 4 * s45.t3(0.7), s45.delta_R(0.7), 1e-14)
    for rv_, key in ((0.5, "p2-Pratio-0p5"), (1.0, "p2-Pratio-1p0"), (2.0, "p2-Pratio-2p0")):
        S.num("2", "remark", "", "", f"quoted Delta_R/(2 ln 2 rho^2) at rho = {rv_:g} (macro {key}) is the exact value rounded",
              round(s45.delta_R(rv_) / (2 * LN2 * rv_ ** 2), 4), macro(key), 1e-12)
    worst = max(abs(s45.delta_R(rv_) / (2 * LN2 * rv_ ** 2) - 1) for rv_ in np.linspace(0.05, 1.0, 20))
    S.add("2", "remark", "", "", "Parkinson's bias is within 1% of sigma_eta^2/2 for every rho <= 1 (grid of 20)", "numerical",
          worst < 0.01, f"max relative gap {worst:.4f}")
    # (d) the density substitution and the polar evaluation
    S.sym("2", "d", "B.2", "d", "int_{-inf}^a (a - x) 2(2a - x) phi(2a - x) dx = 2 int_a^inf (z - a) z phi(z) dz = 2 Phibar(a)",
          sp.integrate((a_ - x_) * 2 * (2 * a_ - x_) * phi(2 * a_ - x_), (x_, -sp.oo, a_)), 2 * PHIBAR(a_), {"a": (0.05, 3)})
    S.sym("2", "d", "B.2", "d", "2 int_a^inf (z - a) z phi(z) dz = 2 Phibar(a)",
          2 * sp.integrate((z - a_) * z * phi(z), (z, a_, sp.oo)), 2 * PHIBAR(a_), {"a": (0.05, 3)})
    for rv_ in (0.5, 1.5):
        lhs_ = 2 * integrate.quad(lambda av: (rv_ * norm.pdf(av / rv_) - av * norm.sf(av / rv_)) * norm.sf(av), 0, 15)[0]
        rhs_ = 2 * integrate.dblquad(lambda zz2, zz: (lambda mu: (rv_ * zz * mu - mu * mu / 2))(min(rv_ * zz, zz2)) * norm.pdf(zz) * norm.pdf(zz2),
                                     0, 12, 0, 12, epsabs=1e-12)[0]
        S.num("2", "d", "B.2", "d", f"2 int_0^inf E[(eta-a)^+] Phibar(a) da = 2E[1{{eta>0,Z''>0}}(eta mu - mu^2/2)] (rho = {rv_:g})",
              lhs_, rhs_, 1e-7)
        S.num("2", "d", "B.2", "d", f"... and both equal rho^2/4 - T1/2 (rho = {rv_:g})", rv_ ** 2 / 4 - s45.t1(rv_) / 2, lhs_, 1e-7)
    polar = 2 / sp.pi * (sp.integrate(rp * sp.cos(ph) * sp.sin(ph) - sp.sin(ph) ** 2 / 2, (ph, 0, al))
                         + sp.integrate(rp ** 2 * sp.cos(ph) ** 2 / 2, (ph, al, sp.pi / 2)))
    S.sym("2", "d", "B.2", "d", "polar evaluation: (2/pi)[int_0^a (rho cos sin - sin^2/2) + int_a^{pi/2} rho^2 cos^2/2] = rho^2/4 - T1/2",
          polar, rp ** 2 / 4 - T1_cf / 2)
    S.sym("2", "d", "B.2", "d", "E[RS] - 1 = 2(rho^2/4 - T1/2) = rho^2/2 - T1", 2 * (rp ** 2 / 4 - T1_cf / 2), rp ** 2 / 2 - T1_cf)
    # (e), (f), (g)
    DR = sp.symbols("Delta_R", real=True)
    S.sym("2", "e", "B.2", "e", "E[GK] - 1 = (4 ln 2 + Delta_R)/2 - (2 ln 2 - 1)(1 + rho^2) - 1 = Delta_R/2 - (2 ln 2 - 1) rho^2",
          (4 * sp.log(2) + DR) / 2 - (2 * sp.log(2) - 1) * (1 + rp ** 2) - 1, DR / 2 - (2 * sp.log(2) - 1) * rp ** 2)
    S.sym("2", "f", "B.2", "f", "P(rho Z > |Z'|) = (angle 2 atan rho)/(2 pi) = atan(rho)/pi; total (2/pi) atan rho",
          2 * (2 * sp.atan(rp) / (2 * sp.pi)), 2 * sp.atan(rp) / sp.pi)
    S.sym("2", "-", "", "", "B2 inversion: s = (2/pi) atan(rho) gives rho = tan(pi s/2)", sp.tan(sp.pi * (2 * sp.atan(rp) / sp.pi) / 2), rp)
    xx = sp.symbols("x", positive=True)
    S.sym("2", "-", "", "", "B2 inversion: x = rho^2/(1 + rho^2) gives rho = sqrt(x/(1 - x))", sp.sqrt((rp ** 2 / (1 + rp ** 2)) / (1 - rp ** 2 / (1 + rp ** 2))), rp)
    kk = sp.Rational(34, 100) / (sp.Rational(134, 100) + sp.Rational(22, 20))
    S.num("2", "g", "", "", "k = 0.34/(1.34 + 22/20) for a 21-session window, quoted as macro p2-yz-k", round(float(kk), 4), macro("p2-yz-k"), 1e-12)
    S.sym("2", "g", "B.2", "g", "Rogers-Satchell loading: lim (rho^2/2 - T1)/rho^2 = 1/2", sp.limit((rp ** 2 / 2 - T1_cf) / rp ** 2, rp, 0), sp.Rational(1, 2))
    S.sym("2", "g", "B.2", "g", "Parkinson loading: (2 ln 2 rho^2)/(4 ln 2)/rho^2 = 1/2", (2 * sp.log(2)) / (4 * sp.log(2)), sp.Rational(1, 2))
    S.sym("2", "g", "B.2", "g", "Garman-Klass loading: ln 2 - (2 ln 2 - 1) = 1 - ln 2", sp.log(2) - (2 * sp.log(2) - 1), 1 - sp.log(2))
    S.sym("2", "g", "B.2", "g", "overnight^2 + Parkinson loading 1 + 1/2 = 3/2; + Garman-Klass 1 + (1 - ln 2) = 2 - ln 2",
          sp.Matrix([1 + sp.Rational(1, 2), 1 + 1 - sp.log(2)]) - sp.Matrix([sp.Rational(3, 2), 2 - sp.log(2)]))
    kv = sp.symbols("k", positive=True)
    S.sym("2", "g", "B.2", "g", "Yang-Zhang daily form loading 1 + k + (1 - k)/2 = (3 + k)/2", 1 + kv + (1 - kv) / 2, (3 + kv) / 2)
    S.num("2", "g", "", "", "(3 + k)/2 quoted as macro p2-yz-load", round((3 + float(kk)) / 2, 3), macro("p2-yz-load"), 1e-12)
    S.num("2", "g", "", "", "1 - ln 2 quoted as macro p2-gk-load", round(1 - LN2, 3), macro("p2-gk-load"), 1e-12)
    S.num("2", "g", "", "", "2 - ln 2 quoted as macro p2-gk2-load", round(2 - LN2, 3), macro("p2-gk2-load"), 1e-12)


# =============================================================================================
# Proposition 3 (Appendix B.3)
# =============================================================================================

def prop3(S: Steps, quick: bool) -> None:
    bL = sp.symbols("b_L", real=True)
    Ego, Egg = sp.symbols("E_go E_gg", positive=True)
    S.sym("3", "a", "B.3", "a", "tower property: E[g r] = E[g E[r|o_L]] = b_L E[g o_L], so b = b_L E[g o_L]/E[g^2]",
          (bL * Ego) / Egg - bL * (Ego / Egg))
    yv, bt = sp.symbols("y beta", positive=True)
    S.sym("3", "a", "B.3", "a", "y > beta: g(y)(y - g(y)) = beta(y - beta) > 0", bt * ((bt + yv) - bt) - bt * yv)
    S.sym("3", "a", "B.3", "a", "y < -beta: g(y)(y - g(y)) = -beta(y + beta) > 0", (-bt) * ((-bt - yv) + bt) - bt * yv)
    yy = np.linspace(-5, 5, 200001)
    gfun = np.clip(yy, -1.0, 1.0)
    S.add("3", "a", "B.3", "a", "g(y)(y - g(y)) >= 0 everywhere and > 0 exactly when |y| > beta (grid)", "numerical",
          bool((gfun * (yy - gfun) >= 0).all() and ((gfun * (yy - gfun) > 0) == (np.abs(yy) > 1)).all()), "beta = 1, 200,001 points")
    rng = np.random.default_rng(SEED + 3)
    u = rng.uniform(-0.9, 0.9, 100000)
    gu = np.clip(u, -1, 1)
    S.num("3", "a", "B.3", "a", "F = 1 when no latent open exceeds the band", 1.0, float((gu * u).sum() / (gu * gu).sum()), 1e-15)
    # (b)
    S.sym("3", "b", "B.3", "b", "interior: E[o_L r 1_A]/E[o_L^2 1_A] = b_L", (bL * Egg) / Egg - bL)
    Eabs, PA = sp.symbols("E_abs P_A", positive=True)
    S.sym("3", "b", "B.3", "b", "pinned: b_L beta E|o_L|1_Ac / (beta^2 P(A^c)) = b_L E[|o_L| | A^c]/beta",
          bL * bt * Eabs / (bt ** 2 * PA) - bL * (Eabs / PA) / bt)
    S.add("3", "b", "B.3", "b", "E[|o_L| | |o_L| >= beta]/beta >= 1, so b_pinned >= b_L when b_L >= 0 (Gaussian grid)", "numerical",
          bool(all(s45.mills(kv) / kv >= 1 for kv in np.linspace(0.01, 6, 600))), "inverse Mills ratio exceeds its argument")
    # (c) Stein, E[g^2], N, D
    Egz = sp.integrate(z ** 2 * phi(z), (z, -kp, kp)) + 2 * kp * sp.integrate(z * phi(z), (z, kp, sp.oo))
    S.sym("3", "c", "B.3", "c", "Stein: E[g(z) z] = int_{-k}^{k} z^2 phi + 2k int_k^inf z phi = 2 Phi(k) - 1", Egz, 2 * PHI(kp) - 1)
    Egg_ = sp.integrate(z ** 2 * phi(z), (z, -kp, kp)) + 2 * kp ** 2 * PHIBAR(kp)
    S.sym("3", "c", "B.3", "c", "E[g^2] = 2 Phi(k) - 1 - 2k phi(k) + 2k^2 Phibar(k)", Egg_,
          2 * PHI(kp) - 1 - 2 * kp * phi(kp) + 2 * kp ** 2 * PHIBAR(kp))
    S.sym("3", "c", "B.3", "c", "N(k) = int_0^k 2 phi(t) dt = 2 Phi(k) - 1", sp.integrate(2 * phi(tp), (tp, 0, kp)), 2 * PHI(kp) - 1)
    Dk = sp.integrate(4 * tp * PHIBAR(tp), (tp, 0, kp))
    S.sym("3", "c", "B.3", "c", "D(k) = int_0^k 4t Phibar(t) dt = E[min(z^2, k^2)]", Dk, 2 * PHI(kp) - 1 - 2 * kp * phi(kp) + 2 * kp ** 2 * PHIBAR(kp))
    Fk = (2 * PHI(kp) - 1) / (2 * PHI(kp) - 1 - 2 * kp * phi(kp) + 2 * kp ** 2 * PHIBAR(kp))
    for kv in (0.3, 1.1, 2.5):
        S.num("3", "c", "", "", f"equation (F) equals the code's F_gauss (k = {kv:g})", float(Fk.subs(kp, kv)), float(s45.F_gauss(kv)), 1e-13)
    # the lemma: a(k)C(k) - c(k)A(k) = c(k) int_0^k c(t)[a(k)/c(k) - a(t)/c(t)] dt, with the actual a and c
    aF = lambda v: 2 * phi(v)                                   # noqa: E731
    cF = lambda v: 4 * v * PHIBAR(v)                            # noqa: E731
    lhs = aF(kp) * sp.integrate(cF(tp), (tp, 0, kp)) - cF(kp) * sp.integrate(aF(tp), (tp, 0, kp))
    rhs = cF(kp) * (aF(kp) / cF(kp) * sp.integrate(cF(tp), (tp, 0, kp)) - sp.integrate(aF(tp), (tp, 0, kp)))
    S.sym("3", "c", "B.3", "c", "lemma's identity a(k)C(k) - c(k)A(k) = c(k) int c(t)[a(k)/c(k) - a(t)/c(t)] dt (linearity)", lhs, rhs)
    for kv in (0.2, 0.8, 1.5, 3.0):
        val = float(lhs.subs(kp, kv))
        S.add("3", "c", "B.3", "c", f"lemma: a(k)C(k) - c(k)A(k) < 0 (k = {kv:g})", "numerical", val < 0, f"value {val:.3e}")
    lam = phi(tp) / PHIBAR(tp)
    S.sym("3", "c", "B.3", "c", "a(t)/c(t) = 2 phi/(4 t Phibar) = lambda(t)/(2t)", aF(tp) / cF(tp), lam / (2 * tp))
    S.sym("3", "c", "B.3", "c", "lambda' = lambda(lambda - t)", sp.diff(lam, tp), lam * (lam - tp))
    S.sym("3", "c", "B.3", "c", "(lambda/t)' = lambda(t lambda - t^2 - 1)/t^2", sp.diff(lam / tp, tp), lam * (tp * lam - tp ** 2 - 1) / tp ** 2)
    fb, pb = sp.symbols("Phibar_t phi_t", positive=True)
    S.sym("3", "c", "B.3", "c", "lambda < t + 1/t  <=>  Phibar > t phi/(1 + t^2): (t + 1/t)Phibar - phi = ((1+t^2)/t)(Phibar - t phi/(1+t^2))",
          (tp + 1 / tp) * fb - pb, ((1 + tp ** 2) / tp) * (fb - tp * pb / (1 + tp ** 2)))
    ts = np.linspace(0.001, 30, 30000)
    gord = norm.sf(ts) * (1 + ts * ts) - ts * norm.pdf(ts)
    S.add("3", "c", "B.3", "c", "Gordon (1941): Phibar(t)(1 + t^2) > t phi(t) on (0, 30] (grid, scaled form)", "numerical",
          bool((gord > 0).all()), f"min {gord.min():.2e}")
    S.sym("3", "c", "B.3", "c", "N(k) -> 1 as k -> infinity", sp.limit(2 * PHI(kp) - 1, kp, sp.oo), 1)
    S.sym("3", "c", "B.3", "c", "D(k) -> 1 as k -> infinity", sp.limit(2 * PHI(kp) - 1 - 2 * kp * phi(kp) + 2 * kp ** 2 * PHIBAR(kp), kp, sp.oo), 1)
    S.sym("3", "c", "B.3", "c", "N(k) = 2 phi(0) k + O(k^3)", sp.series(2 * PHI(kp) - 1, kp, 0, 3).removeO(), 2 * phi(0) * kp)
    S.sym("3", "c", "B.3", "c", "D(k) = k^2 + O(k^3)",
          sp.series(2 * PHI(kp) - 1 - 2 * kp * phi(kp) + 2 * kp ** 2 * PHIBAR(kp), kp, 0, 3).removeO(), kp ** 2)
    S.sym("3", "c", "B.3", "c", "k F(k) -> 2 phi(0) as k -> 0", sp.limit(kp * Fk, kp, 0), 2 * phi(0))
    S.sym("3", "c", "B.3", "c", "F(k) -> 1 as k -> infinity", sp.limit(Fk, kp, sp.oo), 1)
    S.sym("3", "c", "B.3", "c", "pinned ratio: E[|z| | |z| > k] = 2 int_k^inf z phi / (2 Phibar(k)) = lambda(k)",
          sp.integrate(z * phi(z), (z, kp, sp.oo)) / PHIBAR(kp), phi(kp) / PHIBAR(kp))
    import mpmath as mpm
    mpm.mp.dps = 50

    def F_mp(kk):
        N = mpm.erf(kk / mpm.sqrt(2))
        return N / (N - 2 * kk * mpm.npdf(kk) + 2 * kk * kk * mpm.ncdf(-kk))

    vals = [F_mp(mpm.mpf(i) / 500) for i in range(3, 4001)]
    dec = all(vals[i + 1] < vals[i] for i in range(len(vals) - 1))
    S.add("3", "c", "B.3", "c", "F strictly decreasing on [0.006, 8] (4,000 points in 50-digit arithmetic)", "numerical", dec,
          f"F(8) - 1 = {mpm.nstr(vals[-1] - 1, 5)}")
    # (d)
    b0, b1, i0, i1 = sp.symbols("b_0 b_1 bint_0 bint_1", positive=True)
    S.sym("3", "d", "B.3", "d", "ln(b0/b1) = ln(b0/b0int) + ln(b0int/b1int) + ln(b1int/b1) (telescoping)",
          sp.expand_log(sp.log(b0 / i0) + sp.log(i0 / i1) + sp.log(i1 / b1), force=True), sp.expand_log(sp.log(b0 / b1), force=True))
    F0, F1 = sp.symbols("F_0 F_1", positive=True)
    S.sym("3", "d", "B.3", "d", "regime 0: ln(b0/b0int) = ln F0; regime 1: ln(b1int/b1) = -ln F1",
          sp.Matrix([sp.log((bL * F0) / bL), sp.log(bL / (bL * F1))]), sp.Matrix([sp.log(F0), -sp.log(F1)]), {"b_L": (0.05, 1)})
    # quoted decomposition, from the frozen table
    ap = pd.read_csv(TAB / "table122_theory_applications.csv")
    d = ap[(ap.part == "B3") & (ap["sample"] == "NEPSE A2 -> C")].set_index("statistic")["value"]
    S.num("3", "d", "", "", "the three terms of NEPSE's A2 -> C decomposition add up (table122)",
          float(d["ln(b_A2/b_C)"]), float(d.drop("ln(b_A2/b_C)").sum()), 1e-9)


# =============================================================================================
# Proposition 4 (Appendix B.4)
# =============================================================================================

def prop4(S: Steps) -> None:
    Y, f, cc = sp.symbols("Y f c", positive=True)
    QL = lambda yv, fv: yv / fv - sp.log(yv / fv) - 1             # noqa: E731
    S.sym("4", "a", "B.4", "a", "QL(Y,f) - QL(Y,cf) = (Y/f)(1 - 1/c) - ln c", QL(Y, f) - QL(Y, cc * f), (Y / f) * (1 - 1 / cc) - sp.log(cc))
    mv = sp.symbols("m", positive=True)
    S.sym("4", "a", "B.4", "a", "averaged with c = m = mean(Y/f): m(1 - 1/m) - ln m = q(m)", mv * (1 - 1 / mv) - sp.log(mv), mv - 1 - sp.log(mv))
    q = cc - 1 - sp.log(cc)
    S.sym("4", "a", "B.4", "a", "q(1) = 0, q'(c) = 1 - 1/c, q'' = 1/c^2 > 0, so q >= 0 (ln c <= c - 1)",
          sp.Matrix([q.subs(cc, 1), sp.diff(q, cc) - (1 - 1 / cc), sp.diff(q, cc, 2) - 1 / cc ** 2]))
    Lc = mv / cc + sp.log(cc)          # mean QL(Y, c f) up to terms free of c
    S.sym("4", "a", "B.4", "a", "d/dc mean QL(Y, c f) = 1/c - m/c^2 vanishes at c = m (the best rescaling)",
          sp.solve(sp.diff(Lc, cc), cc)[0] - mv)
    S.sym("4", "a", "B.4", "a", "second derivative at c = m is 1/m^2 > 0", sp.diff(Lc, cc, 2).subs(cc, mv) - 1 / mv ** 2)
    rng = np.random.default_rng(SEED + 4)
    Yv, fv = rng.gamma(2, 1, 500), rng.gamma(3, 1, 500)
    ql = lambda yy, ff: yy / ff - np.log(yy / ff) - 1           # noqa: E731
    cs = np.mean(Yv / fv)
    S.num("4", "a", "B.4", "a", "sample identity: mean QL(Y,f) = mean QL(Y, c* f) + q(c*) (500 random pairs)",
          float(np.mean(ql(Yv, fv))), float(np.mean(ql(Yv, cs * fv)) + cs - 1 - math.log(cs)), 1e-12)
    # (b)
    w1, w2, w3, m1, m2, m3, kap = sp.symbols("w1 w2 w3 m1 m2 m3 kappa", positive=True)
    Lp = w1 * (m1 / kap + sp.log(kap)) + w2 * (m2 / kap + sp.log(kap)) + w3 * (m3 / kap + sp.log(kap))
    ks = sp.solve(sp.diff(Lp, kap), kap)[0]
    S.sym("4", "b", "B.4", "b", "first-order condition: sum w_i c*_i(kappa) = sum w_i at the optimal common scale",
          (w1 * m1 + w2 * m2 + w3 * m3) / ks - (w1 + w2 + w3))
    S.sym("4", "b", "B.4", "b", "q(c) = (c-1)^2/2 + O((c-1)^3)", sp.series(q, cc, 1, 3).removeO(), (cc - 1) ** 2 / 2)
    S.sym("4", "b", "B.4", "b", "ln c = (c - 1) + O((c - 1)^2)", sp.series(sp.log(cc), cc, 1, 2).removeO(), cc - 1)
    S.sym("4", "b", "B.4", "b", "q(c) - (ln c)^2/2 = O((c - 1)^3)", sp.series(q - sp.log(cc) ** 2 / 2, cc, 1, 3).removeO(), 0)
    # (c)
    So, se2, sc2, DR, bb = sp.symbols("S_o sigma_eta2 sigma_c2 Delta_R beta", positive=True)
    Er2 = So + sc2
    psi = (bb ** 2 * (So + se2) + sc2 * (1 + DR / (4 * sp.log(2)))) / Er2
    s_, n_ = So / Er2, se2 / Er2
    S.sym("4", "c", "B.4", "c", "psi(beta) = 1 - (1 - beta^2)s + beta^2 n + sigma_c^2 Delta_R/(4 ln 2 E[r^2])",
          psi, 1 - (1 - bb ** 2) * s_ + bb ** 2 * n_ + sc2 * DR / (4 * sp.log(2) * Er2))
    S.sym("4", "c", "B.4", "c", "first order (Delta_R = 2 ln 2 rho^2): psi = 1 - (1 - beta^2)s + (beta^2 + 1/2) n",
          psi.subs(DR, 2 * sp.log(2) * se2 / sc2), 1 - (1 - bb ** 2) * s_ + (bb ** 2 + sp.Rational(1, 2)) * n_)
    # (d)
    av, gv, nv, sv, tv, xi = sp.symbols("a gamma n s t xi", positive=True)
    S.sym("4", "d", "B.4", "d", "ln(a + gamma n) = ln gamma + ln(a/gamma + n), so the variances are equal",
          sp.expand_log(sp.log(av + gv * nv), force=True) - sp.expand_log(sp.log(gv) + sp.log(av / gv + nv), force=True))
    u = sp.symbols("u", positive=True)          # u = beta^2
    aa, gg = 1 - (1 - u) * sv, u + sp.Rational(1, 2)
    S.sym("4", "d", "B.4", "d", "d(a/gamma)/d(beta^2) = (s gamma - a)/gamma^2 = (3s/2 - 1)/gamma^2",
          sp.diff(aa / gg, u), (sp.Rational(3, 2) * sv - 1) / gg ** 2)
    S.sym("4", "d", "B.4", "d", "s gamma - a = 3s/2 - 1", sv * gg - aa, sp.Rational(3, 2) * sv - 1)
    g = np.random.default_rng(SEED + 41)
    ns = g.uniform(0, 0.6, 2000)
    var = lambda xv: float(np.var(np.log(xv + ns)))             # noqa: E731
    der = (var(1.0 + 1e-6) - var(1.0 - 1e-6)) / 2e-6
    cov = 2 * float(np.cov(np.log(1.0 + ns), 1 / (1.0 + ns), bias=True)[0, 1])
    S.num("4", "d", "B.4", "d", "d/dxi Var(ln(xi + n)) = 2 Cov(ln(xi + n), 1/(xi + n)) (xi = 1, finite differences)", cov, der, 1e-7)
    S.add("4", "d", "B.4", "d", "that covariance is negative (oppositely monotone in n), for xi in a grid", "numerical",
          all(np.cov(np.log(xv + ns), 1 / (xv + ns), bias=True)[0, 1] < 0 for xv in np.linspace(0.05, 5, 40)), "")
    disp = [np.var(np.log(1 - (1 - bv ** 2) * 0.8 + (bv ** 2 + 0.5) * ns)) for bv in np.linspace(0, 1, 11)]
    S.add("4", "d", "B.4", "d", "the condition s < 2/3 matters: with s = 0.8 the dispersion decreases in beta", "numerical",
          bool((np.diff(disp) < 0).all()), "counterexample outside the stated range")
    tt = (1 - u) / (1 + gg * nv)
    S.sym("4", "d", "B.4", "d", "share-only: 1 - (1 - beta^2)s_i + gamma n = (1 + gamma n)(1 - t s_i)", 1 - (1 - u) * sv + gg * nv, (1 + gg * nv) * (1 - tt * sv))
    S.sym("4", "d", "B.4", "d", "dt/d(beta^2) = -(1 + 3n/2)/(1 + gamma n)^2 < 0", sp.diff(tt, u), -(1 + sp.Rational(3, 2) * nv) / (1 + gg * nv) ** 2)
    ss = g.uniform(0.1, 0.6, 2000)
    vt = lambda tv_: float(np.var(np.log(1 - tv_ * ss)))       # noqa: E731
    der = (vt(0.5 + 1e-6) - vt(0.5 - 1e-6)) / 2e-6
    cov = 2 * float(np.cov(np.log(1 - 0.5 * ss), -ss / (1 - 0.5 * ss), bias=True)[0, 1])
    S.num("4", "d", "B.4", "d", "d/dt Var(ln(1 - t s)) = 2 Cov(ln(1 - t s), -s/(1 - t s)) (t = 0.5)", cov, der, 1e-7)
    S.add("4", "d", "B.4", "d", "that covariance is positive (both decreasing in s), for t in a grid", "numerical",
          all(np.cov(np.log(1 - tv_ * ss), -ss / (1 - tv_ * ss), bias=True)[0, 1] > 0 for tv_ in np.linspace(0.01, 1.5, 40)), "")
    S.sym("4", "d", "B.4", "d", "at beta = 1, t = 0: psi_i = 1 + gamma n is the same for every security", tt.subs(u, 1), 0)


# =============================================================================================
# Proposition 5 (Appendix B.5)
# =============================================================================================

def prop5(S: Steps) -> None:
    r0, r1, a1, a2, a3 = sp.symbols("rho_0 rho_1 a_1 a_2 a_3", positive=True)
    kap = (r0 * a1 + r1 * a2 + r1 * a3) / (a1 + a2 + a3)
    om = (a2 + a3) / (a1 + a2 + a3)
    S.sym("5", "a", "B.5", "a", "ratio of sums with R_s = rho_j(s) a_s is omega rho_1 + (1 - omega) rho_0", kap, om * r1 + (1 - om) * r0)
    S.sym("5", "a", "", "", "relative bias kappa/rho_1 - 1 = (1 - omega)(rho_0/rho_1 - 1)", kap / r1 - 1, (1 - om) * (r0 / r1 - 1))
    ok = True
    for L in (10, 20, 60, 120):
        A = np.ones(3 * L)
        post = np.arange(3 * L) >= L
        w = pd.Series(np.where(post, A, 0.0)).rolling(L).sum() / pd.Series(A).rolling(L).sum()
        j = np.arange(2 * L)
        ok &= bool(np.allclose(w.to_numpy()[L:3 * L], np.minimum((j + 1) / L, 1.0), atol=1e-15))
    S.add("5", "b", "B.5", "b", "constant kernel mass: omega_{tau+j} = min((j+1)/L, 1) for L = 10, 20, 60, 120", "numerical", ok, "")
    dl, w = sp.symbols("delta omega", positive=True)
    S.sym("5", "c", "B.5", "c", "ln((1 - omega) rho_1 e^delta + omega rho_1) - ln rho_1 = (1 - omega) delta + O(delta^2)",
          sp.series(sp.log((1 - w) * sp.exp(dl) + w), dl, 0, 2).removeO(), (1 - w) * dl)
    j, L = sp.symbols("j L", integer=True, positive=True)
    ssum = sp.summation((1 - (j + 1) / L) ** 2, (j, 0, L - 1))
    S.sym("5", "c", "B.5", "c", "sum_{j=0}^{L-1} (1 - (j+1)/L)^2 = (L-1)(2L-1)/(6L)", ssum, (L - 1) * (2 * L - 1) / (6 * L))
    S.sym("5", "c", "B.5", "c", "(L-1)(2L-1)/(6L) = L/3 - 1/2 + 1/(6L) = L/3 + O(1)", (L - 1) * (2 * L - 1) / (6 * L), L / 3 - sp.Rational(1, 2) + 1 / (6 * L))
    lam, v, Lr = sp.symbols("lambda v L", positive=True)
    loss = (lam * dl ** 2 * Lr / 3 + v / Lr) / 2
    Ls = sp.sqrt(3 * v / (lam * dl ** 2))
    S.sym("5", "c", "B.5", "c", "d/dL (1/2)(lambda delta^2 L/3 + v/L) = 0 at L* = sqrt(3v/(lambda delta^2))", sp.diff(loss, Lr).subs(Lr, Ls))
    S.sym("5", "c", "B.5", "c", "second derivative v/L^3 > 0 at L*", sp.diff(loss, Lr, 2), v / Lr ** 3)
    S.sym("5", "c", "B.5", "c", "minimum value sqrt(lambda delta^2 v/3)", loss.subs(Lr, Ls), sp.sqrt(lam * dl ** 2 * v / 3))
    eps = sp.symbols("epsilon", real=True)
    S.sym("5", "c", "B.5", "c", "q(e^eps) = e^eps - 1 - eps = eps^2/2 + O(eps^3)", sp.series(sp.exp(eps) - 1 - eps, eps, 0, 3).removeO(), eps ** 2 / 2)
    uu = sp.symbols("u", positive=True)
    S.sym("5", "c", "", "", "the factor 1/3 = int_0^1 (1 - u)^2 du", sp.integrate((1 - uu) ** 2, (uu, 0, 1)), sp.Rational(1, 3))
    Kb, T, sdl = sp.symbols("K T Sigma_delta2", positive=True)
    S.sym("5", "c", "", "", "B4: with lambda = K/T and mean delta^2 = Sigma/K, L* = sqrt(3 v T/Sigma delta^2)",
          sp.sqrt(3 * v / ((Kb / T) * (sdl / Kb))), sp.sqrt(3 * v * T / sdl))
    ap = pd.read_csv(TAB / "table122_theory_applications.csv")
    b4 = ap[ap.part == "B4"]
    vv = float(b4[b4.statistic.str.startswith("v,")]["value"].iloc[0])
    Lst = float(b4[b4.statistic.str.startswith("L*")]["value"].iloc[0])
    dls = b4[b4.statistic.str.startswith("delta")]["value"].to_numpy()
    Tn = macro("b4-T")
    S.num("5", "c", "", "", "B4: L* = sqrt(3 v T/sum delta^2) from the table's v, deltas and T", Lst,
          math.sqrt(3 * vv * Tn / float((dls ** 2).sum())), 1e-6 * Lst)
    S.num("5", "c", "", "", "B4: the quoted L* (macro b4-Lstar) is the table's value rounded", round(Lst), macro("b4-Lstar"), 1e-12)


# =============================================================================================
# Proposition 6 (Appendix B.6) and the M14 module's algebra
# =============================================================================================

def prop6(S: Steps, quick: bool) -> None:
    IV, U0, U1, Z = sp.symbols("IV U0 U1 Z")
    vI, v0, v1, c01, b1 = sp.symbols("v_IV v_0 v_1 c_01 beta_1", real=True)
    cz, c0z, c1z = sp.symbols("c_IVZ c_0Z c_1Z", real=True)
    mom = {frozenset((IV,)): vI, frozenset((U0,)): v0, frozenset((U1,)): v1, frozenset((U0, U1)): c01,
           frozenset((IV, U0)): 0, frozenset((IV, U1)): 0, frozenset((IV, Z)): cz, frozenset((U0, Z)): c0z,
           frozenset((U1, Z)): c1z, frozenset((Z,)): 1}
    rv = [IV, U0, U1, Z]
    X0, X1 = IV + U0, b1 * IV + U1                    # centred within security
    S.sym("6", "b", "B.6", "b", "Cov(X_k, X_0) = beta_k Var(IV) + Cov(U_k, U_0)", E(X1 * X0, rv, mom), b1 * vI + c01)
    S.sym("6", "b", "B.6", "b", "Var(X_0) = Var(IV) + Var(U_0)", E(X0 * X0, rv, mom), vI + v0)
    mk, m0, bk = sp.symbols("mbar_k mbar_0 beta_k", positive=True)
    S.sym("6", "b", "B.6", "b", "mean ratio = beta_k + delta_k with delta_k = (mean X_k - beta_k mean X_0)/mean X_0",
          mk / m0, bk + (mk - bk * m0) / m0)
    S.sym("6", "c", "B.6", "c", "Cov(X_k, Z) = beta_k Cov(IV, Z) + Cov(U_k, Z) (bilinearity)", E(X1 * Z, rv, mom), b1 * cz + c1z)
    S.sym("6", "c", "B.6", "c", "the instrumented estimand is [beta_k Cov(V,Z) + Cov(U_k,Z)]/[Cov(V,Z) + Cov(U_0,Z)]",
          E(X1 * Z, rv, mom) / E(X0 * Z, rv, mom), (b1 * cz + c1z) / (cz + c0z))
    S.sym("6", "a", "B.6", "a", "with Cov(U, Z) = 0: Cov(X_k, Z) = beta_k Cov(X_0, Z) (rank one)",
          E(X1 * Z, rv, mom).subs({c0z: 0, c1z: 0}) - b1 * E(X0 * Z, rv, mom).subs({c0z: 0, c1z: 0}))
    # simulation: E[U | F_{t-1}] = 0, Cov(IV - V, Z) = 0 and the rank-one covariances, in script 45's design
    rng = np.random.default_rng(SEED + 6)
    Nsec, T = (60, 400) if quick else (200, 600)
    iv, vv, u0, u1, z1 = [], [], [], [], []
    for i in range(Nsec):
        e = rng.standard_normal(T + 30) * 0.3
        h = np.zeros(T + 30)
        for tt in range(1, T + 30):
            h[tt] = 0.95 * h[tt - 1] + e[tt]
        lev = 0.2 * rng.standard_normal()
        IVv = np.exp(h[30:] + lev)
        V = np.exp(0.95 * h[29:-1] + lev + 0.5 * 0.09)           # E[IV_t | F_{t-1}] for this design
        gs, e0, e1 = (rng.standard_normal(T) for _ in range(3))
        U0v, U1v = IVv * (0.8 * e0 + 0.6 * gs), IVv * (0.5 * e1 + 0.6 * gs)
        X0v = IVv + U0v
        Zv = np.concatenate([[np.nan], X0v[:-1]])               # instrument dated t-1
        iv.append(IVv[1:]); vv.append(V[1:]); u0.append(U0v[1:]); u1.append(U1v[1:]); z1.append(Zv[1:])
    IVa, Va, U0a, U1a, Za = (np.concatenate(x) for x in (iv, vv, u0, u1, z1))
    Zc = Za - Za.mean()
    for nm, arr in (("U_0", U0a), ("U_1", U1a), ("IV - V", IVa - Va)):
        v, se = s45.batch_mean(arr * Zc)
        S.mc("6", "a" if nm != "IV - V" else "c", "B.6", "a" if nm != "IV - V" else "c",
             f"E[{nm} x Z_(t-1)] = 0 (martingale difference against an instrument dated t-1)", 0.0, v, se)
    X1a = 0.3 + 0.8 * IVa + U1a
    X0a = IVa + U0a
    num_, se_ = s45.batch_ratio((X1a - X1a.mean()) * Zc, (X0a - X0a.mean()) * Zc)
    S.mc("6", "a", "B.6", "a", "Cov(X_1, Z)/Cov(X_0, Z) = beta_1 = 0.8 with an instrument dated t-1", 0.8, num_, se_)
    # (d): cited GMM asymptotics, verified by script 45's simulations (consistency and J size)
    led = pd.read_csv(TAB / "table121_theory_checks.csv")
    p6 = led[led.proposition.astype(str) == "6"]
    S.add("6", "d", "B.6", "d", "GMM consistency and the J test's size, checked in simulation (table121, Proposition 6 rows)",
          "Monte Carlo", bool(len(p6) >= 8 and p6["pass"].all()), f"{int(p6['pass'].sum())} of {len(p6)} rows pass")
    # (e) the composite
    a11, a12, a22, bb1, bb2, vI2 = sp.symbols("o11 o12 o22 b1 b2 v", positive=True)
    Om = sp.Matrix([[a11, a12], [a12, a22]])
    B = sp.Matrix([bb1, bb2])
    Sx = vI2 * B * B.T + Om
    lhs = Sx.inv() * B * (1 + vI2 * (B.T * Om.inv() * B)[0])
    S.sym("6", "e", "B.6", "e", "Sherman-Morrison: Sigma^-1 beta (1 + v beta' Omega^-1 beta) = Omega^-1 beta (2 x 2, general)",
          sp.simplify(lhs - Om.inv() * B), sp.zeros(2, 1))
    w = Sx.inv() * B / (B.T * Sx.inv() * B)[0]
    mu = 1 / (B.T * Sx.inv() * B)[0]
    S.sym("6", "e", "B.6", "e", "KKT: Sigma w* = mu beta with mu = 1/(beta' Sigma^-1 beta), and beta' w* = 1",
          sp.Matrix([sp.simplify(x_) for x_ in (Sx * w - mu * B)] + [sp.simplify((B.T * w)[0] - 1)]), sp.zeros(3, 1))
    w1, w2 = sp.symbols("w1 w2", real=True)
    W = sp.Matrix([w1, w2])
    S.sym("6", "e", "B.6", "e", "w' Sigma w = v (w' beta)^2 + w' Omega w, = v + w' Omega w under w' beta = 1",
          (W.T * Sx * W)[0], vI2 * ((W.T * B)[0]) ** 2 + (W.T * Om * W)[0])
    g = np.random.default_rng(SEED + 61)
    worst = 0.0
    for _ in range(200):
        Bn = g.uniform(0.5, 1.5, 4)
        Q = g.standard_normal((4, 4))
        On = Q @ Q.T + 0.3 * np.eye(4)
        Sn = 1.7 * np.outer(Bn, Bn) + On
        wa = np.linalg.solve(Sn, Bn); wa /= Bn @ wa
        wb = np.linalg.solve(On, Bn); wb /= Bn @ wb
        worst = max(worst, float(np.abs(wa - wb).max()))
    S.add("6", "e", "B.6", "e", "the two weight formulas agree on 200 random 4 x 4 designs", "numerical", worst < 1e-10, f"max gap {worst:.1e}")
    # M14's noise bounds (module docstring): 1/(beta'Sigma^-1 beta) = Var(IV) + 1/(beta'Omega^-1 beta)
    S.sym("6", "e", "", "", "M14 bounds: 1/(beta' Sigma^-1 beta) = Var(IV) + 1/(beta' Omega^-1 beta), so D_k = n_k - 1/(beta'Omega^-1 beta) <= n_k",
          1 / (B.T * Sx.inv() * B)[0], vI2 + 1 / (B.T * Om.inv() * B)[0])


# =============================================================================================
# The paper's own mathematical claims, checked on the data where they are identities
# =============================================================================================

# =============================================================================================
# Proposition 7 (Appendix B.7): Anam's kernel under a noisy open
# =============================================================================================

def prop7(S: Steps, quick: bool) -> None:
    s48 = _load("s48_for_46", "48_kernel_theory.py")
    os_, eta = sp.symbols("ostar eta")
    so, ce, ve = sp.symbols("s_oo c_oe v_ee", real=True)
    mom = {frozenset((os_,)): so, frozenset((os_, eta)): ce, frozenset((eta,)): ve}
    rv = [os_, eta]
    o = os_ + eta
    Eoo, Eoos = E(o * o, rv, mom), E(o * os_, rv, mom)
    b = Eoos / Eoo
    # (a)
    S.sym("7", "a", "B.7", "a", "E[(o* - b o)^2] = E[o*^2] - 2b E[o o*] + b^2 E[o^2]",
          E((os_ - b * o) ** 2, rv, mom) - (so - 2 * b * Eoos + b ** 2 * Eoo))
    S.sym("7", "a", "B.7", "a", "with E[o o*] = b E[o^2] this is E[o*^2] - b^2 E[o^2]",
          E((os_ - b * o) ** 2, rv, mom) - (so - b ** 2 * Eoo))
    S.sym("7", "a", "B.7", "a", "E[(b o)^2] = E[o*^2] - E[(o* - b o)^2]",
          E((b * o) ** 2, rv, mom) - (so - E((os_ - b * o) ** 2, rv, mom)))
    mom0 = dict(mom)
    mom0[frozenset((os_, eta))] = 0
    Eoo0, b0 = E(o * o, rv, mom0), E(o * os_, rv, mom0) / E(o * o, rv, mom0)
    S.sym("7", "a", "B.7", "a", "if E[o* eta] = 0: b E[o^2] = E[o*^2]", b0 * Eoo0 - so)
    S.sym("7", "a", "B.7", "a", "if E[o* eta] = 0: E[(b o)^2] = b E[o*^2]", b0 ** 2 * Eoo0 - b0 * so)
    S.sym("7", "a", "B.7", "a", "if E[o* eta] = 0: E[pi(o)] = b^2 E[o^2] + b(1-b) E[o^2] = E[o*^2]",
          b0 ** 2 * Eoo0 + b0 * (1 - b0) * Eoo0 - so)
    S.sym("7", "a", "B.7", "a", "Gaussian: Var(o* | o) = E[o*^2] - b^2 E[o^2] = b(1-b) E[o^2]",
          (so - b0 ** 2 * Eoo0) - b0 * (1 - b0) * Eoo0)
    n = 200_000 if quick else 2_000_000
    rng = np.random.default_rng(SEED + 7)
    sv, tv = 1.0, 0.8
    x = rng.normal(0, sv, n)
    y = x + rng.normal(0, tv, n)
    bb = sv * sv / (sv * sv + tv * tv)
    X = np.column_stack([np.ones(n), y * y])
    coef = np.linalg.lstsq(X, x * x, rcond=None)[0]
    res = x * x - X @ coef
    cov = np.linalg.inv(X.T @ X) * np.mean(res ** 2)
    S.mc("7", "a", "B.7", "a", "Gaussian: E[o*^2 | o] has slope b^2 on o^2 (simulation)", bb * bb, coef[1], math.sqrt(cov[1, 1]))
    S.mc("7", "a", "B.7", "a", "Gaussian: E[o*^2 | o] has intercept b(1-b)E[o^2] (simulation)",
         bb * (1 - bb) * (sv * sv + tv * tv), coef[0], math.sqrt(cov[0, 0]))
    moo, mrr, s_ = sp.symbols("m_oo m_rr s", positive=True)
    bq = sp.symbols("b", real=True)
    S.sym("7", "a", "B.7", "a", "deficit at E[o*^2] = b^2 m_oo is 0", (bq ** 2 * moo) - bq ** 2 * moo)
    S.sym("7", "a", "B.7", "a", "deficit at E[o*^2] = m_rr is m_rr - b^2 m_oo (Prop. 1(e) endpoints)",
          (mrr - bq ** 2 * moo) - (mrr - bq ** 2 * moo))
    # (b)
    m_ = 400_000 if not quick else 50_000
    o_ = rng.normal(0, 0.02, m_)
    c_ = rng.normal(0, 0.02, m_)
    u_ = np.maximum(0, c_) + rng.exponential(0.01, m_)
    d_ = np.minimum(0, c_) - rng.exponential(0.01, m_)
    h, l = o_ + u_, o_ + d_
    for bval in (0.0, 0.25, 0.6, 1.0):
        bo = bval * o_
        Rs = (u_ - d_) + np.maximum(0, bo - h) + np.maximum(0, l - bo)
        S.path("7", "b", "B.7", "b", f"the three cases give R* = max(h, b o) - min(l, b o), b = {bval}",
               Rs - (np.maximum(h, bo) - np.minimum(l, bo)), tol=1e-15)
        S.path("7", "b", "B.7", "b", f"b o lies between 0 and o (a convex combination), b = {bval}",
               np.maximum(0, np.abs(bo) - np.abs(o_)) + np.maximum(0, -bo * o_), tol=0.0)
        TR = np.maximum(h, 0) - np.minimum(l, 0)
        S.path("7", "b", "B.7", "b", f"R <= R* <= TR, b = {bval}",
               np.maximum(0, (u_ - d_) - Rs) + np.maximum(0, Rs - TR), tol=1e-15)
    S.path("7", "b", "B.7", "b", "at b = 1, b o = o lies in [l, h], so R* = R",
           (np.maximum(h, o_) - np.minimum(l, o_)) - (u_ - d_), tol=1e-15)
    hx = math.log(1.05)
    S.num("7", "b", "B.7", "b", "the audit's bar: R* = TR = ln(1.05) and A_0 = 0.8 ln(1.05)^2/(4 ln 2)",
          0.8 * hx ** 2 / (4 * LN2), (1 - 0.2) * (max(hx, 0.0) - min(0.0, 0.0)) ** 2 / (4 * LN2), 1e-15)
    # (c), the true range: ingredients
    a = sp.symbols("a", real=True)
    u = sp.symbols("u", nonnegative=True)
    e_, xx = sp.symbols("e x", positive=True)
    psi = phi(a) - a * PHIBAR(a)
    S.sym("7", "c", "B.7", "c", "psi'(a) = -Phibar(a)", sp.diff(psi, a) + PHIBAR(a))
    S.sym("7", "c", "B.7", "c", "psi(0) = 1/sqrt(2 pi)", psi.subs(a, 0) - 1 / sp.sqrt(2 * sp.pi))
    zz = sp.symbols("zz", real=True)
    S.sym("7", "c", "B.7", "c", "E[(Z - a)^+] = psi(a)",
          sp.integrate((zz - a) * phi(zz), (zz, a, sp.oo)) - psi, {"a": (-2.0, 3.0)})
    S.sym("7", "c", "B.7", "c", "E[(s Z - u)^+] = s psi(u/s)",
          sp.integrate((s_ * zz - u) * phi(zz), (zz, u / s_, sp.oo)) - s_ * psi.subs(a, u / s_))
    S.sym("7", "c", "B.7", "c", "d/ds {s psi(u/s)} = phi(u/s)", sp.diff(s_ * psi.subs(a, u / s_), s_) - phi(u / s_))
    rp_ = sp.symbols("rho", positive=True)
    S.sym("7", "c", "B.7", "c", "E[(eta^+)^2] = rho^2/2", sp.integrate(zz ** 2 * phi(zz / rp_) / rp_, (zz, 0, sp.oo)) - rp_ ** 2 / 2)
    S.sym("7", "c", "B.7", "c", "f_M(0) = 2 phi(0) = sqrt(2/pi)", 2 * phi(0) - sp.sqrt(2 / sp.pi))
    S.sym("7", "c", "B.7", "c", "int_0^e (e - x) f_M(x) dx = f_M(0) e^2/2 + O(e^3)",
          sp.series(sp.integrate((e_ - xx) * 2 * phi(xx), (xx, 0, e_)), e_, 0, 3).removeO() - sp.sqrt(2 / sp.pi) * e_ ** 2 / 2)
    k = sp.symbols("k", integer=True, positive=True)
    S.sym("7", "c", "B.7", "c", "sum (-1)^(k+1)/k = ln 2, so E[U] = 2 sqrt(pi/2) ln 2 = sqrt(2 pi) ln 2",
          2 * sp.sqrt(sp.pi / 2) * sp.summation((-1) ** (k + 1) / k, (k, 1, sp.oo)) - sp.sqrt(2 * sp.pi) * sp.log(2))
    S.num("7", "c", "B.7", "c", "E[U] from the law of U, by quadrature", math.sqrt(2 * math.pi) * LN2, s48.meander_mean(), 1e-9)
    for xv in (0.5, 1.0, 2.0):
        S.num("7", "c", "B.7", "c", f"the meander law is the images limit of (-m | M < a), x = {xv}",
              s48.meander_cdf(xv), s48.meander_cdf_from_images(xv), 2e-4)
    EU = sp.sqrt(2 * sp.pi) * sp.log(2)
    Xs = sp.symbols("X", real=True)
    S.sym("7", "c", "B.7", "c", "assembly: (2/sqrt(2 pi))(E[U]/2 + X)/(4 ln 2) = 1/4 + X/(2 sqrt(2 pi) ln 2)",
          (2 / sp.sqrt(2 * sp.pi)) * (EU / 2 + Xs) / (4 * sp.log(2)) - (sp.Rational(1, 4) + Xs / (2 * sp.sqrt(2 * sp.pi) * sp.log(2))))
    S.sym("7", "c", "B.7", "c", "upper bound: X <= s/sqrt(2 pi) gives 1/4 + s/(4 pi ln 2)",
          sp.Rational(1, 4) + (s_ / sp.sqrt(2 * sp.pi)) / (2 * sp.sqrt(2 * sp.pi) * sp.log(2)) - (sp.Rational(1, 4) + s_ / (4 * sp.pi * sp.log(2))))
    S.sym("7", "c", "B.7", "c", "lower bound: X >= s/sqrt(2 pi) - E[U]/2 gives s/(4 pi ln 2)",
          sp.Rational(1, 4) + (s_ / sp.sqrt(2 * sp.pi) - EU / 2) / (2 * sp.sqrt(2 * sp.pi) * sp.log(2)) - s_ / (4 * sp.pi * sp.log(2)))
    S.sym("7", "c", "B.7", "c", "psi(a) >= psi(0) - a/2 because int_0^a Phibar <= a/2",
          (psi.subs(a, 0) - sp.integrate(sp.Rational(1, 2), (zz, 0, a))) - (1 / sp.sqrt(2 * sp.pi) - a / 2))
    S.sym("7", "c", "B.7", "c", "large s: int_0^{U/s} z phi(0) dz = phi(0) U^2/(2 s^2), times s gives phi(0) U^2/(2s)",
          s_ * sp.integrate(zz * phi(0), (zz, 0, u / s_)) - phi(0) * u ** 2 / (2 * s_))
    grid = np.linspace(0.05, 6.0, 40)
    g = np.array([s48.gamma_tr(v) for v in grid])
    S.num("7", "c", "B.7", "c", "gamma_TR is increasing (min increment on a grid of 40)", 0.0,
          float(min(0.0, np.min(np.diff(g)))), 0.0)
    for v in (0.3, 1.0, 3.0):
        S.num("7", "c", "B.7", "c", f"the two numerical routes to gamma_TR agree, s = {v}", s48.gamma_tr(v),
              s48.gamma_tr_direct(v), 2e-4)
    # (c), the kernels
    lam = sp.symbols("lambda_0", positive=True)
    bb_ = s_ ** 2 / (s_ ** 2 + rp_ ** 2)
    w = lam * (1 - bb_)
    S.sym("7", "c", "B.7", "c", "b = s^2/(s^2 + rho^2) = 1 - rho^2/s^2 + O(rho^4)",
          sp.series(bb_, rp_, 0, 4).removeO() - (1 - rp_ ** 2 / s_ ** 2))
    S.sym("7", "c", "B.7", "c", "E[(b o)^2] = b^2 (s^2 + rho^2) = s^2 - rho^2 + O(rho^4)",
          sp.series(bb_ ** 2 * (s_ ** 2 + rp_ ** 2), rp_, 0, 4).removeO() - (s_ ** 2 - rp_ ** 2))
    EA = (1 - w) * (bb_ ** 2 * (s_ ** 2 + rp_ ** 2) + 1 + rp_ ** 2 / 2) + w * (s_ ** 2 + 1)
    S.sym("7", "c", "B.7", "c", "E[A] = s^2 + 1 - rho^2/2 + O(rho^4) (loading -1/2, any s and lambda_0)",
          sp.series(EA, rp_, 0, 4).removeO() - (s_ ** 2 + 1 - rp_ ** 2 / 2))
    EP = (1 - w) * (bb_ ** 2 * (s_ ** 2 + rp_ ** 2) + bb_ * (1 - bb_) * (s_ ** 2 + rp_ ** 2) + 1 + rp_ ** 2 / 2) + w * (s_ ** 2 + 1)
    S.sym("7", "c", "B.7", "c", "with pi(o): E = s^2 + 1 + rho^2/2 + O(rho^4) (loading +1/2)",
          sp.series(EP, rp_, 0, 4).removeO() - (s_ ** 2 + 1 + rp_ ** 2 / 2))
    S.sym("7", "c", "B.7", "c", "E[pi(o)] = s^2 exactly under the model", bb_ ** 2 * (s_ ** 2 + rp_ ** 2) + bb_ * (1 - bb_) * (s_ ** 2 + rp_ ** 2) - s_ ** 2)
    # (c), simulation of the loadings: the ledger of script 48 (first-order loadings by extrapolation in rho)
    led = pd.read_csv(TAB / "table133_theory_kernel_checks.csv")
    fo = led[led["check"].str.startswith("c: first-order loading")]
    for r in fo.itertuples():
        S.add("7", "c", "B.7", "c", f"{r.check[3:]} ({r.design.split(',')[0]}), against simulation (script 48)",
              "Monte Carlo", bool(r._8), f"theory {r.theory:.6g}, simulated {r.value:.6g} (SE {r.se:.2g})")


# =============================================================================================
# Proposition 8 (Appendix B.8): the market-implied open
# =============================================================================================

def prop8(S: Steps, quick: bool) -> None:
    """Every step of B.8. The algebra is symbolic on a panel of N = 4 securities (security 1 is i); the
    sample identity, the kernel cases and the discrete range are pathwise; script 54's checks are added."""
    from nepsevol.estimators import anam as AN_
    from nepsevol.estimators import anam2 as A2_
    N = 4
    f = sp.Symbol("f", real=True)
    zt = sp.symbols("zeta1:5", real=True)
    et = sp.symbols("eta1:5", real=True)
    xs = sp.symbols("x1:5", real=True)
    bt = sp.symbols("beta1:5", positive=True)
    sf, = sp.symbols("sigma_f", positive=True),
    sz = sp.symbols("sz1:5", positive=True)
    se = sp.symbols("se1:5", positive=True)
    cz = sp.symbols("c1:5", real=True)
    sx = sp.symbols("sx1:5", positive=True)
    rv = [f, *zt, *et, *xs]
    mom = {}
    for u_ in rv:
        for v_ in rv:
            mom[frozenset((u_, v_))] = sp.Integer(0)
    mom[frozenset((f,))] = sf ** 2
    for j in range(N):
        mom[frozenset((zt[j],))] = sz[j] ** 2
        mom[frozenset((et[j],))] = se[j] ** 2
        mom[frozenset((zt[j], et[j]))] = cz[j]
        mom[frozenset((xs[j],))] = sx[j] ** 2
    o = [bt[j] * f + zt[j] + et[j] for j in range(N)]
    r = [bt[j] * f + zt[j] + xs[j] for j in range(N)]
    m1 = sum(o[1:]) / (N - 1)
    bbar1 = sum(bt[1:]) / (N - 1)
    V1 = sum(sz[j] ** 2 + se[j] ** 2 + 2 * cz[j] for j in range(1, N)) / (N - 1) ** 2
    # (a)
    S.sym("8", "a", "B.8", "a", "m_-i does not depend on security i's news: d m_-i / d zeta_i = 0", sp.diff(m1, zt[0]))
    S.sym("8", "a", "B.8", "a", "m_-i does not depend on security i's error: d m_-i / d eta_i = 0", sp.diff(m1, et[0]))
    S.sym("8", "a", "B.8", "a", "E[m_-i eta_i] = 0 (independence and zero means)", E(m1 * et[0], rv, mom))
    # (b)
    err = m1 - bbar1 * f
    S.sym("8", "b", "B.8", "b", "m_-i - beta_bar_-i f = (N-1)^-1 sum_{j != i} (zeta_j + eta_j)",
          err - sum(zt[j] + et[j] for j in range(1, N)) / (N - 1))
    S.sym("8", "b", "B.8", "b", "E[(m_-i - beta_bar_-i f)^2] = V_N (second moments add)", E(err ** 2, rv, mom) - V1)
    rng = np.random.default_rng(SEED + 8)
    ok = True
    for _ in range(2000):
        a2 = rng.uniform(0.1, 3.0, N - 1)
        ok &= a2.sum() / (N - 1) ** 2 <= a2.max() / (N - 1) + 1e-15
    S.add("8", "b", "B.8", "b", "V_N <= max / (N - 1) on 2,000 random draws of the second moments", "numerical", bool(ok),
          "sum of N-1 terms <= (N-1) max")
    # (c)
    S.sym("8", "c", "B.8", "c", "E[m_-i^2] = beta_bar_-i^2 sigma_f^2 + V_N", E(m1 ** 2, rv, mom) - (bbar1 ** 2 * sf ** 2 + V1))
    S.sym("8", "c", "B.8", "c", "E[r_i m_-i] = beta_i beta_bar_-i sigma_f^2 (E[x_i m_-i] = 0 by the assumption)",
          E(r[0] * m1, rv, mom) - bt[0] * bbar1 * sf ** 2)
    beta_, sf_, V_ = sp.symbols("beta s_f V", positive=True)
    bM = (beta_ * beta_ * sf_ ** 2) / (beta_ ** 2 * sf_ ** 2 + V_)
    S.sym("8", "c", "B.8", "c", "equal betas: b_M = beta^2 sigma_f^2 / (beta^2 sigma_f^2 + V_N)",
          bM - beta_ ** 2 * sf_ ** 2 / (beta_ ** 2 * sf_ ** 2 + V_))
    S.sym("8", "c", "B.8", "c", "and b_M -> 1 as V_N -> 0", sp.limit(bM, V_, 0) - 1)
    # (d)
    for i in range(N):
        S.sym("8", "d", "B.8", "d", f"E[o_i r_i] = beta_i^2 sigma_f^2 + E[zeta_i^2] + E[zeta_i eta_i] (i = {i + 1})",
              E(o[i] * r[i], rv, mom) - (bt[i] ** 2 * sf ** 2 + sz[i] ** 2 + cz[i]))
        S.sym("8", "d", "B.8", "d", f"E[o_i^2] = beta_i^2 sigma_f^2 + E[(zeta_i + eta_i)^2] (i = {i + 1})",
              E(o[i] ** 2, rv, mom) - (bt[i] ** 2 * sf ** 2 + sz[i] ** 2 + se[i] ** 2 + 2 * cz[i]))
    SM = sum(bt[j] ** 2 for j in range(N)) * sf ** 2
    SI = sum(sz[j] ** 2 + se[j] ** 2 + 2 * cz[j] for j in range(N))
    bI = sum(sz[j] ** 2 + cz[j] for j in range(N)) / SI
    mu = SM / (SM + SI)
    b = sum(E(o[j] * r[j], rv, mom) for j in range(N)) / sum(E(o[j] ** 2, rv, mom) for j in range(N))
    S.sym("8", "d", "B.8", "d", "b = mu + (1 - mu) b_I", b - (mu + (1 - mu) * bI))
    T_, n_ = (300, 25) if quick else (3000, 40)
    O = rng.normal(0, 1, (T_, n_)) + rng.normal(0, 0.5, (T_, 1))
    R_ = 0.6 * O + rng.normal(0, 1, (T_, n_))
    oM = O.mean(axis=1, keepdims=True) * np.ones_like(O)
    oI = O - oM
    S.path("8", "d", "B.8", "d", "in a sample, sum o_M o_I = 0 date by date", (oM * oI).sum(axis=1), tol=1e-10)
    bh = (O * R_).sum() / (O * O).sum()
    muh = (oM ** 2).sum() / (O ** 2).sum()
    bMh = (oM * R_).sum() / (oM ** 2).sum()
    bIh = (oI * R_).sum() / (oI ** 2).sum()
    S.path("8", "d", "B.8", "d", "the sample identity b = mu b_M + (1 - mu) b_I", np.array([bh - (muh * bMh + (1 - muh) * bIh)]), tol=1e-12)
    # (e)
    n = 2000 if quick else 20000
    PC = np.full(n, 100.0)
    Op = PC * np.exp(rng.normal(0, 0.01, n))
    Cp = Op * np.exp(rng.normal(0, 0.01, n))
    Hp = np.maximum(Op, Cp) * np.exp(np.abs(rng.normal(0, 0.004, n)) + 1e-6)
    Lp = np.minimum(Op, Cp) * np.exp(-np.abs(rng.normal(0, 0.004, n)) - 1e-6)
    co = AN_.bar_coordinates(Op, Hp, Lp, Cp, PC)
    zero_ = pd.Series(0.0, index=co.index)
    A = A2_.kernel(co["o"], co["c"], co["u"], co["d"], zero_)
    A0 = AN_.kernel(co["o"], co["c"], co["u"], co["d"], zero_)
    S.path("8", "e", "B.8", "e", "where the open moved and the bar has a range, A is the open-free kernel",
           ((A - A0) / A0).to_numpy(), tol=1e-12)
    mm = pd.Series(rng.normal(0, 0.01, n))
    st = pd.DataFrame({"o": 0.0, "c": 0.0, "u": 0.0, "d": 0.0}, index=mm.index)
    As = A2_.kernel(st["o"], st["c"], st["u"], st["d"], mm)
    S.path("8", "e", "B.8", "e", "a bar that never left the previous close: A = 2 (1 - w) m^2",
           (As - 2 * (1 - A2_.LAMBDA0) * mm ** 2).to_numpy(), tol=1e-18)
    A0s = AN_.kernel(st["o"], st["c"], st["u"], st["d"], zero_.iloc[:n])
    S.path("8", "e", "B.8", "e", "there the open-free kernel is 0", A0s.to_numpy(), tol=0.0)
    # (f)
    S.sym("8", "f", "B.8", "f", "lambda_1 = E[W(1)^2] = 1", sp.integrate(z ** 2 * phi(z), (z, -sp.oo, sp.oo)) - 1)
    reps = 2000 if quick else 20000
    for nn in (1, 2, 5, 10):
        W = np.cumsum(rng.standard_normal((reps, 4 * nn)) / math.sqrt(4 * nn), axis=1)
        fine = np.maximum(W.max(axis=1), 0) - np.minimum(W.min(axis=1), 0)
        coarse_pts = W[:, 3::4]
        coarse = np.maximum(coarse_pts.max(axis=1), 0) - np.minimum(coarse_pts.min(axis=1), 0)
        S.path("8", "f", "B.8", "f", f"R_n <= R_4n on nested grids (n = {nn})", np.maximum(coarse - fine, 0.0), tol=0.0)
    led = pd.read_csv(TAB / "table143_theory_market_open_checks.csv")
    for _, r_ in led.iterrows():
        part = r_["check"][1]
        how = "Monte Carlo" if "SE" in r_["rule"] else ("pathwise" if "identity" in r_["rule"] else "numerical")
        S.add("8", part, "B.8", part, f"{r_['check'][4:]} ({r_['design']}), script 54", how, bool(r_["pass"]),
              f"{r_['rule']}: theory {r_['theory']:.6g}, value {r_['value']:.6g}")


def paper(S: Steps, quick: bool) -> None:
    # Yang-Zhang identity (Section 6.7, M15 H11): sample moments, ddof = 1
    o1, o2, o3, o4, c1, c2, c3, c4, kv, rsb = sp.symbols("o1 o2 o3 o4 c1 c2 c3 c4 k RSbar", real=True)
    os_, cs_ = [o1, o2, o3, o4], [c1, c2, c3, c4]
    rs_ = [a + b for a, b in zip(os_, cs_)]
    mean = lambda v: sum(v) / len(v)                          # noqa: E731
    var = lambda v: sum((x - mean(v)) ** 2 for x in v) / (len(v) - 1)   # noqa: E731
    cov = lambda v, w: sum((x - mean(v)) * (y - mean(w)) for x, y in zip(v, w)) / (len(v) - 1)  # noqa: E731
    S.sym("paper", "6.7", "", "", "Var(r) = Var(o) + Var(c) + 2 Cov(o, c) for sample moments (ddof = 1, n = 4 symbolic)",
          var(rs_) - (var(os_) + var(cs_) + 2 * cov(os_, cs_)))
    YZ = var(os_) + kv * var(cs_) + (1 - kv) * rsb
    S.sym("paper", "6.7", "", "", "YZ - Var(r) = (1 - k)[mean RS - Var(c)] - 2 Cov(o, c), exactly",
          YZ - var(rs_) - ((1 - kv) * (rsb - var(cs_)) - 2 * cov(os_, cs_)))
    S.num("paper", "4.5", "", "", "Yang-Zhang weight k = 0.34/(1.34 + (n+1)/(n-1)) at n = 21", 0.34 / (1.34 + 22 / 20), s45.yz_k(21), 1e-15)
    # Garman-Klass on a valid bar
    R, c = sp.symbols("R c", positive=True)
    gk = R ** 2 / 2 - (2 * sp.log(2) - 1) * c ** 2
    S.sym("paper", "4.3", "", "", "GK - (3/2 - 2 ln 2) c^2 = (R^2 - c^2)/2 >= 0 when |c| <= R",
          gk - (sp.Rational(3, 2) - 2 * sp.log(2)) * c ** 2, (R ** 2 - c ** 2) / 2)
    S.add("paper", "4.3", "", "", "3/2 - 2 ln 2 > 0, so GK >= 0 on a valid bar", "symbolic",
          bool(sp.Rational(3, 2) - 2 * sp.log(2) > 0), f"3/2 - 2 ln 2 = {1.5 - 2 * LN2:.6f}")
    # the old Appendix A derivation and its correction
    eo, eta, ep, ec, ee = sp.symbols("e_o eta eps_prev e_c eps")
    s_oo, s_oe, s_ee, s_pp, s_cc, s_e2 = sp.symbols("S_oo S_oe S_ee S_pp S_cc S_e", real=True)
    momA = {frozenset((eo,)): s_oo, frozenset((eo, eta)): s_oe, frozenset((eta,)): s_ee, frozenset((ep,)): s_pp,
            frozenset((ec,)): s_cc, frozenset((ee,)): s_e2}
    for pair in [(eo, ep), (eo, ec), (eo, ee), (eta, ep), (eta, ec), (eta, ee), (ep, ec), (ep, ee), (ec, ee)]:
        momA[frozenset(pair)] = 0
    rvA = [eo, eta, ep, ec, ee]
    oA, cA = eo + eta - ep, ec - eta + ee
    S.sym("paper", "Appendix A", "", "", "old Appendix A: -E[oc] = E[e_o eta] + E[eta^2] under its assumptions",
          -E(oA * cA, rvA, momA) - (s_oe + s_ee))
    S.sym("paper", "Appendix A", "", "", "old Appendix A: E[o^2] = E[e_o^2] + 2E[e_o eta] + E[eta^2] + E[eps_prev^2]",
          E(oA * oA, rvA, momA) - (s_oo + 2 * s_oe + s_ee + s_pp))
    bq, xq = sp.symbols("b x", positive=True)
    yq = (sp.sqrt(5 - 4 * bq) - 1) / 2
    S.sym("paper", "Appendix A", "", "", "old Appendix A: y = (sqrt(5-4b) - 1)/2 solves y^2 + y = 1 - b", yq ** 2 + yq - (1 - bq), 0, {"b": (0.01, 0.99)})
    yx = (sp.sqrt(1 + 4 * xq) - 1) / 2
    S.sym("paper", "Appendix A", "", "", "old Appendix A: y = (sqrt(1+4x) - 1)/2 has y^2 = x - y <= x", yx ** 2 - (xq - yx))
    S.sym("paper", "Appendix A", "", "", "corrected Appendix A (round 17) is Proposition 1(c) in Appendix A's coordinates: o* = e_o - eps_prev",
          E((eta) ** 2, rvA, momA) - E(((oA - (eo - ep))) ** 2, rvA, momA))
    # M15's maintained model (independent errors): b = 1 + E[oc]/E[o^2], E[oc] = -Var(eta)
    momB = dict(momA)
    momB[frozenset((eo, eta))] = 0
    S.sym("paper", "M15", "", "", "M15: b = E[or]/E[o^2] = 1 + E[oc]/E[o^2] (r = o + c)",
          E(oA * (oA + cA), rvA, momB) / E(oA * oA, rvA, momB) - (1 + E(oA * cA, rvA, momB) / E(oA * oA, rvA, momB)))
    S.sym("paper", "M15", "", "", "M15: E[oc] = -Var(eta) when the errors are independent of everything", E(oA * cA, rvA, momB) + s_ee)
    if quick:
        return
    # Anam's kernel: the special cases and the extended range, on every NEPSE stock-day
    s40 = _load("s40_for_46", "40_anam_holdout.py")
    AN = s40.AN
    d = s40.nepse()
    o, cc, uu, dd = d["o"], d["c"], d["u"], d["d"]
    ok = o.notna() & cc.notna() & uu.notna() & dd.notna()
    o, cc, uu, dd = o[ok], cc[ok], uu[ok], dd[ok]
    r = o + cc
    h, l_ = o + uu, o + dd
    TR = np.maximum(h, 0) - np.minimum(l_, 0)
    zero_b = pd.Series(0.0, index=o.index)
    one_b = pd.Series(1.0, index=o.index)
    S.data("paper", "6.8", "", "", "open-free form: kernel(b = 0) = 0.8 TR^2/(4 ln 2) + 0.2 r^2",
           (AN.kernel(o, cc, uu, dd, zero_b) - (0.8 * TR ** 2 / (4 * LN2) + 0.2 * r ** 2)).to_numpy(), tol=1e-15)
    S.data("paper", "6.8", "", "", "full form at b = 1: kernel = o^2 + R^2/(4 ln 2) (overnight^2 + Parkinson)",
           (AN.kernel(o, cc, uu, dd, one_b) - (o ** 2 + (uu - dd) ** 2 / (4 * LN2))).to_numpy(), tol=1e-15)
    rngb = np.random.default_rng(SEED + 8)
    bb = pd.Series(rngb.uniform(0, 1, len(o)), index=o.index)
    Rs = AN.extended_range(o, uu, dd, bb)
    S.data("paper", "6.8", "", "", "R* = max(h, b o) - min(l, b o): the range of the bar extended to the effective open",
           (Rs - (np.maximum(h, bb * o) - np.minimum(l_, bb * o))).to_numpy(), tol=1e-15)
    S.add("paper", "6.8", "", "", "R <= R* <= TR for every b in [0, 1], with R*(0) = TR and R*(1) = R", "data",
          bool(((uu - dd) <= Rs + 1e-15).all() and (Rs <= TR + 1e-15).all()
               and np.allclose(AN.extended_range(o, uu, dd, zero_b), TR, atol=1e-15, rtol=0)
               and np.allclose(AN.extended_range(o, uu, dd, one_b), uu - dd, atol=1e-15, rtol=0)),
          f"{len(o):,} stock-days")
    gk = 0.5 * (uu - dd) ** 2 - (2 * LN2 - 1) * cc ** 2
    valid = (uu >= -1e-15) & (dd <= 1e-15) & (cc <= uu + 1e-15) & (cc >= dd - 1e-15)
    S.add("paper", "4.3", "", "", "GK >= (3/2 - 2 ln 2) c^2 >= 0 on every valid NEPSE bar", "data",
          bool((gk[valid] >= (1.5 - 2 * LN2) * cc[valid] ** 2 - 1e-15).all()), f"{int(valid.sum()):,} valid stock-days")
    # the YZ identity on the data, 21-session windows of one security each
    yz_ok, n_win = True, 0
    for _, g in d[d["o"].notna() & d["c"].notna()].groupby("symbol"):
        ov, cv = g["o"].to_numpy(), g["c"].to_numpy()
        rsv = (g["u"] * (g["u"] - g["c"]) + g["d"] * (g["d"] - g["c"])).to_numpy()
        for st in range(0, len(ov) - 21, 97):
            O_, C_, RS_ = ov[st:st + 21], cv[st:st + 21], rsv[st:st + 21]
            k21 = s45.yz_k(21)
            yz = np.var(O_, ddof=1) + k21 * np.var(C_, ddof=1) + (1 - k21) * RS_.mean()
            lhs = yz - np.var(O_ + C_, ddof=1)
            rhs = (1 - k21) * (RS_.mean() - np.var(C_, ddof=1)) - 2 * np.cov(O_, C_, ddof=1)[0, 1]
            yz_ok &= abs(lhs - rhs) <= 1e-12 * max(1e-6, abs(lhs))
            n_win += 1
    S.add("paper", "6.7", "", "", "the Yang-Zhang identity holds on NEPSE 21-session windows (to 1e-12 relative)", "data", bool(yz_ok),
          f"{n_win:,} windows")


# =============================================================================================

def write_outputs(S: Steps) -> pd.DataFrame:
    t = S.frame()
    t.to_csv(TAB / "table124_theory_proof_steps.csv", index=False, float_format=FLOAT_FMT)
    macros = {"proofs-n": len(t), "proofs-pass": int(t["pass"].sum()), "proofs-fail": int((~t["pass"]).sum())}
    groups = {"symbolic": ("symbolic", "symbolic-50dp"), "numerical": ("numerical",), "mc": ("Monte Carlo",),
              "path": ("pathwise",), "data": ("data",)}
    for k_, meths in groups.items():
        macros[f"proofs-{k_}"] = int(t["method"].isin(meths).sum())
    macros["proofs-sym50"] = int((t["method"] == "symbolic-50dp").sum())
    lines = ["% Generated by scripts/46_theory_proofs.py -- do not edit by hand."]
    for k_, v in macros.items():
        lines.append(r"\expandafter\def\csname thn@" + k_ + r"\endcsname{" + f"{v:,}".replace(",", "{,}") + "}")
    (GEN / "proofs.tex").write_text("\n".join(lines) + "\n")
    order = ["model", "1", "2", "3", "4", "5", "6", "7", "8", "paper"]
    label = {"model": "The model", "paper": "The paper's own claims"}
    rows = []
    for p in order:
        g = t[t["proposition"] == p]
        if g.empty:
            continue
        cnt = lambda ms: int(g["method"].isin(ms).sum())     # noqa: E731
        rows.append(f"{label.get(p, 'Proposition ' + p)} & {cnt(('symbolic', 'symbolic-50dp'))} & {cnt(('numerical',))} & "
                    f"{cnt(('Monte Carlo',))} & {cnt(('pathwise',))} & {cnt(('data',))} & {len(g)} & {int(g['pass'].sum())} \\\\")
    (GEN / "tab_proofs.tex").write_text("\n".join(rows) + "\n")
    return t


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true", help="smaller simulations and no data checks")
    a = ap.parse_args()
    t0 = time.time()
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    S = Steps()
    print("Step-by-step verification of the theory's proofs (symbolic, numerical, simulation, data)")
    prop1(S); print(f"  Proposition 1 ({time.time() - t0:.0f}s)")
    prop2(S, a.quick); print(f"  Proposition 2 ({time.time() - t0:.0f}s)")
    prop3(S, a.quick); print(f"  Proposition 3 ({time.time() - t0:.0f}s)")
    prop4(S); print(f"  Proposition 4 ({time.time() - t0:.0f}s)")
    prop5(S); print(f"  Proposition 5 ({time.time() - t0:.0f}s)")
    prop6(S, a.quick); print(f"  Proposition 6 ({time.time() - t0:.0f}s)")
    prop7(S, a.quick); print(f"  Proposition 7 ({time.time() - t0:.0f}s)")
    prop8(S, a.quick); print(f"  Proposition 8 ({time.time() - t0:.0f}s)")
    paper(S, a.quick); print(f"  the paper's claims ({time.time() - t0:.0f}s)")
    t = S.frame()
    nfail = int((~t["pass"]).sum())
    print(f"{len(t)} steps, {len(t) - nfail} pass, {nfail} fail; by method: {t['method'].value_counts().to_dict()}")
    if nfail:
        pd.set_option("display.width", 250)
        pd.set_option("display.max_colwidth", 120)
        print(t[~t["pass"]][["proposition", "part", "appendix", "step", "method", "detail"]].to_string(index=False))
    if not a.quick:
        GEN.mkdir(parents=True, exist_ok=True)
        write_outputs(S)
        print(f"wrote table124 and paper/theory/generated/proofs.tex ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
