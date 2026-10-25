import asyncio
import json
import time

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from ayo.identity import IdentityError
from ayo.jobs import enqueue, get_job, process_one
from ayo.models import Base, ResearchJob, ResearchReportRecord
from ayo.research import ResearchError


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
