"""Source-bound internal correction reviews; providers are offline fixtures."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ayo import app as mod
from ayo.identity import IdentityError
from ayo.merchant_models import Task
from ayo.models import AuditEvent, Membership, ResearchReportRecord, User
from ayo.research_workspace import ResearchWorkspace
from test_platform_flow import platform, csrf, register, verify_latest  # noqa: F401
from test_research_workspace import account, document, report, saved


def setup_report(platform):
    user_id, business_id = account(platform)
    report_id = saved(platform.factory, user_id, business_id, report())
    return user_id, business_id, report_id


def correction_data(platform, report_id, **changes):
    return {'csrf': csrf(platform.client, '/research/library/' + report_id),
            'source_id': 'exact-evidence:one', 'reason': 'outdated',
            'details': 'The listed price may have changed. Review the current product page.', **changes}


def test_correction_persists_source_provenance_and_original_report_and_export(platform):
    user_id, business_id, report_id = setup_report(platform)
    path = '/research/library/' + report_id
    original_export = platform.client.get(path + '/export').json()
    with platform.factory() as session:
        original_json = session.get(ResearchReportRecord, report_id).report_json
    data = correction_data(platform, report_id, details='Review <script>alert(1)</script>\r\nThe listing may be outdated.')
    response = platform.client.post(path + '/corrections', data=data)
    assert response.status_code == 303 and response.headers['location'] == path + '#corrections'
    with platform.factory() as session:
        task = session.scalar(select(Task))
        task_id = task.id
        assert task.source_report_id == report_id and task.business_id == business_id
        assert task.created_by == user_id and task.status == 'open'
        assert 'MERCHANT_PROVIDED_UNVERIFIED' in task.description
        assert document().source_hash in task.description and '\r\n' not in task.description
        audit = session.scalar(select(AuditEvent).where(AuditEvent.action == 'research.correction_requested'))
        details = json.loads(audit.details_json)
        assert audit.resource_id == task_id and audit.actor_user_id == user_id
        assert details['source_id'] == 'exact-evidence:one' and details['source_hash'] == document().source_hash
        assert details['evidence_reverified'] is False
        assert session.get(ResearchReportRecord, report_id).report_json == original_json
    html = platform.client.get(path).text
    assert 'Review evidence correction: Outdated information' in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    assert '<script>alert(1)</script>' not in html
    assert 'Source ID exact-evidence:one' in html and '/work#task-' + task_id in html
    assert platform.client.get(path + '/export').json() == original_export
    assert platform.client.post('/logout', data={'csrf': csrf(platform.client, '/work')}).status_code == 303
    assert platform.client.post('/login', data={'csrf': csrf(platform.client, '/login'),
        'email': 'research-owner@example.org', 'password': 'FixturePassword123!'}).status_code == 303
    assert 'Review evidence correction:' in platform.client.get(path).text
    # Completing review work never certifies a new fact, refresh or ownership.
    assert platform.client.post('/work/tasks/' + task_id, data={
        'csrf': csrf(platform.client, '/work'), 'version': '1', 'status': 'done',
        'title': 'Review evidence correction: Outdated information', 'description': 'Reviewed locally.'}).status_code == 303
    final = platform.client.get(path).text
    assert 'Work status: done' in final
    assert 'A completed task does not independently verify a correction' in final
    with platform.factory() as session:
        assert session.get(ResearchReportRecord, report_id).report_json == original_json


@pytest.mark.parametrize('field,value,status', [
    ('source_id', 'source-from-another-report', 404),
    ('reason', 'verified', 400), ('details', 'short', 400),
    ('details', 'x' * 1501, 400), ('details', 'Invalid control\x00character', 400),
])
def test_invalid_correction_leaves_no_task_or_audit(platform, field, value, status):
    user_id, business_id, report_id = setup_report(platform)
    # An accessible different report still cannot donate evidence to this report.
    saved(platform.factory, user_id, business_id, report(document(source_id='source-from-another-report')))
    response = platform.client.post('/research/library/' + report_id + '/corrections',
        data=correction_data(platform, report_id, **{field: value}))
    assert response.status_code == status
    with platform.factory() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 0
        assert session.scalar(select(AuditEvent).where(AuditEvent.action == 'research.correction_requested')) is None


@pytest.mark.parametrize('role,allowed', [('owner', True), ('admin', True), ('editor', True), ('analyst', False)])
def test_correction_role_enforcement_and_form_visibility(platform, role, allowed):
    user_id, business_id, report_id = setup_report(platform)
    with platform.factory() as session:
        session.get(Membership, (business_id, user_id)).role = role
        session.commit()
    path = '/research/library/' + report_id
    assert ('id="correction-details"' in platform.client.get(path).text) == allowed
    response = platform.client.post(path + '/corrections', data=correction_data(platform, report_id))
    assert response.status_code == (303 if allowed else 403)


def test_correction_csrf_unverified_and_foreign_workspace_are_rejected(platform):
    user_id, business_id, report_id = setup_report(platform)
    path = '/research/library/' + report_id
    assert platform.client.post(path + '/corrections', data=correction_data(platform, report_id, csrf='wrong')).status_code == 403
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as other:
        register(other, 'other-reviewer@example.org')
        assert verify_latest(other, platform.factory).status_code == 303
        assert other.get(path).status_code == 404
        assert other.post(path + '/corrections', data={**correction_data(platform, report_id),
            'csrf': csrf(other, '/work')}).status_code == 404
    with platform.factory() as session:
        session.get(User, user_id).email_verified_at = None
        session.commit()
    assert 'id="correction-details"' not in platform.client.get(path).text
    assert platform.client.post(path + '/corrections', data=correction_data(platform, report_id)).status_code == 403
    with platform.factory() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 0


def test_correction_transaction_rollback_and_account_removal(platform):
    user_id, business_id, report_id = setup_report(platform)
    with platform.factory() as session:
        ResearchWorkspace(session).request_correction(user_id, business_id, report_id,
            source_id='exact-evidence:one', reason='wrong_business', details='This page may describe a different business.')
        session.rollback()
    with platform.factory() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 0
        assert session.scalar(select(AuditEvent).where(AuditEvent.action == 'research.correction_requested')) is None
    assert platform.client.post('/research/library/' + report_id + '/corrections',
        data=correction_data(platform, report_id)).status_code == 303
    from ayo.account_deletion import remove_account
    with platform.factory() as session:
        remove_account(session, user_id, 'FixturePassword123!', 'DELETE')
        session.commit()
    with platform.factory() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 0
        assert session.get(ResearchReportRecord, report_id) is None
        with pytest.raises(IdentityError) as error:
            ResearchWorkspace(session).correction_requests(user_id, business_id, report_id)
        assert error.value.status_code == 403
