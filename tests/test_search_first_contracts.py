"""Offline gates proving the search-first model cannot display fake trust levels."""
import json
from pathlib import Path
import pytest
from ayo.search_first_contracts import EvidenceClaim, OrganizationLeadPreview, PublicMiniReport

ROOT=Path(__file__).resolve().parents[1]

def test_site_search_first_and_shopify_optional():
    journey=json.loads((ROOT/'architecture/search_first_journey.json').read_text())
    assert journey['entry_priority']=='search_first'
    assert journey['pre_signup_access']['requires_account'] is False
    assert journey['shopify']=='optional_after_account'
    assert journey['flow'].index('generate_sourced_mini_report') < journey['flow'].index('create_free_account')
    assert journey['flow'].index('create_free_account') < journey['flow'].index('optional_connections')
    assert 'business_without_website_owner_facts' in journey['supports_inputs']
    assert journey['founding_cohort']['all_released_features_free'] is True
    assert journey['founding_cohort']['first_distinct_customer_users']==500

def test_ai_can_be_switched_but_never_directly_executes():
    routing=json.loads((ROOT/'architecture/ai_provider_routing.json').read_text())
    assert routing['default_discovery_provider']=='gemini'
    assert routing['no_immutable_provider_lock_in']
    assert next(r['provider'] for r in routing['task_routes'] if r['task']=='external_write')=='ayo_policy_engine_only'
    assert routing['promises_first_500_all_features_free'] is True

def test_public_claim_requires_evidence():
    with pytest.raises(ValueError,match='source evidence'):
        EvidenceClaim('Average conversion 18%', 'OBSERVED', ())
    c=EvidenceClaim('Offers handmade dresses', 'OBSERVED', ('public-page-1',))
    report=PublicMiniReport('PUBLIC_WEB',(c,))
    assert report.next_primary_action=='Create your free Ayo account'
    assert report.shopify_connected is False

def test_anonymous_leads_real_provider_only():
    lead=OrganizationLeadPreview('Public boutique candidate','web-source-a','https://boutique.example')
    with pytest.raises(ValueError,match='Never fabricate leads'):
        PublicMiniReport('PUBLIC_WEB',(),(lead,),False)
    with pytest.raises(ValueError,match='capped at three'):
        PublicMiniReport('PUBLIC_WEB',(),(lead,lead,lead,lead),True)
    with pytest.raises(ValueError,match='contacted or sold'):
        OrganizationLeadPreview('Boutique','src','https://boutique.example','SOLD')

def test_owner_supplied_is_not_independent_site_evidence():
    with pytest.raises(ValueError,match='cannot masquerade'):
        PublicMiniReport('OWNER_PROVIDED_UNVERIFIED',(EvidenceClaim('Selling shoes','OBSERVED',('self-description',)),))
    report=PublicMiniReport('OWNER_PROVIDED_UNVERIFIED',(EvidenceClaim('Merchant says they sell shoes','INFERRED'),))
    assert report.website_ownership_verified is False
    with pytest.raises(ValueError,match='never proves ownership'):
        PublicMiniReport('PUBLIC_WEB',(),shopify_connected=True)

def test_source_requirements_exist_in_codex_docs():
    readme=(ROOT/'START_CODEX_HERE.md').read_text()
    assert 'SEARCH-FIRST' in readme
    assert 'docs/25' in readme
    for num in range(25,29):
        assert list((ROOT/'docs').glob(f'{num:02d}_*.md'))
