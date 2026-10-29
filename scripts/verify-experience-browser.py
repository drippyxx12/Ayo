"""Research-to-work browser story and loopback preview process supervision.

All source/model/account/mail data is explicitly synthetic; real PostgreSQL.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import signal
import subprocess

import httpx
from pathlib import Path
import secrets
import socket
import sys
import threading
import time
from urllib.parse import urlsplit

from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def verify_runner(origin, output):
    """Start actual API+worker children against the completed isolated schema."""
    env = dict(os.environ)
    env['AYO_RESEARCH_SOURCE'] = 'direct_public_web'
    # The fixture server owns its own port. Reserve another for the supervisor.
    probe = socket.socket()
    probe.bind(('127.0.0.1', 0))
    port = probe.getsockname()[1]
    probe.close()
    env['APP_ORIGIN'] = 'http://127.0.0.1:' + str(port)
    command = [sys.executable, str(ROOT / 'scripts/run-workspace-preview.py'), '--port', str(port)]
    check = subprocess.run(command + ['--check'], cwd=ROOT, env=env, capture_output=True, timeout=15)
    assert check.returncode == 0, check.stderr.decode()[:500]
    log = output / 'runner.log'
    with log.open('w') as stream:
        child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=stream)
        pids = []
        try:
            deadline = time.monotonic() + 20
            with httpx.Client(trust_env=False, timeout=1) as client:
                while time.monotonic() < deadline:
                    assert child.poll() is None, log.read_text()[-1000:]
                    try:
                        if client.get(env['APP_ORIGIN'] + '/').status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.1)
                else:
                    raise AssertionError('Preview web process did not become ready.')
            # Some managed kernels omit /proc/PID/task/PID/children.
            pids = sorted(int(value) for value in subprocess.check_output(
                ['ps', '-o', 'pid=', '--ppid', str(child.pid)], text=True).split())
            assert len(pids) == 2
            # The runner launches web then worker. Ending either must end its peer.
            os.kill(pids[-1], signal.SIGTERM)
            assert child.wait(timeout=15) == 1
            assert all(not Path('/proc/' + str(pid)).exists() for pid in pids)
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=15)
    return {'configuration_and_postgresql_head': True, 'actual_web_and_worker_processes': True,
            'worker_exit_stops_web_companion': True, 'no_orphan_processes': True,
            'no_migration_or_seed': True}


def main():
    url = make_url(os.environ['AYO_TEST_POSTGRES_URL'])
    if url.get_backend_name() != 'postgresql' or url.host not in {'localhost', '127.0.0.1', '::1'}:
        raise RuntimeError('Only a loopback disposable PostgreSQL schema is supported.')
    schema = 'refresh_browser_' + secrets.token_hex(8)
    admin = create_engine(url)
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(128)
    listener.setblocking(False)
    origin = 'http://127.0.0.1:' + str(listener.getsockname()[1])
    server = thread = None
    created = False
    checks, blocked_requests, page_errors = [], [], []
    output = Path(os.environ.get('AYO_BROWSER_OUTPUT_DIR', str(ROOT.parent / 'scratch/ayo-experience-browser')))
    output.mkdir(parents=True, exist_ok=True)
    runner = None
    calls = {'fixture_sources': 0, 'fixture_models': 0}
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        created = True
        for name in ('GEMINI_API_KEY', 'FIRECRAWL_API_KEY', 'RESEND_API_KEY', 'ANTHROPIC_API_KEY',
                     'SHOPIFY_CLIENT_ID', 'SHOPIFY_CLIENT_SECRET'):
            os.environ.pop(name, None)
        os.environ.update(ENVIRONMENT='development', SESSION_SECRET=secrets.token_urlsafe(48),
            TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(), APP_ORIGIN=origin,
            DATABASE_URL=url.update_query_dict({'options': '-csearch_path=' + schema}).render_as_string(hide_password=False),
            AYO_PROVIDER_SPEND_AUTHORIZED='0', AYO_MAIL_SEND_AUTHORIZED='0', AYO_GEMINI_FREE_CALLS_AUTHORIZED='0',
            AYO_WIKIDATA_READ_AUTHORIZED='0', AYO_AI_DATA_POLICY='public_only_reviewed', AYO_PREVIEW_MODE='0',
            AYO_ON_DEMAND_RESEARCH='0', AYO_ON_DEMAND_GEMINI_AUTHORIZED='0')
        with admin.connect() as connection:
            connection.exec_driver_sql('SET search_path TO "' + schema + '"')
            connection.commit()
            config = Config(str(ROOT / 'alembic.ini'))
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
            connection.commit()
        from ayo import app as mod
        from ayo.identity import IdentityService
        from ayo.jobs import process_one
        from ayo.models import ResearchJob, ResearchReportRecord
        from ayo.merchant_models import Task
        from ayo.report_storage import ReportStore
        from ayo.research import SourceDocument, ResearchService, build_report, PublicProduct

        def evidence(target, label):
            text = label + ' synthetic public fixture: Synthetic fixture tote listed for GHS 85.00. Delivery information. No real merchant or sales.'
            return SourceDocument(id='fixture-' + hashlib.sha256(text.encode()).hexdigest()[:16], url=target,
                retrieved_at=datetime.now(timezone.utc), source_hash=hashlib.sha256(text.encode()).hexdigest(),
                excerpt=text, content=text, title='Offline browser fixture', provider='offline-browser-fixture',
                provider_receipt_id='fixture-only', html_source_hash=hashlib.sha256(('synthetic markup ' + text).encode()).hexdigest(),
                product_observations=(PublicProduct(name='Synthetic fixture tote', listed_price='85.00', currency='GHS'),))

        class Provider:
            async def fetch(self, target, country=''):
                calls['fixture_sources'] += 1
                return evidence(target, 'Refreshed')

        class Gemini:
            name, model = 'gemini', 'offline-browser-refresh-fixture'

            async def complete(self, _system, context):
                calls['fixture_models'] += 1
                return {'claims': [{'text': 'The public product description may benefit from merchant review.',
                    'kind': 'INFERRED', 'quote': '', 'evidence_ids': [context['evidence'][0]['id']]}],
                    'recommendations': [{'text': 'Review the retained delivery information with the business owner.',
                        'evidence_ids': [context['evidence'][0]['id']], 'permission_required': 'merchant_review'}],
                    'limitations': ['Explicit offline model fixture.']}, {'totalTokenCount': 10}

        server = uvicorn.Server(uvicorn.Config(mod.app, log_level='error', access_log=False))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        deadline = time.monotonic() + 15
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        password = 'OfflineRefreshBrowserPassword123!'
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
            try:
                for width in (390, 768, 1440):
                    with mod.DbSession() as session:
                        registration = IdentityService(session).register('refresh-' + str(width) + '@example.org',
                            password, 'Synthetic refresh studio', 'GH')
                        registration.user.email_verified_at = time.time()  # Explicit fixture verification; no mail delivery.
                        original = build_report(evidence('https://offline-browser-fixture.org/', 'Original'), country='GH')
                        store = ReportStore(session)
                        anonymous = secrets.token_urlsafe(32)
                        row, claim = store.save_preview(original, anonymous)
                        store.claim(claim, anonymous, registration.user.id, registration.business.id)
                        session.commit()
                        original_id, original_json = row.id, row.report_json
                        jobs_before = session.scalar(select(func.count()).select_from(ResearchJob))
                    context = browser.new_context(viewport={'width': width, 'height': 950})

                    def restrict(route):
                        if urlsplit(route.request.url).hostname != '127.0.0.1':
                            blocked_requests.append('non-loopback request')
                            route.abort()
                        else:
                            route.continue_()

                    context.route('**/*', restrict)
                    page = context.new_page()
                    page.on('pageerror', lambda error: page_errors.append(str(error)))
                    try:
                        def login():
                            page.goto(origin + '/login', wait_until='networkidle')
                            page.locator('input[name=email]').fill('refresh-' + str(width) + '@example.org')
                            page.locator('input[name=password]').fill(password)
                            page.locator('form[action="/login"] button').click()
                            page.wait_for_url('**/dashboard')

                        page.goto(origin, wait_until='networkidle')
                        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
                        assert page.locator('.research-path .ayo-icon').count() == 3
                        assert page.locator('.discovery-panel').evaluate("e => getComputedStyle(e).opacity") == '1'
                        summary = page.locator('.discovery-owner > summary')
                        assert summary.evaluate("e => getComputedStyle(e).listStyleType") == 'none'
                        summary.focus()
                        summary.press('Enter')
                        assert page.locator('.discovery-owner').get_attribute('open') is not None
                        summary.press('Enter')
                        page.emulate_media(reduced_motion='reduce')
                        assert page.locator('.discovery-intro').evaluate("e => getComputedStyle(e).animationName") == 'none'
                        page.emulate_media(reduced_motion='no-preference')
                        page.screenshot(path=str(output / ('landing-' + str(width) + '.png')), full_page=True)
                        login()
                        page.screenshot(path=str(output / ('dashboard-' + str(width) + '.png')), full_page=True)
                        path = '/research/library/' + original_id
                        assert page.goto(origin + path, wait_until='networkidle').status == 200
                        page.get_by_role('link', name='Review a new source refresh').click()
                        page.wait_for_load_state('networkidle')
                        checkbox = page.get_by_label('I reviewed this scope', exact=False)
                        assert checkbox.evaluate('element => element.required') and not checkbox.is_checked()
                        box = checkbox.bounding_box()
                        assert box and 14 <= box['width'] <= 24 and 14 <= box['height'] <= 24
                        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
                        page.get_by_role('button', name='Start reviewed refresh').click()
                        with mod.DbSession() as session:
                            assert session.scalar(select(func.count()).select_from(ResearchJob)) == jobs_before
                        checkbox.check()
                        with page.expect_response(lambda response: response.request.method == 'POST'
                                                  and urlsplit(response.url).path == path + '/refresh') as sent:
                            page.get_by_role('button', name='Start reviewed refresh').click()
                        assert sent.value.status == 303
                        page.wait_for_load_state('networkidle')
                        assert 'Your reviewed refresh is queued' in page.locator('main').inner_text()
                        job_path = urlsplit(page.url).path
                        # Playwright's sync API owns an event loop in this
                        # thread; run the real async worker in a separate one.
                        with ThreadPoolExecutor(max_workers=1) as workers:
                            result = workers.submit(lambda: asyncio.run(process_one(mod.DbSession, mod.fernet,
                                lambda: ResearchService(Provider()), analysis_provider=Gemini())))
                            assert result.result(timeout=15)
                        page.wait_for_url(lambda url: '/research/library/' in url and '/refresh/' not in url, timeout=20000)
                        page.wait_for_load_state('networkidle')
                        fresh_path = urlsplit(page.url).path
                        assert fresh_path != path
                        assert page.get_by_text('The public product description may benefit from merchant review.', exact=True).is_visible()
                        page.get_by_text('AI interpretation details and limits', exact=True).click()
                        assert 'offline-browser-refresh-fixture' in page.locator('main').inner_text()
                        page.screenshot(path=str(output / ('inspection-' + str(width) + '.png')), full_page=True)
                        with mod.DbSession() as session:
                            task_count = session.scalar(select(func.count()).select_from(Task))
                        page.get_by_role('link', name='Build my action plan', exact=False).click()
                        page.wait_for_load_state('networkidle')
                        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
                        selected = page.locator('input[name=selected]').first
                        selected.check()
                        page.get_by_role('button', name='Add selected steps').click()
                        with mod.DbSession() as session:
                            assert session.scalar(select(func.count()).select_from(Task)) == task_count
                        page.get_by_label('I reviewed these suggestions', exact=False).check()
                        page.get_by_role('button', name='Add selected steps').click()
                        page.wait_for_url('**/plan?created=1')
                        assert page.get_by_role('status').get_by_text('Your selected steps', exact=False).is_visible()
                        page.screenshot(path=str(output / ('plan-' + str(width) + '.png')), full_page=True)
                        with mod.DbSession() as session:
                            assert session.scalar(select(func.count()).select_from(Task)) == task_count + 1
                            task = session.scalar(select(Task).where(Task.business_id == registration.business.id))
                            assert task.source_report_id == fresh_path.rsplit('/', 1)[1]
                            assert 'SHA-256:' in task.description
                            task_id = task.id
                        page.goto(origin + '/work', wait_until='networkidle')
                        assert page.locator('#task-' + task_id).is_visible()
                        page.screenshot(path=str(output / ('work-' + str(width) + '.png')), full_page=True)
                        page.locator('form[action="/logout"] button').click()
                        page.wait_for_load_state('networkidle')
                        login()
                        assert page.goto(origin + job_path, wait_until='networkidle').status == 200
                        assert urlsplit(page.url).path == fresh_path
                        with mod.DbSession() as session:
                            assert session.get(ResearchReportRecord, original_id).report_json == original_json
                            fresh = session.get(ResearchReportRecord, fresh_path.rsplit('/', 1)[1])
                            assert fresh.business_id == registration.business.id
                            assert fresh.owner_user_id == registration.user.id and fresh.anonymous_session_hash is None
                        assert '/work#task-' + task_id in page.goto(origin + fresh_path + '/plan', wait_until='networkidle').text()
                        checks.append({'width': width, 'automatic_refresh_report_open': True,
                            'reviewed_source_linked_tasks': True, 'tasks_survive_relogin': True,
                            'keyboard_disclosures': True, 'no_triangle_markers': True, 'reduced_motion': True, 'review_form': True, 'native_review_validation': True,
                            'checkbox_bounds': True, 'no_horizontal_overflow': True, 'post_status': 303,
                            'new_private_version': True, 'original_immutable': True, 'logout_login_reopen': True})
                    finally:
                        context.close()
            finally:
                browser.close()
        assert not page_errors and not blocked_requests
        runner = verify_runner(origin, output)
    finally:
        if server:
            server.should_exit = True
        if thread:
            thread.join(timeout=10)
        listener.close()
        if created:
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()
    receipt = {'date': datetime.now(timezone.utc).isoformat(), 'mode': 'offline_fixture_research_experience_browser',
        'story': 'Reviewed refresh → worker fixture → automatic report open → reviewed plan → persisted Work → logout/login/reopen',
        'database': 'actual isolated PostgreSQL17 schema', 'checks': checks, 'fixture_calls': calls,
        'workspace_preview_runner': runner, 'screenshots': 'Labeled synthetic fixtures, captured in local scratch output; not a hosted app',
        'real_provider_calls': 0, 'mail_delivery': False, 'public_deployment': False, 'page_errors': page_errors,
        'forbidden_requests': blocked_requests, 'cleanup': {'server_stopped': not thread.is_alive(), 'schema_removed': True}}
    target = ROOT / 'docs/evidence/research-experience-browser.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'widths': [entry['width'] for entry in checks], 'passed': len(checks), 'real_provider_calls': 0,
                      'cleanup': receipt['cleanup']}))


if __name__ == '__main__':
    main()
