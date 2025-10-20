# CiteIQ

CiteIQ is a lightweight CLI that ingests IEEE-style reference lists or BibTeX files, normalizes them into structured metadata, validates identifiers, enriches with open scholarly APIs, computes quality scores, and builds concise analytical reports.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
citeiq process references.txt --output-dir reports/
```

See `citeiq/cli.py` for detailed CLI documentation and flags.

## Features at a glance

- Parse IEEE-style reference lists or BibTeX files.
- Resolve DOIs and enrich metadata via Crossref, OpenAlex, and Unpaywall (with on-disk caching).
- Flag duplicates, mismatches, retractions, preprints, and outdated items.
- Compute a transparent 0–100 quality score for every citation.
- Cluster references by author, organisation, and topic.
- Export CSV/XLSX tables, charts, and a Markdown report.

Additional usage notes and option reference live in `docs/cli_spec.md`.
