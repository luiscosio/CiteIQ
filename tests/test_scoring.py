from citeiq.models import NormalizedReference
from citeiq.scoring import ScoreInputs, compute_score


def test_compute_score_basic() -> None:
    reference = NormalizedReference(
        raw="Doe et al., 2023, Example Journal",
        title="Example Study",
        year=2023,
        type="journal-article",
    )
    inputs = ScoreInputs(
        raw_reference=reference.raw,
        title_for_similarity=reference.title,
        metadata_title=reference.title,
        metadata_year=reference.year,
        parsed_year=2023,
        authors=["Jane Doe", "John Smith"],
        doi_resolved=True,
        has_published_version=False,
        has_newer_version=False,
        is_preprint=False,
        is_peer_reviewed=True,
        is_retracted=False,
        is_open_access=True,
        indexed_in=["PubMed"],
        citation_count=25,
    )
    score, flags = compute_score(reference, inputs)
    assert score.total() > 50
    assert not list(flags)
