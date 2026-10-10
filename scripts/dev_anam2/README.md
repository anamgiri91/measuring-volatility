# Development scripts for Anam II (training spans only)

These are the exploratory scripts behind [`ANAM2_DEVELOPMENT.md`](../../ANAM2_DEVELOPMENT.md). They are kept as
run, so that every variant behind the design of plan M22 can be inspected and rerun. None of them reads a test
span of plan M20 or the Pakistan data: `harness.load_dev` keeps only training rows.

| File | What it does |
|---|---|
| `harness.py` | loads a sample through `scripts/47_corrected_evaluation.py`, keeps its training rows and builds the development folds (NEPSE: A1 → B and B → A1; the others: three expanding folds, or one 60/40 split with `DEV_FOLDS=single`) |
| `kernels2.py` | the candidate kernels: the leave-one-out market move, the two-component open, the effective-bar kernel |
| `models2.py` | convex forecasts fitted by QLIKE (SLSQP with the exact gradient), and the cross-sectional market state |
| `runner.py`, `runner2.py` | the fold loop of rounds E1–E6 |
| `e0_describe.py` … `e16_final.py` | the rounds of the record, one script each (E2 is the script of round E3) |
| `sim_m1.py` | the simulation of the market-implied open |
| `diag_vn.py` | the Vietnam diagnostic |
| `summarize.py` | collects every round into `output/dev_anam2/ledger.csv` |
| `launch.sh` | runs one script on several samples in the background, logging to `output/dev_anam2/` |

To rerun a round, run it from the repository root with the frontier inputs in place:

```bash
python scripts/dev_anam2/e16_final.py "Morocco 2012-2026"
```

Each script writes `output/dev_anam2/<round>_<sample>.csv`.

Two caveats:

* Outside NEPSE, rounds E1 to E5 used a single 60/40 split of the training dates; from E6 on, the three
  expanding folds.
* The scripts are research code. The frozen implementation of the chosen design is in `nepsevol.estimators.anam2`.
