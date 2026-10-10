"""Collect every development round into one ledger: for each round, sample, model and horizon, the mean over
folds of the validation-loss difference against that round's reference forecast, its mean t statistic, and the
number of folds in which the model had the lower loss. Output: output/dev_anam2/ledger.csv"""
import glob
import pathlib

import pandas as pd

OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"
#: the reference each round's differences are taken against (column name -> reference forecast)
REF = {"d_vs_base": "base column", "d": "OF (frozen)", "d_OF": "HAR-OF", "d_FOF": "FHAR-OF"}


def main():
    rows = []
    for f in sorted(glob.glob(str(OUT / "e*_*.csv"))):
        name = pathlib.Path(f).stem
        if name.startswith("e0_"):
            continue
        rnd = name.split("_")[0]
        x = pd.read_csv(f)
        for dcol, tcol in (("d_OF", "t_OF"), ("d_FOF", "t_FOF"), ("d_vs_base", "t_vs_base"), ("d", "t")):
            if dcol in x.columns:
                break
        ref = x["base"].iloc[0] if dcol == "d_vs_base" else REF[dcol]
        g = x.groupby(["sample", "model", "window"]).agg(d=(dcol, "mean"), t=(tcol, "mean"),
                                                          folds=(dcol, "size"), wins=(dcol, lambda s: int((s < 0).sum())))
        g = g.reset_index()
        g.insert(0, "round", rnd)
        g["reference"] = ref
        rows.append(g)
    led = pd.concat(rows, ignore_index=True)
    led["round_no"] = led["round"].str[1:].astype(int)
    led = led.sort_values(["round_no", "sample", "window", "d"]).drop(columns="round_no")
    led.to_csv(OUT / "ledger.csv", index=False, float_format="%.6g")
    print(f"{len(led)} rows, {led.groupby('round')['model'].nunique().sum()} round-model pairs -> {OUT / 'ledger.csv'}")


if __name__ == "__main__":
    main()
