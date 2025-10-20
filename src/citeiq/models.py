"""Pydantic models that capture the normalized citation schema and scoring artefacts."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Sequence

from pydantic import BaseModel, Field


class CitationFlag(str, Enum):
    DOI_UNRESOLVED = "doi_unresolved"
    METADATA_MISMATCH = "metadata_mismatch"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    RETRACTED = "retracted"
    HAS_NEWER_VERSION = "has_newer_version"
    PREFERS_PUBLISHED_VERSION = "prefers_published_version"
    PREPRINT = "preprint"
    LACKS_IDENTIFIER = "lacks_identifier"


class Identifier(BaseModel):
    type: str
    value: str


class Author(BaseModel):
    name: str
    orcid: Optional[str] = None
    affiliations: Sequence[str] = Field(default_factory=list)
    affiliation_ror: Sequence[str] = Field(default_factory=list)


class Affiliation(BaseModel):
    name: str
    ror: Optional[str] = None
    type: Optional[str] = None


class NormalizedReference(BaseModel):
    raw: str
    index: Optional[int] = None
    source_file: Optional[str] = None
    title: Optional[str] = None
    authors: Sequence[Author] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    publisher: Optional[str] = None
    type: Optional[str] = None
    identifiers: Sequence[Identifier] = Field(default_factory=list)
    issn_isbn: Sequence[str] = Field(default_factory=list)
    url: Optional[str] = None
    abstract: Optional[str] = None
    topics: Sequence[str] = Field(default_factory=list)
    affiliations: Sequence[Affiliation] = Field(default_factory=list)
    citation_count: Optional[int] = None
    is_open_access: Optional[bool] = None
    best_oa_location: Optional[str] = None
    related_identifiers: Sequence[Identifier] = Field(default_factory=list)
    is_retracted: Optional[bool] = None
    is_preprint: Optional[bool] = None
    updates: Sequence[Identifier] = Field(default_factory=list)
    version_of: Sequence[Identifier] = Field(default_factory=list)
    indexed_in: Sequence[str] = Field(default_factory=list)

    @property
    def doi(self) -> Optional[str]:
        for identifier in self.identifiers:
            if identifier.type.lower() == "doi":
                return identifier.value
        return None

    @property
    def primary_identifier(self) -> Optional[Identifier]:
        if self.identifiers:
            return self.identifiers[0]
        return None


class RawReference(BaseModel):
    """Minimal record captured at ingestion."""

    raw: str
    index: Optional[int] = None
    source_file: Optional[str] = None


class CitationScore(BaseModel):
    provenance: float = 0.0
    metadata_consistency: float = 0.0
    currency: float = 0.0
    reliability: float = 0.0
    impact: float = 0.0
    type_bonus: float = 0.0
    penalties: float = 0.0

    def total(self) -> float:
        score = (
            self.provenance
            + self.metadata_consistency
            + self.currency
            + self.reliability
            + self.impact
            + self.type_bonus
            + self.penalties
        )
        return max(0.0, min(100.0, score))


class CitationRecord(BaseModel):
    reference: NormalizedReference
    score: CitationScore
    flags: List[CitationFlag] = Field(default_factory=list)

    def add_flag(self, flag: CitationFlag) -> None:
        if flag not in self.flags:
            self.flags.append(flag)
