"""M22, Part C: freeze Anam II's weights on all current data, for the prospective test.

Plan M22 (``M22_ANAM2_PLAN.md``) fixes this procedure before the evaluation is run; the script is run after it. For
each sample and horizon it fits, on every origin whose outcome is observed and where every forecast below is
defined:

* Anam II's weights (``nepsevol.estimators.anam2``);
* FHARL on the open-free kernel (the same dynamics, Anam I's kernel);
* M20's HAR-open-free, by M20's rule (its grid of convex weights).

When new sessions arrive they are scored with these weights under the protocol of plan M21, never refitted.

Output (output/tables/): table142_m22_frozen_weights.csv. The frozen table is never overwritten. A rerun on the
same inputs must reproduce it; a rerun on changed inputs is written to table142_m22_frozen_weights_rerun.csv.
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import importlib.util
import sys

import numpy as np
import pandas as pd

TAB = ROOT / "output" / "tables"
FLOAT_FMT = "%.10g"

_spec = importlib.util.spec_from_file_location("s52", ROOT / "scripts" / "52_m22_evaluation.py")
s52 = importlib.util.module_from_spec(_spec)
_argv, sys.argv = sys.argv, sys.argv[:1]
_spec.loader.exec_module(s52)
sys.argv = _argv
s47, EV, FB, F = s52.s47, s52.EV, s52.FB, s52.F

_spec50 = importlib.util.spec_from_file_location("s50", ROOT / "scripts" / "50_m21_freeze.py")
s50 = importlib.util.module_from_spec(_spec50)
_argv, sys.argv = sys.argv, sys.argv[:1]
_spec50.loader.exec_module(s50)
sys.argv = _argv


def digest(name: str) -> str:
    if name == "Pakistan 2016-2026":
        return f"PSX combined {F.PSX_SHA256[:16]}..., metadata {F.PSX_META_SHA256[:16]}..."
    return s50.digest(name)


def main() -> None:
    print("M22 Part C: weights frozen on all current data")
    rows = []
    for name in s52.SAMPLES:
        if name not in ("NEPSE", "NIFTY50", "SP500") and not s47.INPUTS.exists():
            print(f"  {name}: skipped (data/external/frontier/ not present)")
            continue
        if name == "Pakistan 2016-2026" and not (s47.INPUTS / "psx").exists():
            print(f"  {name}: skipped (data/external/frontier/psx/ not present)")
            continue
        S = s47.load(name)
        S["name"] = name
        d = S["d"]
        M22 = s52.m22_models(S)
        keep = {k: M22[k] for k in (s52.ANAM2, "FHARL open-free") if k in M22}
        for win in s47.WINDOWS:
            M, _, _ = s47.build_models(S, win)
            tgt = EV.forward_target(FB.clean_square(d["CC"]), d["symbol"], d["ses"], win)
            ok = tgt["y"].notna()
            for m in list(M.values()) + list(keep.values()):
                ok &= m.defined.reindex(d.index).fillna(False).astype(bool)
            common = dict(n_origins=int(ok.sum()), last_session=str(d.loc[ok, "date"].max().date()),
                          last_bar=str(d["date"].max().date()), inputs=digest(name))
            for nm, m in keep.items():
                c, L = m.fit(tgt["y"], ok)
                rows.append(dict(sample=name, window=win, model=nm, components=",".join(m.Z.columns),
                                 parameters=str(np.round(c, 10).tolist()), train_loss=L, **common))
            p, L, _ = s47.select(M[s52.REF], tgt["y"], ok)
            rows.append(dict(sample=name, window=win, model=s52.REF, components="d1,m5,m22,lr", parameters=str(p),
                             train_loss=L, **common))
            print(f"  {name} h={win}: {int(ok.sum()):,} origins through {common['last_session']}", flush=True)
    out = pd.DataFrame(rows)
    frozen = TAB / "table142_m22_frozen_weights.csv"
    if not frozen.exists():
        out.to_csv(frozen, index=False, float_format=FLOAT_FMT)
        print(f"  wrote {frozen.name}")
    else:
        old = pd.read_csv(frozen)
        keys = ["sample", "window", "model", "parameters", "n_origins", "last_session"]
        same = (len(old) == len(out) and (old[keys].astype(str).values == out[keys].astype(str).values).all()
                and np.allclose(old["train_loss"].to_numpy(float), out["train_loss"].to_numpy(float), rtol=1e-8, atol=0))
        if same:
            print(f"  reproduces the frozen {frozen.name}")
        else:
            rerun = TAB / "table142_m22_frozen_weights_rerun.csv"
            out.to_csv(rerun, index=False, float_format=FLOAT_FMT)
            print(f"  MISMATCH: this run is in {rerun.name}; {frozen.name} is unchanged")
    print(out[["sample", "window", "model", "parameters"]].to_string(index=False))


if __name__ == "__main__":
    main()
