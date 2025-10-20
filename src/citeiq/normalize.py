"""Helpers for merging external metadata into the normalized reference structure."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from dateutil import parser as date_parser

from .models import Affiliation, Author, Identifier, NormalizedReference


def _first_str(value: Optional[Sequence[str]]) -> Optional[str]:
    if not value:
        return None
    for candidate in value:
        if candidate:
            return str(candidate)
    return None


def _date_to_year(date_parts: Any) -> Optional[int]:
    if isinstance(date_parts, dict):
        parts = date_parts.get("date-parts") or date_parts.get("date_parts")
    else:
        parts = date_parts
    if isinstance(parts, list) and parts:
        first = parts[0]
        if isinstance(first, list) and first:
            return first[0]
        if isinstance(first, int):
            return first
    if isinstance(date_parts, str):
        try:
            dt = date_parser.parse(date_parts)
            return dt.year
        except (ValueError, TypeError):
            return None
    return None


def merge_crossref(reference: NormalizedReference, crossref_data: Dict[str, Any]) -> NormalizedReference:
    work = crossref_data.get("message") if crossref_data else None
    if not work:
        return reference

    title = _first_str(work.get("title")) or reference.title
    container = _first_str(work.get("container-title")) or reference.venue
    issued_year = _date_to_year(work.get("issued")) or reference.year
    authors: List[Author] = []
    for author in work.get("author", []):
        name_parts = [author.get("given"), author.get("family")]
        name = " ".join(filter(None, name_parts)).strip()
        if not name:
            name = author.get("name", "")
        affs = [aff.get("name") for aff in author.get("affiliation", []) if aff.get("name")]
        affiliations = [Affiliation(name=aff) for aff in affs]
        authors.append(
            Author(
                name=name,
                orcid=author.get("ORCID"),
                affiliations=[aff.name for aff in affiliations],
            )
        )

    identifiers = list(reference.identifiers)
    doi = work.get("DOI")
    if doi:
        if not any(id_.type.lower() == "doi" and id_.value.lower() == doi.lower() for id_ in identifiers):
            identifiers.append(Identifier(type="DOI", value=doi))

    issn_isbn = list(reference.issn_isbn)
    for issn in work.get("ISSN", []):
        if issn not in issn_isbn:
            issn_isbn.append(issn)
    if isbn := work.get("ISBN"):
        for value in isbn if isinstance(isbn, list) else [isbn]:
            if value not in issn_isbn:
                issn_isbn.append(value)

    related_identifiers = list(reference.related_identifiers)
    updates: List[Identifier] = list(reference.updates)
    version_of: List[Identifier] = list(reference.version_of)
    if isinstance(work.get("relation"), dict):
        for relation_type, payload in work["relation"].items():
            if not isinstance(payload, list):
                continue
            for item in payload:
                identifier = Identifier(type=relation_type, value=item.get("id") or item.get("DOI", ""))
                if relation_type in {"is-preprint-of", "has-preprint"}:
                    related_identifiers.append(identifier)
                elif relation_type in {"is-version-of", "has-version"}:
                    version_of.append(identifier)
                elif relation_type in {"updates", "is-updated-by"}:
                    updates.append(identifier)

    is_preprint = reference.is_preprint
    if work.get("type") == "posted-content":
        is_preprint = True

    return reference.model_copy(
        update={
            "title": title,
            "venue": container,
            "publisher": work.get("publisher") or reference.publisher,
            "year": issued_year,
            "type": work.get("type") or reference.type,
            "authors": authors or reference.authors,
            "issn_isbn": issn_isbn,
            "identifiers": identifiers,
            "citation_count": work.get("is-referenced-by-count") or reference.citation_count,
            "url": work.get("URL") or reference.url,
            "is_retracted": (work.get("assertion")[0].get("label") == "retraction" if work.get("assertion") and len(work.get("assertion")) > 0 else reference.is_retracted),
            "related_identifiers": related_identifiers,
            "updates": updates,
            "version_of": version_of,
            "is_preprint": is_preprint,
        }
    )


def merge_openalex(reference: NormalizedReference, openalex_data: Dict[str, Any]) -> NormalizedReference:
    if not openalex_data:
        return reference
    work = openalex_data.get("results")
    if isinstance(work, list) and work:
        work = work[0]
    elif openalex_data.get("id"):
        work = openalex_data
    if not work:
        return reference

    title = work.get("display_name") or reference.title
    year = work.get("publication_year") or reference.year
    citation_count = work.get("cited_by_count") or reference.citation_count

    authors: List[Author] = []
    affiliations: List[Affiliation] = []
    for authorship in work.get("authorships", []):
        author_info = authorship.get("author", {})
        institutions = authorship.get("institutions", [])
        affiliation_names = [inst.get("display_name") for inst in institutions if inst.get("display_name")]
        rors = [inst.get("ror") for inst in institutions if inst.get("ror")]
        authors.append(
            Author(
                name=author_info.get("display_name", ""),
                orcid=author_info.get("orcid"),
                affiliations=affiliation_names,
                affiliation_ror=rors,
            )
        )
        for inst in institutions:
            name = inst.get("display_name")
            if not name:
                continue
            aff = Affiliation(name=name, ror=inst.get("ror"), type=inst.get("type"))
            if aff not in affiliations:
                affiliations.append(aff)

    topics = [concept.get("display_name") for concept in work.get("concepts", []) if concept.get("display_name")]
    abstract = ""
    if inverted := work.get("abstract_inverted_index"):
        # Flatten indexes preserving order
        all_indices = [idx for indices in inverted.values() for idx in indices]
        if all_indices:
            abstract_words = [""] * (max(all_indices) + 1)
            for word, positions in inverted.items():
                for pos in positions:
                    if pos < len(abstract_words):
                        abstract_words[pos] = word
            abstract = " ".join(abstract_words)

    identifiers = list(reference.identifiers)
    if openalex_id := work.get("id"):
        identifiers.append(Identifier(type="OpenAlex", value=openalex_id))
    if doi := work.get("doi"):
        if not any(id_.type.lower() == "doi" and id_.value.lower() == doi.lower() for id_ in identifiers):
            identifiers.append(Identifier(type="DOI", value=doi))

    is_preprint = reference.is_preprint
    host_venue = work.get("host_venue", {})
    if host_venue.get("type") == "repository":
        is_preprint = True

    is_retracted = work.get("is_retracted")
    updates = list(reference.updates)
    version_of = list(reference.version_of)
    for rel in work.get("related_works", []):
        relation_type = rel.get("relationship")
        identifier = Identifier(type=relation_type or "related", value=rel.get("id", ""))
        if relation_type in {"has_version", "is_version_of"}:
            version_of.append(identifier)
        elif relation_type in {"updates"}:
            updates.append(identifier)

    oa = work.get("open_access", {})
    is_oa = oa.get("is_oa")
    best_location = oa.get("oa_url") or reference.best_oa_location

    indexed_in = list(reference.indexed_in)
    for inst in work.get("indexed_in", []):
        if inst not in indexed_in:
            indexed_in.append(inst)

    return reference.model_copy(
        update={
            "title": title,
            "year": year,
            "citation_count": citation_count,
            "authors": authors or reference.authors,
            "affiliations": affiliations or reference.affiliations,
            "topics": topics or reference.topics,
            "abstract": abstract or reference.abstract,
            "identifiers": identifiers,
            "is_preprint": is_preprint,
            "is_retracted": is_retracted if is_retracted is not None else reference.is_retracted,
            "best_oa_location": best_location,
            "is_open_access": is_oa if is_oa is not None else reference.is_open_access,
            "updates": updates,
            "version_of": version_of,
            "venue": host_venue.get("display_name") or reference.venue,
            "indexed_in": indexed_in,
        }
    )


def merge_unpaywall(reference: NormalizedReference, unpaywall_data: Dict[str, Any]) -> NormalizedReference:
    if not unpaywall_data:
        return reference
    is_oa = unpaywall_data.get("is_oa")
    best = unpaywall_data.get("best_oa_location") or {}
    oa_url = best.get("url_for_pdf") or best.get("url")
    return reference.model_copy(
        update={
            "is_open_access": is_oa if is_oa is not None else reference.is_open_access,
            "best_oa_location": oa_url or reference.best_oa_location,
        }
    )

