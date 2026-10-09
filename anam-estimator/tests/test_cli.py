import pandas as pd

from anam_estimator.cli import main


def test_command_line_prints_each_security_and_writes_the_path(tmp_path, capsys, panel):
    src = tmp_path / "prices.csv"
    out = tmp_path / "estimates.csv"
    panel.drop(columns="true_variance").to_csv(src, index=False)
    assert main([str(src), "--form", "open-free", "--annualize", "observed", "--output", str(out)]) == 0
    text = capsys.readouterr().out
    assert "open-free form, panel mode" in text and "S001" in text and "S012" in text
    path = pd.read_csv(out)
    assert {"symbol", "date", "b", "kappa", "variance", "volatility", "cc_variance"} <= set(path.columns)
