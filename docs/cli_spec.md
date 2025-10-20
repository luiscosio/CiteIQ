# CiteIQ CLI Spec

The `citeiq` command-line interface wraps the full reference quality pipeline. It is intentionally simple and script-friendly.

## Command

```
citeiq process [OPTIONS] INPUT...
```

### Positional arguments

| Argument | Description |
| --- | --- |
| `INPUT` | One or more files containing raw references. Plain-text IEEE lists (`.txt`) and BibTeX (`.bib`) are supported. Files are processed in the order provided. |

### Options

| Flag | Description |
| --- | --- |
| `-o`, `--output-dir PATH` | Directory for generated outputs (CSV, XLSX, report, charts). Defaults to `./output`. |
| `--cache-dir PATH` | Override the HTTP cache directory. Defaults to `<output-dir>/cache`. |
| `-e`, `--email EMAIL` | Contact email used for Unpaywall lookups. Recommended to maximise API coverage. |
| `-s`, `--sort {author,year,order}` | Sorting mode for the final report. `author` (default) sorts by first author’s surname, `year` sorts by publication year (desc), `order` preserves input order. |
| `-k`, `--topic-clusters INTEGER` | Approximate number of topic clusters to compute (default: 8). |

## Outputs

| File | Purpose |
| --- | --- |
| `references.csv` | All normalized metadata, quality scores, and flags. |
| `references.xlsx` | Excel variant of the CSV. |
| `report.md` | Markdown report summarising key metrics, flags, and clusters. |
| `recency.png` | Publication year histogram. |
| `preprints.png` | Preprint vs peer-reviewed share. |
| `top_cited.png` | Top cited works bar chart. |

## Workflow

1. **Ingest**: parse IEEE-style text or BibTeX into normalized placeholders.
2. **Enrich**: call Crossref, OpenAlex, Unpaywall (with caching and polite rate limiting).
3. **Score**: compute the 0–100 rule-based quality score and attach flags (duplicates, retractions, preprints, mismatches).
4. **Cluster**: detect co-author and organisation communities, plus topic clusters via TF-IDF + KMeans.
5. **Report**: write tabular exports, charts, and a Markdown summary.

## Notes

- The tool caches all HTTP responses under the cache directory (sha256 key names). Delete the folder to force fresh lookups.
- Network requests gracefully degrade—if an API call fails, the pipeline continues with partial data and flags the citation as needed.
- To suggest “better” sources (published versions or newer editions), ensure the DOI resolves so the Crossref/OpenAlex relations can be followed.
