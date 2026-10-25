import asyncio
import json
import time

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from ayo.identity import IdentityError
from ayo.jobs import enqueue, get_job, process_one
from ayo.models import Base, ReportClaim, ResearchJob, ResearchReportRecord
from ayo.research import ResearchError, ResearchReport, SourceDocument, build_report


@pytest.fixture
def jobs(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'jobs.db'))
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False), Fernet(Fernet.generate_key())
    engine.dispose()


def test_provider_failure_keeps_job_failed_and_never_fabricates_report(jobs):
    factory, fernet = jobs
    with factory() as session:
        job = enqueue(session, fernet, url='https://fixture-business.org/', country='GH',
                      business_name='Fixture', anonymous_id='a' * 48)
        session.commit()
        assert 'fixture-business' not in job.payload_cipher
        with pytest.raises(IdentityError):
            get_job(session, job.id, 'b' * 48)
    def missing_provider():
        raise ResearchError('provider_not_configured', 'Configuration missing')
    assert asyncio.run(process_one(factory, fernet, missing_provider))
    with factory() as session:
        stored = session.get(ResearchJob, job.id)
        assert stored.status == 'failed'
        assert stored.error_code == 'provider_not_configured'
        assert stored.report_id is None and stored.claim_cipher is None
        assert session.scalar(select(func.count()).select_from(ResearchReportRecord)) == 0
    assert not asyncio.run(process_one(factory, fernet, missing_provider))


def test_expired_worker_lease_is_recovered_with_bounded_attempts(jobs):
    factory, fernet = jobs
    with factory() as session:
        job = enqueue(session, fernet, url='https://fixture-business.org/', country='NG',
                      business_name='Fixture', anonymous_id='a' * 48)
        job.status, job.attempts, job.lease_until = 'running', 3, time.time() - 1
        session.commit()
    assert asyncio.run(process_one(factory, fernet))
    with factory() as session:
        stored = session.get(ResearchJob, job.id)
        assert stored.status == 'failed' and stored.error_code == 'job_expired'
        assert stored.attempts == 3


def test_queued_payload_has_only_bounded_input_and_no_plaintext_capability(jobs):
    factory, fernet = jobs
    with factory() as session:
        job = enqueue(session, fernet, url='https://fixture-business.org/', country='NG',
                      business_name='Fixture', anonymous_id='a' * 48)
        payload = json.loads(fernet.decrypt(job.payload_cipher.encode()))
        assert payload['anonymous_id'] == 'a' * 48
        assert get_job(session, job.id, 'a' * 48).id == job.id
        with pytest.raises(ResearchError):
            enqueue(session, fernet, url='http://127.0.0.1/', country='NG', business_name='Fixture', anonymous_id='a' * 48)


class EvidenceFixture:
    async def research(self, url, country='', business_name=''):
        import hashlib
        from datetime import datetime, timezone
        content = 'Offline fixture business sells shoes. Delivery terms require review.'
        source = SourceDocument(id='fixture-page', url=url, retrieved_at=datetime.now(timezone.utc),
            source_hash=hashlib.sha256(content.encode()).hexdigest(), title='Offline fixture',
            excerpt=content, content=content, provider='offline-fixture', provider_receipt_id='fixture-receipt')
        return build_report(source, country=country, business_name=business_name)


class GeminiFixture:
    name = 'gemini'
    model = 'offline-gemini-fixture'

    def __init__(self, callback=None, invalid=False):
        self.callback, self.invalid = callback, invalid

    async def complete(self, system, context):
        if self.callback:
            self.callback()
        quote = 'Invented checkout success.' if self.invalid else 'Offline fixture business sells shoes.'
        return {'claims': [{'text': quote, 'quote': quote, 'kind': 'OBSERVED',
                           'evidence_ids': [context['evidence'][0]['id']]}],
                'recommendations': [], 'limitations': ['Explicit offline model fixture.']}, {'input_tokens': 30}


def queued(jobs):
    factory, fernet = jobs
    with factory() as session:
        job = enqueue(session, fernet, url='https://fixture-business.org/', country='NG',
                      business_name='Offline fixture', anonymous_id='a' * 48)
        session.commit()
        return job.id


def test_evidence_checkpoint_is_committed_hidden_and_unclaimable_before_gemini(jobs):
    from ayo.report_storage import ReportStore
    factory, fernet = jobs
    job_id = queued(jobs)

    def inspect_checkpoint():
        with factory() as session:
            job = session.get(ResearchJob, job_id)
            record = session.get(ResearchReportRecord, job.report_id)
            assert record.status == 'PENDING_ANALYSIS' and job.claim_cipher is None
            assert session.scalar(select(ReportClaim)) is None
            with pytest.raises(IdentityError):
                ReportStore(session).accessible(record.id, anonymous_id='a' * 48)
            assert ReportStore(session).pending_preview(record.id, 'a' * 48).analysis_status == 'pending'

    assert asyncio.run(process_one(factory, fernet, EvidenceFixture,
                                  analysis_provider=GeminiFixture(inspect_checkpoint)))
    with factory() as session:
        job = session.get(ResearchJob, job_id)
        assert job.status == 'succeeded' and job.claim_cipher
        report = ResearchReport.model_validate_json(session.get(ResearchReportRecord, job.report_id).report_json)
        assert report.analysis_status == 'completed'
        assert session.scalar(select(func.count()).select_from(ReportClaim)) == 1


def test_crash_resumes_committed_evidence_without_recrawling(jobs):
    factory, fernet = jobs
    job_id = queued(jobs)

    def interrupted():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(process_one(factory, fernet, EvidenceFixture, analysis_provider=GeminiFixture(interrupted)))
    with factory() as session:
        job = session.get(ResearchJob, job_id)
        source_checkpoint = session.get(ResearchReportRecord, job.report_id).report_json
        job.lease_until = time.time() - 1
        session.commit()

    def no_recrawl():
        raise AssertionError('Existing committed evidence must be reused')

    assert asyncio.run(process_one(factory, fernet, no_recrawl, analysis_provider=GeminiFixture()))
    with factory() as session:
        job = session.get(ResearchJob, job_id)
        assert job.status == 'succeeded' and job.attempts == 2
        report = ResearchReport.model_validate_json(session.get(ResearchReportRecord, job.report_id).report_json)
        original = ResearchReport.model_validate_json(source_checkpoint)
        assert report.source_documents == original.source_documents
        assert session.scalar(select(func.count()).select_from(ResearchReportRecord)) == 1
        assert session.scalar(select(func.count()).select_from(ReportClaim)) == 1


def test_stale_model_worker_cannot_publish_or_issue_claim(jobs):
    factory, fernet = jobs
    job_id = queued(jobs)

    def other_worker_took_over():
        with factory() as session:
            job = session.get(ResearchJob, job_id)
            job.attempts += 1
            session.commit()

    assert asyncio.run(process_one(factory, fernet, EvidenceFixture,
                                  analysis_provider=GeminiFixture(other_worker_took_over)))
    with factory() as session:
        job = session.get(ResearchJob, job_id)
        assert job.status == 'running' and job.claim_cipher is None
        assert session.get(ResearchReportRecord, job.report_id).status == 'PENDING_ANALYSIS'
        assert session.scalar(select(ReportClaim)) is None


@pytest.mark.parametrize('invalid', [False, True])
def test_model_unavailable_or_rejected_never_publishes_fake_ai(jobs, monkeypatch, invalid):
    factory, fernet = jobs
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_MODEL', raising=False)
    job_id = queued(jobs)
    assert asyncio.run(process_one(factory, fernet, EvidenceFixture,
                                  analysis_provider=GeminiFixture(invalid=True) if invalid else None))
    with factory() as session:
        job = session.get(ResearchJob, job_id)
        report = ResearchReport.model_validate_json(session.get(ResearchReportRecord, job.report_id).report_json)
        assert report.status == 'PARTIAL' and report.analysis is None
        assert report.analysis_status == ('rejected' if invalid else 'unavailable')
        assert report.analysis_error_code == ('model_output_rejected' if invalid else 'model_not_configured')
        assert job.status == 'succeeded'  # Sourced partial report, explicitly no AI success.


def test_publication_cannot_swap_source_identity_after_checkpoint(jobs):
    from ayo.report_storage import ReportStore
    factory, _fernet = jobs
    report = asyncio.run(EvidenceFixture().research('https://fixture-business.org/', country='GH'))
    with factory() as session:
        row = ReportStore(session).stage_preview(report, 'a' * 48)
        session.commit()
        replaced = report.model_copy(update={'source_documents': (
            report.source_documents[0].model_copy(update={'url': 'https://different-business.org/'}),)})
        with pytest.raises(IdentityError, match='cannot replace'):
            ReportStore(session).finalize_preview(row.id, replaced, 'a' * 48)
        session.rollback()
        assert session.get(ResearchReportRecord, row.id).status == 'PENDING_ANALYSIS'
        assert session.scalar(select(ReportClaim)) is None
