"""Licensed fixed-host acquisition integrated with the existing leased worker."""
import asyncio
import hashlib
import json
import time

import pytest
from sqlalchemy import select

from ayo.budgets import BudgetPolicy
from ayo.models import ResearchJob, ResearchReportRecord, ProviderUsageReservation
from ayo.jobs import enqueue, process_one
from ayo.research import ResearchError, ResearchReport, ResearchService
from ayo.wikidata_source import WikidataProvider
from test_platform_flow import platform  # noqa: F401
from test_merchant_analysis import free_config


def source_config(monkeypatch):
    free_config(monkeypatch)
    monkeypatch.setenv('AYO_AI_DATA_POLICY','public_only_reviewed')
    monkeypatch.setenv('AYO_WIKIDATA_READ_AUTHORIZED','1')
    monkeypatch.setenv('AYO_WIKIDATA_API_REVIEW','cc0_reviewed')
    monkeypatch.setenv('AYO_WIKIDATA_BILLING_MODE','free_only_reviewed')
    monkeypatch.setenv('AYO_REQUEST_CALL_LIMIT','2')
    for key,value in {'SEARCH_RESERVATION_MICROUSD':'0','FETCH_RESERVATION_MICROUSD':'0',
        'DAILY_BUDGET_MICROUSD':'0','SCOPE_DAILY_BUDGET_MICROUSD':'0',
        'DAILY_CALL_LIMIT':'2','SCOPE_DAILY_CALL_LIMIT':'2',
        'BUDGET_POLICY_VERSION':'offline-cc0-v1',
        'BUDGET_POLICY_VALID_UNTIL':str((int(time.time())//86400+1)*86400)}.items():
        monkeypatch.setenv('AYO_WIKIDATA_'+key,value)


def test_fixed_entity_source_rejects_foreign_targets_before_network(monkeypatch):
    source_config(monkeypatch)
    provider=WikidataProvider()
    for url in ('https://evil.example/wiki/Special:EntityData/Q123.json',
                'https://www.wikidata.org/wiki/Special:EntityData/Q123.json?url=http://localhost',
                'https://www.wikidata.org/wiki/Special:EntityData/../secret.json'):
        with pytest.raises(ResearchError):asyncio.run(provider.fetch(url,'NG'))
    assert BudgetPolicy.from_env('wikidata','fetch').reservation_microusd==0


def test_cc0_source_completes_existing_worker_with_committed_real_shape_evidence(platform,monkeypatch):
    source_config(monkeypatch)
    calls=[]
    async def get_json(path):
        calls.append(path)
        return {'entities':{'Q123':{'id':'Q123','type':'item','lastrevid':42,
            'labels':{'en':{'value':'Offline company fixture'}},
            'descriptions':{'en':{'value':'fictional e-commerce company used only in offline tests'}},
            'claims':{'P17':[{'mainsnak':{'datavalue':{'value':{'id':'Q1033'}}}}]}}}}
    from cryptography.fernet import Fernet
    from ayo.intelligence import IntelligenceResult
    key=Fernet.generate_key();fernet=Fernet(key)
    async def fixture_enrich(report,provider=None):
        with platform.factory() as session:
            row=session.scalar(select(ResearchReportRecord))
            assert row.status=='PENDING_ANALYSIS'
        source=report.source_documents[0]
        result=IntelligenceResult(status='completed',provider='gemini',model='offline-fixture',
            summary='Offline only',generated_at=source.retrieved_at,
            claims=({'text':source.content.splitlines()[1],'kind':'OBSERVED',
                'quote':source.content.splitlines()[1],'evidence_ids':[source.id]},),
            recommendations=({'text':'Verify product information separately.','evidence_ids':[source.id],
                              'permission_required':'merchant_review'},),limitations=('Offline fixture.',))
        return ResearchReport.model_validate({**report.model_dump(),'analysis_status':'completed','analysis':result})
    monkeypatch.setattr('ayo.jobs.enrich_report',fixture_enrich)
    with platform.factory() as session:
        job=enqueue(session,fernet,url='https://www.wikidata.org/wiki/Special:EntityData/Q123.json',
            country='NG',business_name='Offline company fixture',anonymous_id='x'*40)
        session.commit();job_id=job.id
    assert asyncio.run(process_one(platform.factory,fernet,
        lambda:ResearchService(WikidataProvider(get_json=get_json))))
    with platform.factory() as session:
        job=session.get(ResearchJob,job_id)
        assert job.status=='succeeded' and job.attempts==1
        report=ResearchReport.model_validate_json(session.get(ResearchReportRecord,job.report_id).report_json)
        source=report.source_documents[0]
        assert source.provider=='wikidata_cc0' and source.robots_policy=='API_POLICY_REVIEWED'
        assert 'Nigeria' in source.content and hashlib.sha256(source.content.encode()).hexdigest()==source.source_hash
        assert report.analysis_status=='completed'
        assert not report.opportunities
        assert not any('hosted provider' in item or 'merchant claims' in item for item in report.limitations)
        assert any('Missing fields' in item for item in report.limitations)
        assert len(session.scalars(select(ProviderUsageReservation)).all())==1
    assert calls==['/wiki/Special:EntityData/Q123.json']


def test_company_search_omits_individuals_and_does_not_trust_returned_urls(monkeypatch):
    from contextlib import nullcontext
    source_config(monkeypatch)
    async def fake(path):
        assert path.startswith('/w/api.php?action=wbsearchentities&')
        return {'search':[{'id':'Q1','label':'Fixture company','description':'e-commerce company','url':'http://localhost/secret'},
                          {'id':'Q2','label':'Unrelated person','description':'politician'}]}
    candidates=asyncio.run(WikidataProvider(get_json=fake,dispatch_budget=lambda *_:nullcontext()).search('Company'))
    assert len(candidates)==1 and candidates[0].url=='https://www.wikidata.org/wiki/Special:EntityData/Q1.json'


def test_explicit_changed_target_review_keeps_zero_cost_source_counts(platform,monkeypatch):
    from ayo.budgets import UsageLedger
    from ayo.models import ProviderBudgetAccount,AuditEvent
    source_config(monkeypatch)
    ledger=UsageLedger(platform.factory)
    ledger.reserve(scope_id='cc0-test',request_id='first',dispatch_id='first',policy=BudgetPolicy.from_env('wikidata','search'))
    ledger.review_additional_cc0_reads(additional_calls=2,reason='Founder requested a different small business after excluding the earlier target.')
    with platform.factory() as session:
        row=session.scalar(select(ProviderBudgetAccount).where(ProviderBudgetAccount.kind=='provider_day'))
        assert row.call_limit==4 and row.calls==1 and row.limit_microusd==0
        assert session.scalar(select(AuditEvent).where(AuditEvent.action=='budget.cc0_target_review')) is not None
        assert len(session.scalars(select(ProviderUsageReservation)).all())==1


@pytest.mark.parametrize('description,claims', [
    ('politician', {}),
    ('company founder', {'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q5'}}}}]})])
def test_direct_nonbusiness_entity_never_becomes_report(monkeypatch, description, claims):
    from contextlib import nullcontext
    source_config(monkeypatch)
    calls = []
    async def fake(path):
        calls.append(path)
        return {'entities': {'Q123': {'id': 'Q123', 'type': 'item',
            'labels': {'en': {'value': 'Excluded entity fixture'}},
            'descriptions': {'en': {'value': description}}, 'claims': claims}}}
    service = ResearchService(WikidataProvider(get_json=fake, dispatch_budget=lambda *_:nullcontext()))
    with pytest.raises(ResearchError) as error:
        asyncio.run(service.research('https://www.wikidata.org/wiki/Special:EntityData/Q123.json', 'GH'))
    assert error.value.code == 'source_not_business' and len(calls) == 1
