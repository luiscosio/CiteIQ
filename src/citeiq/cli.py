"""CLI entry point for CiteIQ pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer

from .pipeline import PipelineConfig, ReferencePipeline

app = typer.Typer(help="CiteIQ reference analysis CLI.")


@app.command()
def process(
    inputs: List[Path] = typer.Argument(..., help="Input reference files (.txt or .bib)."),
    output_dir: Path = typer.Option(Path("output"), "--output-dir", "-o", help="Directory to write reports."),
    cache_dir: Optional[Path] = typer.Option(None, "--cache-dir", help="Directory for HTTP cache."),
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Contact email for Unpaywall API."),
    sort_mode: str = typer.Option("author", "--sort", "-s", help="Sort mode: author|year|order."),
    topic_clusters: int = typer.Option(8, "--topic-clusters", "-k", help="Desired number of topic clusters."),
) -> None:
    """Run the full CiteIQ pipeline."""
    if not inputs:
        typer.echo("No input files provided.", err=True)
        raise typer.Exit(code=1)

    config = PipelineConfig(
        input_files=inputs,
        output_dir=output_dir,
        cache_dir=cache_dir,
        email=email,
        sort_mode=sort_mode,
        topic_clusters=topic_clusters,
    )
    pipeline = ReferencePipeline(config)
    result = pipeline.run()

    typer.echo(f"Processed {len(result.records)} references.")
    typer.echo(f"Report saved to {result.markdown_report_path}")


if __name__ == "__main__":
    app()
