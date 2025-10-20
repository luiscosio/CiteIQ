"""Quality scoring implementation following the rule-based recipe."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable, Optional, Sequence, Tuple

from rapidfuzz import fuzz

from .models import CitationFlag, CitationRecord, CitationScore, NormalizedReference


@dataclass
class ScoreInputs:
    raw_reference: str
    title_for_similarity: Optional[str]
    metadata_title: Optional[str]
    metadata_year: Optional[int]
    parsed_year: Optional[int]
    authors: Sequence[str]
    doi_resolved: bool
    has_published_version: bool
    has_newer_version: bool
    is_preprint: bool
    is_peer_reviewed: bool
    is_retracted: bool
    is_open_access: Optional[bool]
    indexed_in: Sequence[str]
    citation_count: Optional[int]


def _title_similarity(candidate: Optional[str], metadata_title: Optional[str]) -> float:
    if not candidate or not metadata_title:
        return 0.0
    return fuzz.token_sort_ratio(candidate, metadata_title) / 100.0


def _author_presence_score(raw_reference: str, authors: Sequence[str]) -> float:
    if not authors:
        return 0.0
    matches = 0
    for author in authors[:5]:
        last_name = author.split()[-1]
        if last_name and last_name.lower() in raw_reference.lower():
            matches += 1
    return matches / min(len(authors[:5]), 5)


def compute_score(reference: NormalizedReference, inputs: ScoreInputs) -> Tuple[CitationScore, Iterable[CitationFlag]]:
    flags: list[CitationFlag] = []
    score = CitationScore()

    # Provenance
    if inputs.doi_resolved or reference.doi:
        score.provenance += 15
    else:
        score.penalties -= 30
        flags.append(CitationFlag.DOI_UNRESOLVED)

    # Metadata consistency
    similarity_candidate = inputs.title_for_similarity or inputs.raw_reference
    similarity = _title_similarity(similarity_candidate, inputs.metadata_title)
    if similarity >= 0.9:
        score.metadata_consistency += 10
    elif similarity >= 0.75:
        score.metadata_consistency += 5
    else:
        score.penalties -= 15
        flags.append(CitationFlag.METADATA_MISMATCH)

    author_presence = _author_presence_score(inputs.raw_reference, inputs.authors)
    if author_presence >= 0.8:
        score.metadata_consistency += 5
    elif author_presence < 0.3 and inputs.authors:
        score.penalties -= 5
        flags.append(CitationFlag.METADATA_MISMATCH)

    # Year check
    year_delta = None
    if inputs.metadata_year and inputs.parsed_year:
        year_delta = abs(inputs.metadata_year - inputs.parsed_year)
    if year_delta is not None:
        if year_delta == 0:
            score.metadata_consistency += 5
        elif year_delta == 1:
            score.metadata_consistency += 2
        elif year_delta > 1:
            score.penalties -= 10

    # Currency
    now_year = datetime.now(UTC).year
    years_since = None
    if inputs.metadata_year:
        years_since = max(0, now_year - inputs.metadata_year)
        score.currency += max(0.0, 20.0 - years_since)

    if inputs.has_newer_version:
        score.penalties -= 20
        flags.append(CitationFlag.HAS_NEWER_VERSION)

    # Reliability
    if inputs.is_retracted:
        score.penalties -= 100  # Hard stop
        flags.append(CitationFlag.RETRACTED)
    else:
        if inputs.is_peer_reviewed:
            score.reliability += 10
        if inputs.indexed_in:
            score.reliability += 5
        if inputs.is_open_access:
            score.reliability += 3

    if inputs.is_preprint and inputs.has_published_version:
        flags.append(CitationFlag.PREFERS_PUBLISHED_VERSION)

    # Impact
    if inputs.citation_count:
        score.impact += min(10.0, max(0.0, 2.0 * (inputs.citation_count**0.5)))

    # Type bonuses
    if reference.type in {"standard", "guideline"}:
        score.type_bonus += 10
    elif reference.type in {"journal-article", "proceedings-article"}:
        score.type_bonus += 5

    return score, flags


def build_citation_record(reference: NormalizedReference, inputs: ScoreInputs) -> CitationRecord:
    score, flags = compute_score(reference, inputs)
    record = CitationRecord(reference=reference, score=score, flags=list(flags))
    if inputs.is_preprint and inputs.has_published_version:
        record.add_flag(CitationFlag.PREFERS_PUBLISHED_VERSION)
    return record
