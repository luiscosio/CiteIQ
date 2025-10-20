# CiteIQ

CiteIQ is a lightweight CLI that ingests IEEE-style reference lists or BibTeX files, normalizes them into structured metadata, validates identifiers, enriches with open scholarly APIs, computes quality scores, and builds concise analytical reports.

## Installation

```bash
# Install with pip (in editable mode for development)
pip install -e .

# Or install with dev dependencies for testing
pip install -e ".[dev]"
```

## Quickstart

### Single file
```bash
citeiq process references.txt --output-dir reports/
```

### Multiple files (NO need to combine them!)
```bash
# Process all your reference files at once - they'll be combined automatically
citeiq process doc1_refs.txt doc2_refs.txt doc3_refs.bib doc4_refs.txt doc5_refs.bib --output-dir reports/
```

### With email for better API coverage (recommended)
```bash
citeiq process references.txt --email your.email@example.com --output-dir reports/
```

### Using wildcards (if your shell supports it)
```bash
citeiq process refs/*.txt --output-dir reports/
```

### Basic example
```bash
# For 5 separate reference files, just list them all:
citeiq process paper1.txt paper2.txt paper3.txt paper4.txt paper5.txt -o output/ -e me@email.com
```

**Output**: The tool generates `references.csv`, `references.xlsx`, `report.md`, and charts in your output directory.

### What to Expect (Verbose Output)

CiteIQ provides detailed progress information so you always know what's happening:

```
============================================================
CiteIQ Reference Quality Analysis
============================================================

📚 Phase 1: Ingesting references...
  Reading 5 input file(s)...
    • paper1.txt: 12 reference(s)
    • paper2.txt: 8 reference(s)
    • paper3.txt: 15 reference(s)
    • paper4.txt: 10 reference(s)
    • paper5.txt: 7 reference(s)
✓ Found 52 total references
  - 35 with DOI (67.3%)
  - 50 with year (96.2%)

🔍 Phase 2: Enriching metadata (fetching from APIs)...
  This may take a while for 52 references...
  Processing 1/52...
  Processing 10/52...
  Processing 20/52...
  ...
✓ Enrichment complete

🔎 Phase 3: Analyzing quality and detecting issues...
✓ Quality analysis complete:
  - 0 retracted
  - 2 possible duplicates ⚠️
  - 5 preprints
  - 3 unresolved DOIs
  - 1 metadata mismatches

📊 Phase 4: Generating reports and visualizations...
  ✓ Exported CSV and XLSX to output/
  Clustering authors, organizations, and topics...
  ✓ Found 8 author clusters, 5 org clusters, 8 topic clusters
  Generating charts...
  ✓ Generated 3 charts
  ✓ Markdown report: output/report.md

============================================================
✅ Analysis complete!
  📁 Output directory: output/
  📄 52 references processed
  📈 Average quality score: 68.3/100
============================================================
```

The tool tells you:
- **How many references** found in each file
- **How many have DOIs** and years (before enrichment)
- **Progress updates** during the slow API enrichment phase
- **Quality issues** found (duplicates, retractions, etc.)
- **Final statistics** including average quality score

## Supported Input Formats

### Plain text (`.txt`)
IEEE-style numbered references or paragraph-separated citations:
```
[1] J. Smith et al., "Example Paper," IEEE Conference, 2023, doi:10.1109/example.2023
[2] A. Jones, "Another Study," Nature, vol. 123, pp. 45-67, 2022
```

### BibTeX (`.bib`)
Standard BibTeX format:
```bibtex
@article{smith2023,
  title={Example Paper},
  author={Smith, John and Doe, Jane},
  journal={IEEE Conference},
  year={2023},
  doi={10.1109/example.2023}
}
```

**You can mix both formats** - the tool handles `.txt` and `.bib` files together!

## Common Options

| Option | Description | Example |
|--------|-------------|---------|
| `-o`, `--output-dir` | Where to save results (default: `./output`) | `-o reports/` |
| `-e`, `--email` | Your email for Unpaywall API (recommended!) | `-e you@email.com` |
| `-s`, `--sort` | Sort by: `author`, `year`, or `order` (default: `author`) | `-s year` |
| `-k`, `--topic-clusters` | Number of topic clusters (default: 8) | `-k 5` |
| `--cache-dir` | Custom cache location (default: `output/cache`) | `--cache-dir .cache/` |

Run `citeiq process --help` for full options.

## Features at a glance

- Parse IEEE-style reference lists or BibTeX files.
- Resolve DOIs and enrich metadata via Crossref, OpenAlex, and Unpaywall (with on-disk caching).
- Flag duplicates, mismatches, retractions, preprints, and outdated items.
- Compute a transparent 0–100 quality score for every citation.
- Cluster references by author, organisation, and topic.
- Export CSV/XLSX tables, charts, and a Markdown report.

## Additional Documentation

- Full CLI specification: `docs/cli_spec.md`
- Run tests: `pytest tests/`
