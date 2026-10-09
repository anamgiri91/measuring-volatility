"""M21: freeze every forecast's parameters on all current data, for the prospective test.

Plan M21 (``M21_PROSPECTIVE_PLAN.md``) evaluates the seventeen forecasts of plan M20 on sessions that are not
in this repository yet: NEPSE after 2026-08-26, Dhaka after 2026-10-08, Casablanca after 2026-03-27 and, if a
documented source is found, Vietnam after 2020-03-18. Its parameters are fixed here, on every current origin
whose outcome is observed, by the selection rule of M20. When the new sessions arrive they are scored with
these values, never refitted.

The table records, for each sample, horizon and forecast: the parameters, the training loss, the number of
origins, the last session used, and a digest of the inputs, so the prospective run can check that it starts
from the same data.

Output (output/tables/): table136_m21_frozen_parameters.csv

The frozen table is never overwritten. A rerun on the same pinned inputs must reproduce it, and the script says
whether it does; if the inputs have changed (new sessions appended, say), the rerun is written to
table136_m21_frozen_parameters_rerun.csv instead, and the plan's digest still identifies the frozen file.
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import hashlib
import importlib.util
import sys

import numpy as np
import pandas as pd

TAB = ROOT / "output" / "tables"
FLOAT_FMT = "%.10g"

_spec = importlib.util.spec_from_file_location("s47", ROOT / "scripts" / "47_corrected_evaluation.py")
s47 = importlib.util.module_from_spec(_spec)
sys.argv = sys.argv[:1]
_spec.loader.exec_module(s47)
EV, FB, F = s47.EV, s47.FB, s47.F


def digest(name: str) -> str:
    if name == "NEPSE":
        p = ROOT / "data" / "processed" / "equity_sample.csv"
        return "sha256 " + hashlib.sha256(p.read_bytes()).hexdigest()
    if name == "NIFTY50":
        p = ROOT / "data" / "external" / "nifty50.csv"
        return "sha256 " + hashlib.sha256(p.read_bytes()).hexdigest()
    if name == "SP500":
        import arch
        return f"arch.data.sp500, arch {arch.__version__}"
    return {"DSE 2023-2026": f"DSE upload {F.DSE_UPLOAD_SHA256[:16]}..., mirror {F.DSE_MIRROR_SHA256[:16]}...",
            "DSE 2009-2021": f"DSE upload {F.DSE_UPLOAD_SHA256[:16]}...",
            "Vietnam 2007-2020": f"Vietnam manifest {F.VN_MANIFEST_SHA256[:16]}...",
            "Morocco 2012-2026": f"Casablanca manifest {F.CSE_MANIFEST_SHA256[:16]}..."}[name]


def main() -> None:
    print("M21: parameters frozen on all current data")
    rows = []
    for name in s47.SAMPLES:
        if name not in ("NEPSE", "NIFTY50", "SP500") and not s47.INPUTS.exists():
            print(f"  {name}: skipped (data/external/frontier/ not present)")
            continue
        S = s47.load(name)
        d = S["d"]
        for win in s47.WINDOWS:
            M, K, b = s47.build_models(S, win)
            tgt = EV.forward_target(FB.clean_square(d["CC"]), d["symbol"], d["ses"], win)
            ok = tgt["y"].notna()
            for m in M.values():
                ok &= m.defined.reindex(d.index).fillna(False).astype(bool)
            params = {}
            common = dict(n_origins=int(ok.sum()), last_session=str(d.loc[ok, "date"].max().date()),
                          last_bar=str(d["date"].max().date()), inputs=digest(name))
            for mname, m in M.items():
                p, L, rej = s47.select(m, tgt["y"], ok)
                params[mname] = p
                rows.append(dict(sample=name, window=win, model=mname, parameters=str(p), train_loss=L,
                                 rejected_candidates=int(rej), **common))
            # the fixed combination has no parameter of its own: it averages the two frozen forecasts
            f = 0.5 * M["CC"].forecast(params["CC"]) + 0.5 * M[s47.OF].forecast(params[s47.OF])
            rows.append(dict(sample=name, window=win, model=s47.COMBO,
                             parameters=f"0.5 CC({params['CC']}) + 0.5 open-free({params[s47.OF]})",
                             train_loss=float(np.mean(EV.qlike_canonical(tgt["y"][ok], f[ok]))),
                             rejected_candidates=0, **common))
            print(f"  {name} h={win}: {int(ok.sum()):,} origins through {d.loc[ok, 'date'].max().date()}")
    out = pd.DataFrame(rows)
    frozen = TAB / "table136_m21_frozen_parameters.csv"
    if not frozen.exists():
        out.to_csv(frozen, index=False, float_format=FLOAT_FMT)
        print(f"  wrote {frozen.name}")
    else:
        old = pd.read_csv(frozen)
        same = (len(old) == len(out)
                and (old[["sample", "window", "model", "parameters", "n_origins", "last_session"]].astype(str).values
                     == out[["sample", "window", "model", "parameters", "n_origins", "last_session"]].astype(str).values).all()
                and np.allclose(old["train_loss"].to_numpy(float), out["train_loss"].to_numpy(float), rtol=1e-8, atol=0))
        if same:
            print(f"  reproduces the frozen {frozen.name} (parameters, origins and training losses)")
        else:
            rerun = TAB / "table136_m21_frozen_parameters_rerun.csv"
            out.to_csv(rerun, index=False, float_format=FLOAT_FMT)
            print(f"  MISMATCH: the inputs no longer give the frozen parameters; this run is in {rerun.name}, and "
                  f"{frozen.name}, whose digest plan M21 records, is unchanged")
    print(out.pivot_table(index="model", columns=["sample", "window"], values="parameters", aggfunc="first")
          .to_string()[:4000])


if __name__ == "__main__":
    main()
