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


@pytest.mark.parametrize(('first', 'second'), [
    ('https://facebook.com/profile.php?id=123', 'https://facebook.com/profile.php?id=456'),
    ('https://linkedin.com/company/offline-boutique-one', 'https://linkedin.com/company/offline-boutique-two'),
])
def test_distinct_hosted_organizations_survive_lead_discovery(first, second):
    assert identity_key(first) != identity_key(second)
    rows = [{**candidate(first), 'source_id': 'offline-search-one'},
            {**candidate(second), 'source_id': 'offline-search-two'}]
    leads = asyncio.run(discover_leads(FixtureSearch(rows), 'clothing', 'GH'))
    assert len(leads) == 2
    assert len({lead.id for lead in leads}) == 2
    assert {lead.source_id for lead in leads} == {'offline-search-one', 'offline-search-two'}


@pytest.mark.parametrize(('canonical', 'alias'), [
    ('https://facebook.com/profile.php?id=123', 'https://www.facebook.com/profile.php?id=123&utm_source=offline#about'),
    ('https://facebook.com/profile.php?id=123', 'http://m.facebook.com/profile.php?id=123&tracking=discard'),
    ('https://linkedin.com/company/offline-boutique', 'https://www.linkedin.com/company/offline-boutique/?utm_source=offline#about'),
    ('https://linkedin.com/company/offline-boutique', 'https://linkedin.com/company/offline-boutique/about/'),
    ('https://instagram.com/offline-boutique', 'https://www.instagram.com/offline-boutique/?utm_source=offline'),
])
def test_tracking_and_known_profile_aliases_do_not_duplicate_prospects(canonical, alias):
    assert identity_key(canonical) == identity_key(alias)
    leads = asyncio.run(discover_leads(FixtureSearch([candidate(canonical), candidate(alias)]), 'clothing', 'NG'))
    assert len(leads) == 1
    assert asyncio.run(discover_leads(FixtureSearch([candidate(alias)]), 'clothing', 'NG',
                                     existing_urls=(canonical,))) == ()


def test_ambiguous_facebook_identity_and_individual_linkedin_profile_are_not_organization_leads():
    rows = [candidate('https://facebook.com/profile.php'),
            candidate('https://linkedin.com/in/offline-person', snippet='A clothing business owner and shop enthusiast.')]
    assert asyncio.run(discover_leads(FixtureSearch(rows), 'clothing', 'GH')) == ()


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
