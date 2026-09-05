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
