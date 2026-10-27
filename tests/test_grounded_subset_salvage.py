"""Provider result triage: never publish hallucinations or unsupported claims."""
from datetime import datetime, timezone
import pytest

from ayo.intelligence import (
    IntelligenceError, PublicResearchContext, SourceEvidence,
    validate_grounded_subset,
)


def ctx():
    return PublicResearchContext(
        country="", question="How could the product presentation improve?",
        evidence=(SourceEvidence(
            id="sample-1", url="https://books.toscrape.com/",
            excerpt="Books to Scrape lists fiction and travel books with prices and stock labels.",
            observed_at=datetime.now(timezone.utc),
        ),),
    )


def valid():
    return {
        "claims": [{"kind": "INFERRED", "text": "The published page suggests that clearer stock labels may help visitors compare titles.",
                    "evidence_ids": ["sample-1"], "quote": ""}],
        "recommendations": [{"text": "Review the visibility of stock labels on catalogue pages.",
                             "evidence_ids": ["sample-1"], "permission_required": "merchant_review"}],
        "limitations": ["Only one source page was checked."],
    }


def test_normal_valid_response_preserved():
    parsed = validate_grounded_subset(valid(), ctx())
    assert len(parsed.claims) == len(parsed.recommendations) == 1


def test_unsupported_observation_is_discarded_without_tainting_valid_inference():
    raw = valid()
    raw["claims"].insert(0, {"kind": "OBSERVED", "text": "Invented word-for-word quotation.",
        "evidence_ids": ["sample-1"], "quote": "Invented word-for-word quotation."})
    result = validate_grounded_subset(raw, ctx())
    assert len(result.claims) == 1
    assert result.claims[0].kind == "INFERRED"
    assert len(result.recommendations) == 1


def test_invented_citation_is_never_preserved():
    raw = valid()
    raw["claims"].append({"kind": "INFERRED", "text": "The published page suggests more options.",
        "evidence_ids": ["fake-source"], "quote": ""})
    result = validate_grounded_subset(raw, ctx())
    assert len(result.claims) == 1
    assert result.claims[0].evidence_ids == ("sample-1",)


def test_all_unsupported_findings_are_rejected():
    raw = valid()
    raw["claims"] = [{"kind": "OBSERVED", "text": "Fictional quoted claim.",
                      "evidence_ids": ["sample-1"], "quote": "Fictional quoted claim."}]
    raw["recommendations"] = [{"text": "Ayo sent an outreach campaign.",
                               "evidence_ids": ["sample-1"], "permission_required": "merchant_review"}]
    with pytest.raises(IntelligenceError):
        validate_grounded_subset(raw, ctx())


def test_financial_and_action_outcome_excluded_even_when_other_evidence_survives():
    raw = valid()
    raw["claims"].append({"kind": "INFERRED", "text": "Revenue increased 30%.",
                           "evidence_ids": ["sample-1"], "quote": ""})
    raw["limitations"].append("Ayo has sent marketing emails.")
    result = validate_grounded_subset(raw, ctx())
    assert len(result.claims) == 1
    assert not any("sent" in x for x in result.limitations)
