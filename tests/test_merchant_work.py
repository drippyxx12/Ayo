"""Real persistent profile/work HTTP flows; no source/model/provider execution."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError

from ayo import app as mod
from ayo.identity import IdentityError, IdentityService
from ayo.merchant_models import BusinessProfile, Task
from ayo.merchant_work import ProfileService, TaskService
from ayo.models import AuditEvent, Business, Lead, Membership, ResearchReportRecord, User
from test_platform_flow import platform, csrf, register, verify_latest


def owner(platform, *, verified=True):
    register(platform.client, 'work-owner@example.org')
    if verified:
        assert verify_latest(platform.client, platform.factory).status_code == 303
    with platform.factory() as session:
        user = session.scalar(select(User))
        business = session.scalar(select(Business))
        return user.id, business.id


def profile_data(client, **overrides):
    return {'csrf': csrf(client, '/business'), 'version': '0', 'business_name': 'Accra textile studio',
            'country': 'GH', 'offer': 'Locally made cotton clothing', 'products': 'Shirts and dresses',
            'audience': 'Independent retailers', 'location': 'Accra', 'goals': 'Improve delivery information', **overrides}


def task_data(client, **overrides):
    return {'csrf': csrf(client, '/work'), 'title': 'Review delivery information',
            'description': 'Check the policy with the team.', 'due_date': '2026-11-30', **overrides}


def test_profile_persists_without_site_reopens_and_updates_market_atomically(platform):
    user_id, business_id = owner(platform)
    client = platform.client
    result = client.post('/business', data=profile_data(client))
    assert result.status_code == 303
    page = client.get('/business')
    assert 'Locally made cotton clothing' in page.text
    assert 'OWNER_PROVIDED_UNVERIFIED' in page.text and 'does not prove' in page.text
    assert '/static/merchant-work.css' in page.text
    with platform.factory() as session:
        profile = session.get(BusinessProfile, business_id)
        assert (profile.offer, profile.goals, profile.version, profile.updated_by) == (
            'Locally made cotton clothing', 'Improve delivery information', 1, user_id)
        assert session.get(Business, business_id).currency == 'GHS'
    result = client.post('/business', data=profile_data(client, version='1', country='NG', location='Lagos'))
    assert result.status_code == 303
    with platform.factory() as session:
        business = session.get(Business, business_id)
        assert (business.country, business.currency, business.timezone) == ('NG', 'NGN', 'Africa/Lagos')
        audit = session.scalar(select(AuditEvent).where(AuditEvent.action == 'business.profile_updated').order_by(AuditEvent.id.desc()))
        details = json.loads(audit.details_json)
        assert audit.actor_user_id == user_id and audit.business_id == business_id
        assert details['ownership_verified'] is False and details['to_version'] == 2
    assert client.post('/logout', data={'csrf': csrf(client, '/business')}).status_code == 303
    login = client.post('/login', data={'csrf': csrf(client, '/login'), 'email': 'work-owner@example.org', 'password': 'FixturePassword123!'})
    assert login.status_code == 303
    assert 'Lagos' in client.get('/business').text


def test_tasks_persist_filter_edit_due_date_clear_and_completion_audit(platform):
    user_id, business_id = owner(platform)
    client = platform.client
    assert client.post('/work/tasks', data=task_data(client)).status_code == 303
    with platform.factory() as session:
        task = session.scalar(select(Task))
        task_id = task.id
        assert task.business_id == business_id and task.created_by == user_id
        assert task.status == 'open' and task.due_date == date(2026, 11, 30) and task.version == 1
    update = task_data(client, version='1', title='Review delivery and returns', status='in_progress')
    assert client.post('/work/tasks/' + task_id, data=update).status_code == 303
    assert 'Review delivery and returns' in client.get('/work?status=in_progress').text
    assert 'task-' + task_id not in client.get('/work?status=open').text
    assert client.post('/work/tasks/' + task_id, data=task_data(client, version='2', status='done', due_date='')).status_code == 303
    assert 'No external action, reply or sale is verified' in client.get('/work').text
    with platform.factory() as session:
        task = session.get(Task, task_id)
        assert task.status == 'done' and task.due_date is None and task.version == 3
        audit = session.scalar(select(AuditEvent).where(AuditEvent.action == 'task.updated').order_by(AuditEvent.id.desc()))
        detail = json.loads(audit.details_json)
        assert detail['completion_classification'] == 'MERCHANT_RECORDED_TASK_COMPLETION'
        assert detail['external_outcome_verified'] is False
        assert detail['from_status'] == 'in_progress' and audit.resource_id == task_id
    assert client.post('/work/tasks/' + task_id, data=task_data(client, version='3', status='cancelled')).status_code == 303
    with platform.factory() as session:
        assert session.get(Task, task_id).status == 'cancelled'


def test_source_opportunity_prefill_and_followup_use_explicit_same_workspace_links(platform):
    user_id, business_id = owner(platform)
    client = platform.client
    with platform.factory() as session:
        report = ResearchReportRecord(business_id=business_id, owner_user_id=user_id, title='Fixture business report',
            status='COMPLETE', country='GH', report_json=json.dumps({'opportunities': [
                {'title': 'Clarify delivery policy', 'description': 'Review the public delivery policy.'}]}))
        lead = Lead(business_id=business_id, name='Fixture retailer', url='https://fixture-retailer.org', country='GH',
                    fit_reason='Offline fixture', evidence_json='{}')
        session.add_all([report, lead])
        session.commit()
        report_id, lead_id = report.id, lead.id
    page = client.get(f'/work?source_report_id={report_id}&opportunity=0')
    assert page.status_code == 200 and 'value="Clarify delivery policy"' in page.text
    assert f'name="source_report_id" value="{report_id}"' in page.text
    result = client.post('/work/tasks', data=task_data(client, title='Clarify delivery policy', source_report_id=report_id))
    assert result.status_code == 303
    assert client.get(f'/work?source_report_id={report_id}&opportunity=-1').status_code == 404
    assert client.get(f'/work?source_report_id={report_id}&opportunity=1000').status_code == 404
    assert 'does not contact this prospect' in client.get('/work?source_lead_id=' + lead_id).text
    with platform.factory() as session:
        followup = TaskService(session).create(user_id, business_id, title='Review retailer follow-up', source_lead_id=lead_id)
        session.commit()
        assert followup.source_lead_id == lead_id
        assert session.scalar(select(Task).where(Task.source_report_id == report_id)) is not None
        assert session.get(Lead, lead_id).status == 'discovered'


def test_foreign_work_profile_tasks_and_sources_remain_unavailable(platform):
    user_id, business_id = owner(platform)
    client = platform.client
    assert client.post('/business', data=profile_data(client)).status_code == 303
    assert client.post('/work/tasks', data=task_data(client)).status_code == 303
    with platform.factory() as session:
        task_id = session.scalar(select(Task.id))
        report = ResearchReportRecord(business_id=business_id, owner_user_id=user_id, title='Secret fixture report',
            status='COMPLETE', country='GH', report_json='{}')
        lead = Lead(business_id=business_id, name='Secret fixture prospect', url='https://secret-fixture.org', country='GH',
                    fit_reason='fixture', evidence_json='{}')
        session.add_all([report, lead])
        session.commit()
        report_id, lead_id = report.id, lead.id
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as other:
        register(other, 'work-other@example.org')
        assert verify_latest(other, platform.factory).status_code == 303
        assert 'Locally made cotton clothing' not in other.get('/business').text
        assert 'Review delivery information' not in other.get('/work').text
        assert other.post('/work/tasks/' + task_id, data=task_data(other, version='1', status='done')).status_code == 404
        assert other.get('/work?source_report_id=' + report_id).status_code == 404
        assert other.get('/work?source_lead_id=' + lead_id).status_code == 404
        assert other.post('/work/tasks', data=task_data(other, source_report_id=report_id)).status_code == 404
        assert other.post('/work/tasks', data=task_data(other, source_lead_id=lead_id)).status_code == 404
        with platform.factory() as session:
            other_user = session.scalar(select(User).where(User.email == 'work-other@example.org'))
            with pytest.raises(IdentityError) as exc:
                ProfileService(session).save(other_user.id, business_id, name='Attack', country='GH')
            assert exc.value.status_code == 403
    with platform.factory() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 1
        assert session.get(Task, task_id).status == 'open'
        assert session.get(BusinessProfile, business_id).offer == 'Locally made cotton clothing'


@pytest.mark.parametrize('role,profile_allowed,task_allowed', [
    ('owner', True, True), ('admin', True, True), ('editor', False, True), ('analyst', False, False)])
def test_verified_roles_enforced_by_server(platform, role, profile_allowed, task_allowed):
    user_id, business_id = owner(platform)
    client = platform.client
    with platform.factory() as session:
        session.get(Membership, (business_id, user_id)).role = role
        session.commit()
    result = client.post('/business', data=profile_data(client))
    assert result.status_code == (303 if profile_allowed else 403)
    result = client.post('/work/tasks', data=task_data(client))
    assert result.status_code == (303 if task_allowed else 403)
    with platform.factory() as session:
        assert session.scalar(select(func.count()).select_from(BusinessProfile)) == int(profile_allowed)
        assert session.scalar(select(func.count()).select_from(Task)) == int(task_allowed)


def test_unverified_owner_csrf_and_origin_cannot_write(platform):
    owner(platform, verified=False)
    client = platform.client
    assert client.get('/business').status_code == client.get('/work').status_code == 200
    assert client.post('/business', data=profile_data(client)).status_code == 403
    assert client.post('/work/tasks', data=task_data(client)).status_code == 403
    assert verify_latest(client, platform.factory).status_code == 303
    assert client.post('/business', data=profile_data(client, csrf='bad')).status_code == 403
    assert client.post('/work/tasks', data=task_data(client, csrf='bad')).status_code == 403
    assert client.post('/work/tasks', data=task_data(client), headers={'origin': 'https://evil.example'}).status_code == 403
    with platform.factory() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 0
        assert session.scalar(select(func.count()).select_from(BusinessProfile)) == 0


@pytest.mark.parametrize('overrides', [
    {'title': '   '}, {'title': 'x' * 201}, {'description': 'x' * 5001},
    {'due_date': '2026-02-30'}, {'due_date': '01/12/2026'}, {'due_date': '2026-1-1'}, {'title': 'Bad\x01title'}])
def test_invalid_task_inputs_do_not_persist_or_audit(platform, overrides):
    owner(platform)
    client = platform.client
    result = client.post('/work/tasks', data=task_data(client, **overrides))
    assert result.status_code == 400
    assert 'role="alert"' in result.text
    with platform.factory() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 0
        assert session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == 'task.created')) == 0


@pytest.mark.parametrize('overrides', [
    {'business_name': ' '}, {'business_name': 'x' * 161}, {'country': 'US'},
    {'offer': 'x' * 3001}, {'location': 'x' * 251}])
def test_invalid_profile_preserves_existing_market_and_identity(platform, overrides):
    _, business_id = owner(platform)
    client = platform.client
    assert client.post('/business', data=profile_data(client, **overrides)).status_code == 400
    with platform.factory() as session:
        business = session.get(Business, business_id)
        assert (business.name, business.country, business.currency) == ('Fixture merchant', 'GH', 'GHS')
        assert session.get(BusinessProfile, business_id) is None


def test_stale_and_invalid_task_updates_preserve_latest_record(platform):
    _, business_id = owner(platform)
    client = platform.client
    assert client.post('/work/tasks', data=task_data(client)).status_code == 303
    with platform.factory() as session:
        task_id = session.scalar(select(Task.id))
    assert client.post('/work/tasks/' + task_id, data=task_data(client, version='1', status='in_progress', title='Latest work')).status_code == 303
    stale = client.post('/work/tasks/' + task_id, data=task_data(client, version='1', status='done', title='Lost update'))
    assert stale.status_code == 409 and 'This task changed' in stale.text
    assert client.post('/work/tasks/' + task_id, data=task_data(client, version='2', status='sent')).status_code == 400
    assert client.post('/work/tasks/' + task_id, data=task_data(client, version=str(2**63), status='done')).status_code == 409
    with platform.factory() as session:
        row = session.get(Task, task_id)
        assert (row.business_id, row.title, row.status, row.version) == (business_id, 'Latest work', 'in_progress', 2)
        assert session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == 'task.updated')) == 1


def test_stale_profile_does_not_overwrite_current_context_or_market(platform):
    _, business_id = owner(platform)
    client = platform.client
    assert client.post('/business', data=profile_data(client)).status_code == 303
    assert client.post('/business', data=profile_data(client, version='1', country='NG', offer='Latest offer')).status_code == 303
    stale = client.post('/business', data=profile_data(client, version='1', country='GH', offer='Stale offer'))
    assert stale.status_code == 409
    assert 'Latest offer' in stale.text and 'Stale offer' not in stale.text
    assert 'name="version" value="2"' in stale.text
    assert client.post('/business', data=profile_data(client, version=str(2**63))).status_code == 409
    with platform.factory() as session:
        assert session.get(BusinessProfile, business_id).offer == 'Latest offer'
        assert session.get(Business, business_id).currency == 'NGN'


def test_concurrent_task_edits_have_one_winner_and_one_conflict(platform):
    user_id, business_id = owner(platform)
    with platform.factory() as session:
        task = TaskService(session).create(user_id, business_id, title='Concurrent review')
        session.commit()
        task_id = task.id
    barrier = Barrier(2)

    def change(title):
        with platform.factory() as session:
            row = session.get(Task, task_id)
            assert row.version == 1
            barrier.wait(timeout=10)
            try:
                TaskService(session).update(user_id, business_id, task_id, version=1, title=title)
                session.commit()
                return 'saved'
            except IdentityError as exc:
                session.rollback()
                return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(change, ['First change', 'Second change']))
    assert sorted(results) == ['saved', 'stale_task']
    with platform.factory() as session:
        assert session.get(Task, task_id).version == 2
        assert session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == 'task.updated')) == 1


def test_caller_rollback_reverts_first_profile_identity_market_and_task(platform):
    user_id, business_id = owner(platform)
    with platform.factory() as session:
        ProfileService(session).save(user_id, business_id, name='Uncommitted name', country='NG', offer='Uncommitted offer')
        TaskService(session).create(user_id, business_id, title='Uncommitted work')
        session.rollback()
    with platform.factory() as session:
        business = session.get(Business, business_id)
        assert (business.name, business.country, business.currency) == ('Fixture merchant', 'GH', 'GHS')
        assert session.get(BusinessProfile, business_id) is None
        assert session.scalar(select(func.count()).select_from(Task)) == 0
        assert session.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.action.in_(['business.profile_updated', 'task.created']))) == 0


def test_untrusted_text_escaped_and_not_used_as_markup(platform):
    owner(platform)
    client = platform.client
    attack = '<img src=x onerror=alert(1)>'
    assert client.post('/business', data=profile_data(client, business_name=attack, offer=attack, goals='</textarea><script>alert(1)</script>')).status_code == 303
    page = client.get('/business')
    assert attack not in page.text and '&lt;img' in page.text and '&lt;script&gt;' in page.text
    assert client.post('/work/tasks', data=task_data(client, title=attack, description='</textarea><script>alert(1)</script>')).status_code == 303
    work = client.get('/work')
    assert attack not in work.text and '<script>' not in work.text and '&lt;script&gt;' in work.text
    assert work.headers['cache-control'] == 'private, no-store'


def test_schema_enforces_task_states_versions_profile_source_and_workspace_cascade(platform):
    user_id, business_id = owner(platform)
    with platform.factory() as session:
        if session.bind.dialect.name == 'sqlite':
            session.execute(text('PRAGMA foreign_keys=ON'))
        ProfileService(session).save(user_id, business_id, name='Fixture merchant', country='GH')
        row = TaskService(session).create(user_id, business_id, title='Stored work')
        session.commit()
        task_id = row.id
        for statement in [
            update(Task).values(status='sent'), update(Task).values(version=0),
            update(BusinessProfile).values(source_classification='VERIFIED'),
            update(BusinessProfile).values(version=0),
        ]:
            with pytest.raises(IntegrityError):
                with session.begin_nested():
                    session.execute(statement)
        session.execute(delete(Business).where(Business.id == business_id))
        session.commit()
    with platform.factory() as session:
        assert session.get(Task, task_id) is None and session.get(BusinessProfile, business_id) is None
