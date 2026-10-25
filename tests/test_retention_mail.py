import json
import time
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from ayo.identity import IdentityService
from ayo.mailer import deliver_one, queue_identity_mail
from ayo.models import Base, FoundingGrant, MailOutbox, ResearchReportRecord
from ayo.retention import cleanup_expired


@pytest.fixture
def store(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'retention.db'))
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


def test_cleanup_preserves_claimed_reports_and_permanent_founder_entitlement(store):
    now = time.time()
    account = IdentityService(store).register('retention@example.org', 'FixturePassword123!', 'Fixture', 'GH')
    store.add_all([
        ResearchReportRecord(id='expired', title='Expired fixture', status='PARTIAL', report_json='{}', created_at=now-90000, expires_at=now-1),
        ResearchReportRecord(id='saved', title='Saved fixture', status='PARTIAL', report_json='{}', business_id=account.business.id,
                             owner_user_id=account.user.id, created_at=now-90000, expires_at=None),
    ])
    store.commit()
    assert cleanup_expired(store, now) >= 1
    store.commit()
    assert store.get(ResearchReportRecord, 'expired') is None
    assert store.get(ResearchReportRecord, 'saved') is not None
    assert store.scalar(select(FoundingGrant)).user_id == account.user.id


def test_identity_mail_is_encrypted_and_supersedes_old_tickets_without_sending(store, monkeypatch):
    account = IdentityService(store).register('mail@example.org', 'FixturePassword123!', 'Fixture', 'NG')
    fernet = Fernet(Fernet.generate_key())
    queue_identity_mail(store, fernet, account.user, 'verify_email', account.verification_token, 'https://app.example.org')
    queue_identity_mail(store, fernet, account.user, 'verify_email', 'b' * 48, 'https://app.example.org')
    store.commit()
    rows = store.scalars(select(MailOutbox).order_by(MailOutbox.id)).all()
    assert [row.status for row in rows] == ['superseded', 'pending']
    assert account.verification_token not in rows[0].payload_cipher
    assert 'token=' in json.loads(fernet.decrypt(rows[1].payload_cipher.encode()))['url']
    monkeypatch.delenv('AYO_MAIL_SEND_AUTHORIZED', raising=False)
    with pytest.raises(RuntimeError, match='not been authorized'):
        deliver_one(store, fernet)
