# Raw NEPSE stock-level inputs

The original stock-level NEPSE source files used to build the processed panel are **not redistributed** in this journal submission package because their redistribution terms are unresolved.

For paper reproduction, use the frozen, audited CSV files in `data/processed/`. They are sufficient for every retained paper-facing analysis in `run_paper_analysis.sh`.

`scripts/02_build_panel.py` remains the complete cleaning/build specification. If the original source files are lawfully available, place them in:

- `data/raw/stock-daily-long/*.csv`
- `data/raw/stock-daily-trades/*.csv`

and run `python scripts/02_build_panel.py`.

The original project build manifest recorded 1,268 raw CSVs with aggregate SHA-256:

`7b2c5cc9815ee9600208ba91251a5147b541d4c044c4fbabd9396cb278f4afec`
