"""Lead evidence and state tests using explicitly offline discovery fixtures."""
import asyncio
from datetime import datetime, timezone

import pytest

from ayo.leads import LeadError, PipelineEvidence, discover_leads, identity_key, transition_lead


def candidate(url='https://boutique.org/', name='Fixture boutique', snippet='A wholesale clothing boutique in Accra.'):
    return {'name': name, 'url': url, 'snippet': snippet, 'source_id': 'search-fixture-1',
            'discovered_at': datetime.now(timezone.utc)}


class FixtureSearch:
    def __init__(self, rows=()):
        self.rows = rows
        self.call = None

    async def search(self, query, country='', city='', limit=5):
        self.call = (query, country, city, limit)
        return self.rows


def test_empty_real_search_does_not_generate_leads():
    assert asyncio.run(discover_leads(FixtureSearch(), 'clothing stockists', 'GH')) == ()


def test_discovery_is_sourced_deduped_and_not_outreach_consent():
    provider = FixtureSearch([candidate(), candidate('https://www.boutique.org/about'), candidate('https://otherboutique.org/')])
    results = asyncio.run(discover_leads(provider, 'clothing stockists', 'GH', 'Accra'))
    assert len(results) == 2
    assert provider.call == ('clothing stockists', 'GH', 'Accra', 5)
    assert results[0].status == 'discovered'
    assert results[0].country == 'GH'
    assert results[0].source_excerpt == 'A wholesale clothing boutique in Accra.'
    assert results[0].fit_evidence_ids == ('search-fixture-1',)
    assert results[0].contact_status == 'unknown'
    assert results[0].outreach_allowed is False
    assert 'email' not in results[0].to_dict()
    assert any('clothing' in reason for reason in results[0].fit_reasons)


def test_existing_domain_is_not_inserted_again():
    rows = asyncio.run(discover_leads(FixtureSearch([candidate()]), 'clothing', 'NG', existing_urls=('https://boutique.org/catalog',)))
    assert rows == ()


def test_shared_marketplace_profiles_remain_distinct():
    assert identity_key('https://instagram.com/boutique-a') != identity_key('https://instagram.com/boutique-b')


@pytest.mark.parametrize('row', [
    candidate('http://127.0.0.1/'),
    candidate('https://user:pass@boutique.org/'),
    candidate(snippet=''),
    candidate(name='Fixture person', snippet='Personal hobbies and a travel diary.'),
    {**candidate(), 'source_id': ''},
    {**candidate(), 'discovered_at': datetime.now()},
])
def test_invalid_unsourced_or_personal_candidates_are_omitted(row):
    assert asyncio.run(discover_leads(FixtureSearch([row]), 'clothing', 'GH')) == ()


def test_market_is_selected_not_guessed():
    provider = FixtureSearch([candidate()])
    with pytest.raises(LeadError, match='Nigeria or Ghana'):
        asyncio.run(discover_leads(provider, 'Nigerian businesses', ''))
    assert provider.call is None


def evidence(**changes):
    data = {'business_id': 'business-a', 'kind': 'qualification', 'reference': 'source-1', 'note': 'Merchant reviewed sourced offer overlap.'}
    data.update(changes)
    return PipelineEvidence(**data)


def transition(current='discovered', next_status='qualified', proof=None, actor='business-a'):
    return transition_lead(business_id='business-a', actor_business_id=actor, current_status=current,
                           next_status=next_status, evidence=proof or evidence())


def test_qualification_requires_source_review_and_keeps_event_provenance():
    result = transition()
    assert result.status == 'qualified'
    assert result.provenance == 'evidence_reviewed'
    assert result.evidence_reference == 'source-1'
    with pytest.raises(LeadError):
        transition(proof=evidence(note=''))


def test_tenant_mismatch_cannot_advance_pipeline():
    with pytest.raises(LeadError) as raised:
        transition(actor='business-b')
    assert raised.value.code == 'forbidden_tenant'
    with pytest.raises(LeadError):
        transition(proof=evidence(business_id='business-b'))


def test_ai_or_public_discovery_cannot_claim_contacted_replied_or_converted():
    with pytest.raises(LeadError) as raised:
        transition('qualified', 'contacted')
    assert raised.value.code == 'verified_event_required'
    with pytest.raises(LeadError):
        transition('discovered', 'converted')
    for current, nxt, kind in [('contacted', 'replied', 'provider_reply'), ('replied', 'converted', 'provider_conversion')]:
        with pytest.raises(LeadError):
            transition(current, nxt, evidence(kind=kind, verified=False))


@pytest.mark.parametrize('changes', [
    {'approved_by_user_id': None}, {'permission_checked': False}, {'suppressed': True},
])
def test_contacted_requires_approval_lawful_checks_and_no_suppression(changes):
    fields = {'kind': 'provider_send', 'verified': True, 'approved_by_user_id': 1, 'permission_checked': True}
    fields.update(changes)
    with pytest.raises(LeadError) as raised:
        transition('qualified', 'contacted', evidence(**fields))
    assert raised.value.code == 'outreach_not_authorized'


def test_verified_outcome_and_manual_outcome_are_distinct():
    verified = transition('replied', 'converted', evidence(kind='provider_conversion', verified=True))
    assert verified.provenance == 'provider_verified'
    manual = transition('replied', 'converted', evidence(kind='merchant_reported', note='Merchant reported a signed order.'))
    assert manual.provenance == 'merchant_reported'
