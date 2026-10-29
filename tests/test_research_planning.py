"""Actual SQLite/PostgreSQL persistence; source/model data is offline."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import re
import threading

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

from ayo import app as mod
from ayo.identity import IdentityError, IdentityService
from ayo.merchant_models import Task
from ayo.models import AuditEvent, Membership, ResearchReportRecord, User
from ayo.research_planning import ResearchPlanning
from test_platform_flow import platform, csrf, register, verify_latest  # noqa: F401
from test_research_workspace import account, saved, report


def setup(platform):
    user, business = account(platform)
    record = saved(platform.factory, user, business, report(ai=True))
    return user, business, record


def reviewed(platform, user, business, record):
    with platform.factory() as session:
        return ResearchPlanning(session).review(user, business, record)


def data(platform, user, business, record, **changes):
    plan = reviewed(platform, user, business, record)
    return {'csrf': csrf(platform.client, '/research/library/' + record + '/plan'),
        'reviewed': 'true', 'report_hash': plan['report_hash'],
        'selected': [plan['choices'][0]['key']], **changes}


def test_reviewed_plan_persists_source_linked_work_replay_relogin_and_original(platform, monkeypatch):
    user, business, record = setup(platform)
    original = platform.client.get('/research/library/' + record + '/export').json()
    plan = reviewed(platform, user, business, record)
    assert plan['choices'][0]['origin'] == 'AI proposal'
    assert plan['can_edit'] and plan['choices'][0]['sources'][0].source_hash

    def forbidden(*_args, **_kwargs):
        raise AssertionError('Planning cannot call a source or model provider')
    monkeypatch.setattr(mod.app.state, 'research_factory', forbidden)
    path = '/research/library/' + record + '/plan'
    payload = data(platform, user, business, record)
    for _ in range(2):
        response = platform.client.post(path, data=payload)
        assert response.status_code == 303, response.text
    with platform.factory() as session:
        tasks = session.scalars(select(Task)).all()
        assert len(tasks) == 1
        task = tasks[0]
        task_id = task.id
        assert task.business_id == business and task.source_report_id == record
        assert task.status == 'open' and 'No external action has been performed' in task.description
        assert 'exact-evidence:one' in task.description and 'SHA-256:' in task.description
        assert len(task.description) <= 5000
        assert len(session.scalars(select(AuditEvent).where(AuditEvent.action == 'research.plan_created')).all()) == 1
    assert platform.client.get('/research/library/' + record + '/export').json() == original
    page = platform.client.get(path)
    assert '/work#task-' + task_id in page.text and 'Why this step is here' in page.text
    platform.client.post('/logout', data={'csrf': csrf(platform.client, '/work')})
    login = platform.client.post('/login', data={'csrf': csrf(platform.client, '/login'),
        'email': 'research-owner@example.org', 'password': 'FixturePassword123!'})
    assert login.status_code == 303
    assert '/work#task-' + task_id in platform.client.get(path).text
    assert task.title in platform.client.get('/work').text


@pytest.mark.parametrize('changes', [
    {'reviewed': 'false'}, {'selected': []}, {'selected': ['f' * 24]},
    {'selected': ['bad']}, {'report_hash': 'f' * 64}, {'report_hash': ''},
])
def test_invalid_or_stale_plan_creates_no_work(platform, changes):
    user, business, record = setup(platform)
    response = platform.client.post('/research/library/' + record + '/plan',
        data=data(platform, user, business, record, **changes))
    assert response.status_code in {400, 409}
    with platform.factory() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 0


def test_changed_report_and_duplicate_selection_are_rejected(platform):
    user, business, record = setup(platform)
    plan = reviewed(platform, user, business, record)
    with platform.factory() as session:
        row = session.get(ResearchReportRecord, record)
        row.report_json = row.report_json.replace('Offline Fixture Shop', 'Changed Fixture Shop')
        session.commit()
    with platform.factory() as session:
        with pytest.raises(IdentityError, match='saved evidence changed'):
            ResearchPlanning(session).create(user, business, record, report_hash=plan['report_hash'],
                selected=[plan['choices'][0]['key']], reviewed=True)
        session.rollback()
    fresh = reviewed(platform, user, business, record)
    with platform.factory() as session:
        with pytest.raises(IdentityError, match='one and eight'):
            ResearchPlanning(session).create(user, business, record, report_hash=fresh['report_hash'],
                selected=[fresh['choices'][0]['key']] * 2, reviewed=True)


def test_roles_csrf_foreign_workspace_and_pending_evidence_fail_closed(platform):
    user, business, record = setup(platform)
    path = '/research/library/' + record + '/plan'
    payload = data(platform, user, business, record)
    assert platform.client.post(path, data={**payload, 'csrf': 'wrong'}).status_code == 403
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as stranger:
        assert stranger.get(path).status_code in {303, 401}
        register(stranger, 'foreign-plan@example.org')
        verify_latest(stranger, platform.factory)
        assert stranger.get(path).status_code == 404
    with platform.factory() as session:
        member = session.scalar(select(Membership).where(Membership.user_id == user))
        member.role = 'analyst'
        session.commit()
    assert platform.client.get(path).status_code == 200
    assert platform.client.post(path, data=payload).status_code == 403
    with platform.factory() as session:
        member = session.scalar(select(Membership).where(Membership.user_id == user))
        member.role = 'owner'
        session.get(User, user).email_verified_at = None
        session.commit()
    assert platform.client.post(path, data=payload).status_code == 403
    with platform.factory() as session:
        session.get(ResearchReportRecord, record).status = 'PENDING_ANALYSIS'
        session.commit()
    assert platform.client.get(path).status_code == 404


def test_two_team_members_concurrently_create_one_task_and_audit(platform):
    user, business, record = setup(platform)
    with platform.factory() as session:
        registration = IdentityService(session).register('plan-editor@example.org', 'FixturePassword123!',
                                                         'Second fixture', 'GH')
        editor = registration.user.id
        registration.user.email_verified_at = 100
        session.add(Membership(user_id=editor, business_id=business, role='editor'))
        session.commit()
    plan = reviewed(platform, user, business, record)
    barrier = threading.Barrier(2)

    def submit(actor):
        with platform.factory() as session:
            barrier.wait(timeout=5)
            ids = ResearchPlanning(session).create(actor, business, record,
                report_hash=plan['report_hash'], selected=[plan['choices'][0]['key']], reviewed=True)
            session.commit()
            return ids
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit, actor) for actor in (user, editor)]
        assert futures[0].result(timeout=15) == futures[1].result(timeout=15)
    with platform.factory() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 1
        assert len(session.scalars(select(AuditEvent).where(AuditEvent.action == 'research.plan_created')).all()) == 1


def test_no_recommendations_means_empty_plan_without_invented_tasks(platform):
    user, business = account(platform)
    value = report()
    value = value.model_copy(update={'opportunities': ()})
    record = saved(platform.factory, user, business, value)
    plan = reviewed(platform, user, business, record)
    assert not plan['choices']
    response = platform.client.get('/research/library/' + record + '/plan')
    assert 'More evidence before a plan.' in response.text
    assert 'name="selected"' not in response.text
