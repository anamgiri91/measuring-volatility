# External market series used in the submitted paper

- `nifty50.csv` - NIFTY 50 OHLC series used for the cross-market implementation check.
- `india_vix.csv` - India VIX series used as the options-market **co-movement check** (Section 6.3). It is not a validation of estimator accuracy; see the manuscript's Section 6.3 and Section 10.
- `nepse_index_history.csv` - NEPSE index OHLC series used for the aggregate-market comparison.

- `nepse_security_master.csv` - instrument category and par value for 652 currently listed NEPSE
  securities, mapped onto the four classes the paper uses plus `preference`. Added in this
  revision to answer referee item 2: it is the authoritative target against which
  `scripts/27_classification_audit.py` validates the rule-based classifier. Columns: `symbol`,
  `company_name`, `sharesansar_sector` (the source category, retained verbatim so the mapping is
  auditable), `sec_type_master`, `par_value`, `listing_date`, `listed_shares`. Retrieved
  2026-09-02. It lists CURRENTLY listed securities, so ten securities that were delisted, merged
  or renamed during 2024-2026 do not appear and fall back to the rule; they are listed in
  `output/tables/table37_classification_disagreements.csv`.

The NIFTY 50 and India VIX files were preserved from the audited research archive and were originally acquired through the project's external-data workflow. The NEPSE index series is also preserved from that archive. These files are included so the paper-facing results can be reproduced exactly; their inclusion should not be interpreted as a grant of redistribution rights beyond the submission/review context.

## Provenance (mandatory item 7 / peer-review item F)

The original acquisition of `nifty50.csv`, `india_vix.csv` and `nepse_index_history.csv` predates
this package and was not logged with a per-file retrieval timestamp or exact request URL, so this
section states two separate things rather than conflating them: (1) the **provider** each series
comes from and its adjustment/units convention, which is verifiable from the file contents
themselves, and (2) the **current** public access point at that provider, checked 2026-09-03 —
offered as where a reader could re-acquire an equivalent series today, not as a claim about the
exact page the original download came from.

| File | Provider | Series | Units / adjustment | Current public access point (checked 2026-09-03) | License / terms |
|---|---|---|---|---|---|
| `nifty50.csv` | National Stock Exchange of India (NSE) | NIFTY 50 index, daily OHLC | Index points; NSE publishes the index unadjusted for dividends (price return, not total return) | NSE India, Reports → Historical Data → Indices: <https://www.nseindia.com/reports-indices-historical-vix> and the indices historical-data section under <https://www.nseindia.com/> (NSE has reorganised this URL more than once; if it has moved again, search NSE India's site for "historical index data") | NSE's data-terms page governs redistribution; NOT independently re-verified for this package, hence "not publicly redistributed" in `BUILD-MANIFEST.json` |
| `india_vix.csv` | National Stock Exchange of India (NSE) | India VIX, daily | Index points; forward-looking, option-implied annualised volatility (not directly comparable in level to a realized-volatility estimator) | NSE India, Historical VIX: <https://www.nseindia.com/reports-indices-historical-vix> | Same as above |
| `nepse_index_history.csv` | Nepal Stock Exchange (NEPSE) | NEPSE index, daily OHLC | Index points; price index (not total return); reflects the exchange's own session and price-limit rules described in the manuscript's Section 3 | NEPSE official site, Indices: <https://www.nepalstock.com/indices> (also mirrored at <https://nepalstock.com.np/>) | NEPSE's own terms govern redistribution; NOT independently re-verified for this package |
| `nepse_security_master.csv` | ShareSansar (a private Nepali market-data portal, **not** NEPSE or SEBON) | Instrument category (`sharesansar_sector`) and par value for currently listed securities | As published by ShareSansar; retained verbatim in `sharesansar_sector` so the mapping to this paper's four classes is auditable | <https://www.sharesansar.com/> (company/listing pages); retrieved 2026-09-02 | Independent third-party source. It is described in the manuscript (§3, Table 9, §10) as "an external listing... rather than an official SEBON register" precisely because it is not one; do not describe it as an official NEPSE/SEBON register in derivative text |

None of these four files is redistributed as a claim of official provenance beyond what is stated
above. Where the manuscript needs a stronger provenance guarantee than "provider identified,
current access point verified" — for example an exact retrieval timestamp and request log — that
guarantee does not currently exist for the pre-2026-09 acquisitions and is disclosed as such
rather than reconstructed after the fact.

## Series used by M16 and not stored here

`scripts/40_anam_holdout.py` reads the S&P 500 daily OHLC series (1999-01-04 to 2018-12-31) and the CBOE VIX (2014-01-03 to 2019-01-03) from the datasets bundled with the `arch` Python package, version 8.0.0 (`arch.data.sp500`, `arch.data.vix`; the package documents them as originally from Yahoo Finance). They are loaded at run time, not copied into this directory, and are pinned through `requirements.txt`. The usual market-data hosts were not reachable from the environment in which M16 was run.

## Frontier-market inputs used by M17 and not stored here

`scripts/42_anam_frontier.py` reads three third-party inputs from `data/external/frontier/`, a directory that is
gitignored and excluded from `SUBMISSION_MANIFEST.json`. Each is pinned by SHA-256 in `src/nepsevol/frontier.py`
and checked before use; a different file stops the script. Redistribution terms of the underlying exchange data
were not verified, which is why none of them is copied into the package.

| Path under `data/external/frontier/` | What it is | How to obtain it | SHA-256 |
|---|---|---|---|
| `dse_upload/DSE_Data.csv` | Dhaka Stock Exchange daily OHLC and volume, 534 trading codes, stamped 1999-01-02 to 2025-04-08 (columns `Trading_Code, Date, Open, High, Low, Close, Volume`), supplied by the author as `Archive.zip` (SHA-256 `1d6c4cd5412fb33e83e9d6ada4213c3070c327a1881d323ac3333c352d97d04d`) with `Instruments.txt` | Its name, span and columns match "Dhaka Stock Exchange Historical Data (1999-2025)", Sunny, Nafis and Khan, Mendeley Data (2025), <https://data.mendeley.com/datasets/5mww8rb9td>; its row count (1,523,921) does not match that listing's (1,684,249), so check the hash rather than assume the release is the same file. **Its dates before 2023 have day and month exchanged whenever the day is 12 or less**; `nepsevol.frontier` repairs 2009-2021, drops 2022 and documents the evidence | `a619a0ff80ce944414f94f6b1cd88e8ee186e83241a0934c2330036c190c6763` |
| `dse_mirror/prices.csv` | Dhaka Stock Exchange day-end archive, 2024-09-30 to 2026-10-08, with the exchange's previous close and trade count; identical to the upload on the 52,920 stock-days they share | `git clone https://github.com/nifty1303/dse-data` and check out commit `9f11a766ae8690bdb798f68b077a1ce5449807e0`; copy `data/prices.csv` (and `data/fundamentals.csv`, whose sector field defined the non-equity list) | `552e1a4515e36348a35069fca13067149988e9242e03b0bcac5b1a289b1b9633` |
| `vietnam/tickers/*.csv` | One file per Vietnamese security (HOSE, HNX, UPCoM, unlabelled), 2000-07-28 to 2020-03-18, prices adjusted for corporate actions and rounded to 0.01 thousand dong; the 936 three-character codes are used | `git clone https://github.com/88d52bdba0366127fffca9dfa93895/vnstock-data` and check out commit `b52e2fe0905417e0d1c7215fbda1d352dde47492`; copy `tickers/*.csv` (the repository's `stocks.csv`, `README.md` and `LICENSE` are Git LFS pointers whose content could not be fetched, so the original source and licence of these files are unknown) | manifest `69caa964702c5152574eba580dc7e406213fbdf41b6824e53584d50c9c7e2691` (SHA-256 of the sorted `"<file> <sha256>"` lines of the 936 files) |

The frontier panels are built by `nepsevol.frontier.market_panel`; its docstring states the cleaning rules, which
were frozen in `M17_ANAM_FRONTIER_PLAN.md` before any estimator was computed on these data.

### Added for M18: Casablanca Stock Exchange

| Path under `data/external/frontier/` | What it is | How to obtain it | SHA-256 |
|---|---|---|---|
| `casablanca/stock/*.csv` (and `casablanca/info.csv`) | One file per Casablanca Stock Exchange share, 77 shares, 2012-03-26 to 2026-03-27, columns `Time, Open, High, Low, Close, Volume`, not adjusted for corporate actions | Supplied by the author as `archive_2.zip` (SHA-256 `c9cc8888fec542a2aafc6d2a2458c88508ea7761f18b422c8f1aa4e02e0ef1be`), folder `cse-data/`; the original source is not stated. The `index/` folder is not used | manifest `41a7ecdef86b23491dbf1571dfcc718a4cc59a649dbfab4e29a72fb75ebd5e0e` (sorted `"<file> <sha256>"` lines of the 77 share files) |
