"""Reference processing pipeline that orchestrates ingestion, enrichment, scoring, and reporting."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
from rapidfuzz import fuzz

LOGGER = logging.getLogger(__name__)

from .clustering import ClusterSummary, build_author_clusters, build_org_clusters, build_topic_clusters
from .external import ExternalMetadataService
from .ingest import extract_initial_metadata, read_bibtex, read_plaintext_references
from .models import CitationFlag, CitationRecord, NormalizedReference, RawReference
from .normalize import merge_crossref, merge_openalex, merge_unpaywall
from .report import export_tabular_data, plot_preprint_share, plot_recency_histogram, plot_top_cited, records_to_dataframe, render_markdown_report
from .scoring import ScoreInputs, build_citation_record


@dataclass
class PipelineConfig:
    input_files: Sequence[Path]
    output_dir: Path
    cache_dir: Optional[Path] = None
    email: Optional[str] = None
    sort_mode: str = "author"  # author | year | order
    topic_clusters: int = 8
    per_request_pause: float = 0.2


@dataclass
class PipelineResult:
    records: List[CitationRecord]
    dataframe: pd.DataFrame
    author_clusters: List[ClusterSummary]
    org_clusters: List[ClusterSummary]
    topic_clusters: List[ClusterSummary]
    duplicate_pairs: List[Tuple[int, int]]
    charts: List[Path]
    markdown_report_path: Path


class ReferencePipeline:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        cache_dir = config.cache_dir or (config.output_dir / "cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.external = ExternalMetadataService(cache_dir=cache_dir, email=config.email, per_request_pause=config.per_request_pause)

    def run(self) -> PipelineResult:
        LOGGER.info("=" * 60)
        LOGGER.info("CiteIQ Reference Quality Analysis")
        LOGGER.info("=" * 60)
        LOGGER.info("")
        
        LOGGER.info("📚 Phase 1: Ingesting references...")
        references, original_years, order_indices = self._ingest_all()
        
        # Analyze ingested references
        with_doi = sum(1 for ref in references if ref.doi)
        with_year = sum(1 for ref in references if ref.year)
        
        LOGGER.info(f"✓ Found {len(references)} total references")
        LOGGER.info(f"  - {with_doi} with DOI ({with_doi/len(references)*100:.1f}%)" if references else "  - 0 with DOI")
        LOGGER.info(f"  - {with_year} with year ({with_year/len(references)*100:.1f}%)" if references else "  - 0 with year")
        LOGGER.info("")
        
        if not references:
            LOGGER.warning("⚠ No references found in input files!")
            return self._empty_result()
        
        LOGGER.info(f"🔍 Phase 2: Enriching metadata (fetching from APIs)...")
        LOGGER.info(f"  This may take a while for {len(references)} references...")
        
        records: List[CitationRecord] = []
        for idx, reference in enumerate(references, 1):
            if idx % 10 == 0 or idx == 1 or idx == len(references):
                LOGGER.info(f"  Processing {idx}/{len(references)}...")
            
            parsed_year = original_years[idx - 1]
            reference, doi_resolved, has_published_version = self._enrich_reference(reference)

            inputs = ScoreInputs(
                raw_reference=reference.raw,
                title_for_similarity=reference.title,
                metadata_title=reference.title,
                metadata_year=reference.year,
                parsed_year=parsed_year,
                authors=[author.name for author in reference.authors if author.name],
                doi_resolved=doi_resolved,
                has_published_version=has_published_version,
                has_newer_version=bool(reference.updates),
                is_preprint=bool(reference.is_preprint),
                is_peer_reviewed=reference.type in {"journal-article", "proceedings-article", "book-chapter"},
                is_retracted=bool(reference.is_retracted),
                is_open_access=reference.is_open_access,
                indexed_in=reference.indexed_in,
                citation_count=reference.citation_count,
            )
            record = build_citation_record(reference, inputs)
            records.append(record)
        
        LOGGER.info("✓ Enrichment complete")
        LOGGER.info("")

        LOGGER.info("🔎 Phase 3: Analyzing quality and detecting issues...")
        duplicate_pairs = self._flag_duplicates(records)
        
        # Count flags
        retractions = sum(1 for r in records if CitationFlag.RETRACTED in r.flags)
        duplicates = sum(1 for r in records if CitationFlag.POSSIBLE_DUPLICATE in r.flags)
        preprints = sum(1 for r in records if CitationFlag.PREPRINT in r.flags or r.reference.is_preprint)
        unresolved_dois = sum(1 for r in records if CitationFlag.DOI_UNRESOLVED in r.flags)
        mismatches = sum(1 for r in records if CitationFlag.METADATA_MISMATCH in r.flags)
        
        LOGGER.info(f"✓ Quality analysis complete:")
        LOGGER.info(f"  - {retractions} retracted" + (" ⚠️" if retractions > 0 else ""))
        LOGGER.info(f"  - {duplicates} possible duplicates" + (" ⚠️" if duplicates > 0 else ""))
        LOGGER.info(f"  - {preprints} preprints")
        LOGGER.info(f"  - {unresolved_dois} unresolved DOIs")
        LOGGER.info(f"  - {mismatches} metadata mismatches")
        LOGGER.info("")
        
        records = self._sort_records(records, order_indices)

        LOGGER.info("📊 Phase 4: Generating reports and visualizations...")
        df = records_to_dataframe(records)
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        export_tabular_data(df, self.config.output_dir)
        LOGGER.info(f"  ✓ Exported CSV and XLSX to {self.config.output_dir}")

        LOGGER.info("  Clustering authors, organizations, and topics...")
        author_clusters = build_author_clusters([record.reference for record in records])
        org_clusters = build_org_clusters([record.reference for record in records])
        topic_clusters = build_topic_clusters([record.reference for record in records], desired_k=self.config.topic_clusters)
        LOGGER.info(f"  ✓ Found {len(author_clusters)} author clusters, {len(org_clusters)} org clusters, {len(topic_clusters)} topic clusters")

        LOGGER.info("  Generating charts...")
        charts = [
            plot_recency_histogram(df, self.config.output_dir),
            plot_preprint_share(records, self.config.output_dir),
            plot_top_cited(df, self.config.output_dir),
        ]
        LOGGER.info(f"  ✓ Generated {len(charts)} charts")

        markdown = render_markdown_report(df, records, author_clusters, org_clusters, topic_clusters, charts)
        markdown_path = self.config.output_dir / "report.md"
        markdown_path.write_text(markdown, encoding="utf-8")
        LOGGER.info(f"  ✓ Markdown report: {markdown_path}")
        LOGGER.info("")
        
        # Final summary
        avg_score = df["score_total"].mean() if not df.empty else 0
        LOGGER.info("=" * 60)
        LOGGER.info("✅ Analysis complete!")
        LOGGER.info(f"  📁 Output directory: {self.config.output_dir}")
        LOGGER.info(f"  📄 {len(records)} references processed")
        LOGGER.info(f"  📈 Average quality score: {avg_score:.1f}/100")
        if retractions > 0:
            LOGGER.info(f"  ⚠️  {retractions} RETRACTED references found - review immediately!")
        LOGGER.info("=" * 60)

        return PipelineResult(
            records=records,
            dataframe=df,
            author_clusters=author_clusters,
            org_clusters=org_clusters,
            topic_clusters=topic_clusters,
            duplicate_pairs=duplicate_pairs,
            charts=charts,
            markdown_report_path=markdown_path,
        )

    def _empty_result(self) -> PipelineResult:
        """Return an empty result when no references are found."""
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        empty_df = pd.DataFrame()
        markdown_path = self.config.output_dir / "report.md"
        markdown_path.write_text("# CiteIQ Report\n\nNo references found in input files.", encoding="utf-8")
        return PipelineResult(
            records=[],
            dataframe=empty_df,
            author_clusters=[],
            org_clusters=[],
            topic_clusters=[],
            duplicate_pairs=[],
            charts=[],
            markdown_report_path=markdown_path,
        )

    def _ingest_all(self) -> Tuple[List[NormalizedReference], List[Optional[int]], List[int]]:
        references: List[NormalizedReference] = []
        original_years: List[Optional[int]] = []
        order_indices: List[int] = []
        position = 0

        LOGGER.info(f"  Reading {len(self.config.input_files)} input file(s)...")
        for path in self.config.input_files:
            count_before = len(references)
            if path.suffix.lower() == ".bib":
                normalized = read_bibtex(path, source_label=path.name)
                for item in normalized:
                    references.append(item)
                    original_years.append(item.year)
                    order_indices.append(position)
                    position += 1
            else:
                raw_refs: List[RawReference] = read_plaintext_references(path, source_label=path.name)
                normalized = extract_initial_metadata(raw_refs)
                for item in normalized:
                    references.append(item)
                    original_years.append(item.year)
                    order_indices.append(position)
                    position += 1
            count_added = len(references) - count_before
            LOGGER.info(f"    • {path.name}: {count_added} reference(s)")
        return references, original_years, order_indices

    def _enrich_reference(self, reference: NormalizedReference) -> Tuple[NormalizedReference, bool, bool]:
        doi_resolved = False
        has_published_version = False

        crossref_payload = None
        if reference.doi:
            crossref_payload = self.external.crossref_get_work(reference.doi)
            doi_resolved = crossref_payload is not None
        if not crossref_payload:
            search = self.external.crossref_search_bibliographic(reference.raw)
            if search and search.get("message", {}).get("items"):
                best = search["message"]["items"][0]
                crossref_payload = {"message": best}
                doi_resolved = bool(best.get("DOI"))

        if crossref_payload:
            reference = merge_crossref(reference, crossref_payload)

        openalex_payload = None
        if reference.doi:
            openalex_payload = self.external.openalex_get_work(f"doi:{reference.doi}")
        if not openalex_payload and reference.title:
            openalex_payload = self.external.openalex_search(title=reference.title)
        if openalex_payload:
            reference = merge_openalex(reference, openalex_payload)

        if reference.doi and self.config.email:
            unpaywall_payload = self.external.unpaywall_get(reference.doi)
            if unpaywall_payload:
                reference = merge_unpaywall(reference, unpaywall_payload)

        has_published_version = any(
            identifier.type in {"is-preprint-of", "has-published-version"}
            for identifier in reference.related_identifiers
        )
        return reference, doi_resolved, has_published_version

    def _flag_duplicates(self, records: Sequence[CitationRecord]) -> List[Tuple[int, int]]:
        duplicates: List[Tuple[int, int]] = []
        doi_map: Dict[str, int] = {}
        for idx, record in enumerate(records):
            doi = record.reference.doi
            if doi:
                doi_lower = doi.lower()
                if doi_lower in doi_map:
                    duplicates.append((doi_map[doi_lower], idx))
                    record.add_flag(CitationFlag.POSSIBLE_DUPLICATE)
                    records[doi_map[doi_lower]].add_flag(CitationFlag.POSSIBLE_DUPLICATE)
                else:
                    doi_map[doi_lower] = idx

        for i in range(len(records)):
            title_i = records[i].reference.title or records[i].reference.raw
            for j in range(i + 1, len(records)):
                title_j = records[j].reference.title or records[j].reference.raw
                similarity = fuzz.token_sort_ratio(title_i, title_j) / 100.0
                if similarity >= 0.95:
                    duplicates.append((i, j))
                    records[i].add_flag(CitationFlag.POSSIBLE_DUPLICATE)
                    records[j].add_flag(CitationFlag.POSSIBLE_DUPLICATE)
        return duplicates

    def _sort_records(self, records: List[CitationRecord], order_indices: Sequence[int]) -> List[CitationRecord]:
        if self.config.sort_mode == "author":
            return sorted(
                records,
                key=lambda record: (record.reference.authors[0].name.split()[-1].lower() if record.reference.authors else "", record.reference.year or 0),
            )
        if self.config.sort_mode == "year":
            return sorted(records, key=lambda record: record.reference.year or 0, reverse=True)
        if self.config.sort_mode == "order":
            combined = list(zip(records, order_indices))
            combined.sort(key=lambda item: item[1])
            return [record for record, _ in combined]
        return records
