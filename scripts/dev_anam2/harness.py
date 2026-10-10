"""Development harness for a second-generation estimator: TRAINING SPANS ONLY.

load_dev(name) returns the sample restricted to rows whose date lies in the training span, with the
fit/validate split used for development:
  * NEPSE: regimes A1 and B (two folds, A1 -> B and B -> A1, as in the M16 development);
  * every other sample: the first 60% of training dates fit, the last 40% validate (purged).
"""
import importlib.util, sys, pathlib
import numpy as np, pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "anam-estimator" / "src"))
_spec = importlib.util.spec_from_file_location("s47", ROOT / "scripts" / "47_corrected_evaluation.py")
s47 = importlib.util.module_from_spec(_spec); sys.argv = sys.argv[:1]; _spec.loader.exec_module(s47)
EV, FB, AN, OF = s47.EV, s47.FB, s47.AN, s47.OF
SAMPLES = s47.SAMPLES
import os
FOLDS = os.environ.get("DEV_FOLDS", "expanding")

def load_dev(name):
    S = s47.load(name)
    d = S["d"]
    tr = S["train"].reindex(d.index).fillna(False).astype(bool)
    d = d[tr].copy()
    if name == "NEPSE":
        folds = [("A1", "B"), ("B", "A1")]
        masks = [(d["regime"] == a, d["regime"] == b) for a, b in folds]
    else:
        dates = np.sort(d["date"].unique())
        if FOLDS == "single":
            cut = dates[int(0.6 * len(dates))]
            masks = [(d["date"] < cut, d["date"] >= cut)]
        else:  # three expanding folds: fit before 40/60/80% of the training dates, validate the next fifth
            cuts = [dates[int(q * len(dates))] for q in (0.4, 0.6, 0.8)] + [dates[-1] + np.timedelta64(1, "D")]
            masks = [(d["date"] < cuts[k], (d["date"] >= cuts[k]) & (d["date"] < cuts[k + 1])) for k in range(3)]
    return dict(name=name, d=d, mode=S["mode"], masks=masks, liq=S["liq"])
