"""Reporting utilities to build CSV/Excel exports and Markdown summaries."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import pandas as pd

from .clustering import ClusterSummary, top_entities
from .models import CitationFlag, CitationRecord


def records_to_dataframe(records: Sequence[CitationRecord]) -> pd.DataFrame:
    rows = []
    for record in records:
        ref = record.reference
        rows.append(
            {
                "index": ref.index,
                "raw": ref.raw,
                "title": ref.title,
                "authors": "; ".join(author.name for author in ref.authors),
                "year": ref.year,
                "venue": ref.venue,
                "publisher": ref.publisher,
                "type": ref.type,
                "doi": ref.doi,
                "identifiers": "; ".join(f"{identifier.type}:{identifier.value}" for identifier in ref.identifiers),
                "issn_isbn": "; ".join(ref.issn_isbn),
                "is_open_access": ref.is_open_access,
                "best_oa_location": ref.best_oa_location,
                "citation_count": ref.citation_count,
                "topics": "; ".join(ref.topics),
                "flags": "; ".join(flag.value for flag in record.flags),
                "score_total": record.score.total(),
                "score_provenance": record.score.provenance,
                "score_metadata": record.score.metadata_consistency,
                "score_currency": record.score.currency,
                "score_reliability": record.score.reliability,
                "score_impact": record.score.impact,
                "score_type": record.score.type_bonus,
                "score_penalties": record.score.penalties,
            }
        )
    df = pd.DataFrame(rows)
    df.sort_values(by=["score_total"], ascending=False, inplace=True)
    return df


def export_tabular_data(df: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "references.csv"
    xlsx_path = output_dir / "references.xlsx"
    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)


def _chart_base(output_dir: Path, filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / filename


def plot_recency_histogram(df: pd.DataFrame, output_dir: Path) -> Path:
    filtered = df.dropna(subset=["year"])
    if filtered.empty:
        return _chart_base(output_dir, "recency.png")
    plt.figure(figsize=(6, 4))
    plt.hist(filtered["year"], bins=10, color="#1f77b4", edgecolor="white")
    plt.title("Publication Year Distribution")
    plt.xlabel("Year")
    plt.ylabel("Count")
    path = _chart_base(output_dir, "recency.png")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def plot_preprint_share(records: Sequence[CitationRecord], output_dir: Path) -> Path:
    preprints = sum(
        1
        for record in records
        if record.reference.is_preprint or CitationFlag.PREFERS_PUBLISHED_VERSION in record.flags
    )
    total = len(records)
    if total == 0:
        return _chart_base(output_dir, "preprints.png")
    plt.figure(figsize=(5, 5))
    plt.pie([preprints, total - preprints], labels=["Preprint", "Peer-reviewed"], autopct="%1.0f%%", colors=["#ff7f0e", "#2ca02c"])
    plt.title("Preprint vs Peer-reviewed")
    path = _chart_base(output_dir, "preprints.png")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def plot_top_cited(df: pd.DataFrame, output_dir: Path, top_n: int = 10) -> Path:
    filtered = df.dropna(subset=["citation_count"])
    if filtered.empty:
        return _chart_base(output_dir, "top_cited.png")
    top = filtered.nlargest(top_n, "citation_count")
    plt.figure(figsize=(8, 4))
    plt.barh(top["title"], top["citation_count"], color="#9467bd")
    plt.xlabel("Citation Count")
    plt.ylabel("Title")
    plt.title("Most Cited References")
    plt.tight_layout()
    path = _chart_base(output_dir, "top_cited.png")
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def render_markdown_report(
    df: pd.DataFrame,
    records: Sequence[CitationRecord],
    author_clusters: Sequence[ClusterSummary],
    org_clusters: Sequence[ClusterSummary],
    topic_clusters: Sequence[ClusterSummary],
    charts: Iterable[Path],
) -> str:
    lines = ["# CiteIQ Reference Quality Report", ""]
    total = len(records)
    flagged = sum(1 for record in records if record.flags)
    preprints = sum(1 for record in records if record.reference.is_preprint)
    retractions = sum(1 for record in records if CitationFlag.RETRACTED in record.flags)
    lines.append(f"- Total references: **{total}**")
    lines.append(f"- References with flags: **{flagged}**")
    lines.append(f"- Preprints: **{preprints}**")
    lines.append(f"- Retracted: **{retractions}**")
    lines.append("")

    if charts:
        lines.append("## Visuals")
        for chart in charts:
            lines.append(f"![{chart.stem}]({chart.name})")
        lines.append("")

    lines.append("## Top Authors")
    author_counts = top_entities(author.name for record in records for author in record.reference.authors)
    if author_counts:
        for name, count in author_counts:
            lines.append(f"- {name}: {count}")
    else:
        lines.append("_No authors available._")
    lines.append("")

    lines.append("## Top Organisations")
    org_counts = top_entities(aff.name for record in records for aff in record.reference.affiliations)
    if org_counts:
        for name, count in org_counts:
            lines.append(f"- {name}: {count}")
    else:
        lines.append("_No organisation data available._")
    lines.append("")

    if author_clusters:
        lines.append("## Author Clusters")
        for cluster in author_clusters:
            lines.append(f"- **{cluster.label}** ({cluster.size} members): {', '.join(cluster.members)}")
        lines.append("")

    if org_clusters:
        lines.append("## Organisation Clusters")
        for cluster in org_clusters:
            types = ", ".join(f"{k}: {v}" for k, v in cluster.metadata.get("types", {}).items())
            suffix = f" ({types})" if types else ""
            lines.append(f"- **{cluster.label}** ({cluster.size} organisations{suffix}): {', '.join(cluster.members)}")
        lines.append("")

    if topic_clusters:
        lines.append("## Topic Clusters")
        for cluster in topic_clusters:
            keywords = ", ".join(cluster.metadata.get("keywords", [])[:5])
            lines.append(f"- **{cluster.label}** ({cluster.size} items; keywords: {keywords})")
        lines.append("")

    lines.append("## High-Risk References")
    risky = df[df["flags"] != ""]
    if risky.empty:
        lines.append("No risky references detected.")
    else:
        for _, row in risky.iterrows():
            lines.append(f"- **{row['title'] or row['raw']}** ({row['year']}): {row['flags']}")

    return "\n".join(lines)
