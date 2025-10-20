"""Utility functions for ingesting raw reference strings from plain text or BibTeX sources."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import bibtexparser

from .models import Identifier, NormalizedReference, RawReference

IEEE_ENTRY_RE = re.compile(r"^\s*\[?(\d+)\]?\s*(.+)", re.IGNORECASE)
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
PMID_RE = re.compile(r"PMID\s*[:\s]\s*(\d+)", re.IGNORECASE)
ARXIV_RE = re.compile(r"arXiv\s*[:\s]\s*([0-9]+\.[0-9]+|[a-z-]+/[0-9]+)", re.IGNORECASE)
URL_RE = re.compile(r"(https?://\S+)")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _split_ieee_entries(text: str) -> List[Tuple[Optional[int], str]]:
    entries: List[Tuple[Optional[int], str]] = []
    current_index: Optional[int] = None
    current_chunks: List[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = IEEE_ENTRY_RE.match(line)
        if match:
            if current_chunks:
                entries.append((current_index, " ".join(current_chunks).strip()))
                current_chunks = []
            current_index = int(match.group(1))
            remainder = match.group(2).strip()
            if remainder:
                current_chunks.append(remainder)
        else:
            if current_chunks:
                current_chunks.append(line)
            else:
                current_chunks = [line]

    if current_chunks:
        entries.append((current_index, " ".join(current_chunks).strip()))

    return entries


def _identifiers_from_text(text: str) -> List[Identifier]:
    identifiers: List[Identifier] = []
    if doi_match := DOI_RE.search(text):
        identifiers.append(Identifier(type="DOI", value=doi_match.group(0)))
    if pmid_match := PMID_RE.search(text):
        identifiers.append(Identifier(type="PMID", value=pmid_match.group(1)))
    if arxiv_match := ARXIV_RE.search(text):
        identifiers.append(Identifier(type="arXiv", value=arxiv_match.group(1)))
    for url_match in URL_RE.findall(text):
        identifiers.append(Identifier(type="URL", value=url_match))
    return identifiers


def read_plaintext_references(path: Path, source_label: Optional[str] = None) -> List[RawReference]:
    text = path.read_text(encoding="utf-8")
    entries = _split_ieee_entries(text)
    raw_refs: List[RawReference] = []
    for idx, entry in entries:
        raw_refs.append(RawReference(raw=entry, index=idx, source_file=source_label or path.name))
    if not entries:
        # Fall back to splitting on blank lines to avoid empty results.
        chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
        for i, chunk in enumerate(chunks, start=1):
            raw_refs.append(RawReference(raw=chunk, index=i, source_file=source_label or path.name))
    return raw_refs


def read_bibtex(path: Path, source_label: Optional[str] = None) -> List[NormalizedReference]:
    parser = bibtexparser.bparser.BibTexParser(common_strings=True)
    with path.open("r", encoding="utf-8") as handle:
        database = bibtexparser.load(handle, parser=parser)

    normalized: List[NormalizedReference] = []
    for entry in database.entries:
        title = entry.get("title")
        year = entry.get("year")
        try:
            year_int = int(year)
        except (TypeError, ValueError):
            year_int = None
        raw_ref = entry.get("note") or title or entry.get("ID", "")
        identifiers: List[Identifier] = []
        if doi := entry.get("doi"):
            identifiers.append(Identifier(type="DOI", value=doi))
        if url := entry.get("url"):
            identifiers.append(Identifier(type="URL", value=url))
        normalized.append(
            NormalizedReference(
                raw=raw_ref,
                index=None,
                title=title,
                year=year_int,
                venue=entry.get("booktitle") or entry.get("journal"),
                publisher=entry.get("publisher"),
                type=entry.get("ENTRYTYPE"),
                identifiers=identifiers,
                issn_isbn=[entry.get("issn")] if entry.get("issn") else [],
                url=entry.get("url"),
                source_file=source_label or path.name,
            )
        )
    return normalized


def extract_initial_metadata(raw_refs: Iterable[RawReference]) -> List[NormalizedReference]:
    normalized: List[NormalizedReference] = []
    for raw in raw_refs:
        identifiers = _identifiers_from_text(raw.raw)
        year = None
        if year_match := YEAR_RE.search(raw.raw):
            try:
                year = int(year_match.group(0))
            except ValueError:
                year = None
        normalized.append(
            NormalizedReference(
                raw=raw.raw,
                index=raw.index,
                identifiers=identifiers,
                type=None,
                year=year,
                source_file=raw.source_file,
            )
        )
    return normalized
