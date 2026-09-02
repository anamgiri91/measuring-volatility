# `data/raw/` — currently empty, deliberately

Raw input data is held in the project's private data vault, not here, because its redistribution
terms are unresolved. The file in question is the NEPSE daily index series (2010-01-03 →
2026-06-12, 3,759 rows), which was self-scraped from a source not yet documented.

Until provenance and licence are established, the conservative state is to keep it out of the
public package. Public is the harder state to undo.

## What happens next

- **If redistribution is permitted** — the file is promoted here, and `config/config.yaml` points
  at this directory.
- **If it is not** — this package ships `src/nepsevol/ingest/` (the scraper) plus
  `scripts/00_fetch_data.py`, and a user reproduces by fetching from source.

Either way the scraper is being rebuilt, because reproducing from an opaque CSV is not a
reproduction. Anyone running this pipeline should be able to obtain the inputs themselves.

## Contract for anything placed here

- Treated as **read-only**. Never edited in place. Cleaning writes to `data/interim/`.
- Every file has a provenance entry: source, retrieval date, method, licence, known limitations.
- Every file is checksummed, and the checksum is verified before use.
