"""Loopback-only browser regression. ALL source/model/mail data are offline fixtures."""
import asyncio
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import secrets
import threading
import time
from urllib.parse import urlencode, urlsplit

from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.schema import CreateSchema, DropSchema
from playwright.sync_api import sync_playwright
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
schema = 'm2_browser_' + secrets.token_hex(8)
pg_url = os.environ['AYO_TEST_POSTGRES_URL']
admin = create_engine(pg_url)
with admin.begin() as conn:
    conn.execute(CreateSchema(schema))
os.environ.update(ENVIRONMENT='test', SESSION_SECRET=secrets.token_urlsafe(48),
    TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(), APP_ORIGIN='http://127.0.0.1:8018',
    DATABASE_URL=pg_url + '?' + urlencode({'options': '-csearch_path=' + schema}),
    AYO_PROVIDER_SPEND_AUTHORIZED='0', AYO_MAIL_SEND_AUTHORIZED='0', AYO_PREVIEW_MODE='0')
from ayo import app as mod
from ayo.jobs import process_one
from ayo.models import MailOutbox, ResearchJob, ResearchReportRecord
from ayo.research import BusinessCandidate, ResearchError, ResearchService, SourceDocument

class SourceFixture:
    async def search(self, query, country='', city='', limit=5):
        return (BusinessCandidate(id='offline-candidate', name='Offline Fixture Clothing Business',
            url='https://offline-fixture.org/', snippet='Offline fixture clothing business and wholesale shop; not a real prospect.',
            country=country, source_id='offline-search', discovered_at=datetime.now(timezone.utc), provider='offline-fixture'),)
    async def fetch(self, url, country=''):
        text = 'Offline Fixture Clothing Business sells handmade clothing. Public delivery information needs review.'
        return SourceDocument(id='offline-page', url=url, title='Offline Fixture Clothing Business',
            retrieved_at=datetime.now(timezone.utc), source_hash=hashlib.sha256(text.encode()).hexdigest(),
            excerpt=text, content=text, provider='offline-fixture', provider_receipt_id='offline-receipt')

class RejectedFixture:
    async def research(self, *_args, **_kwargs):
        raise ResearchError('provider_rate_limited', 'Offline fixture rejection')

class GeminiFixture:
    name, model = 'gemini', 'offline-gemini-fixture'
    async def complete(self, policy, payload):
        quote = 'Offline Fixture Clothing Business sells handmade clothing.'
        return {'claims': [{'text': quote, 'quote': quote, 'kind': 'OBSERVED',
                            'evidence_ids': [payload['evidence'][0]['id']]}],
                'recommendations': [], 'limitations': ['Explicit offline browser fixture.']}, {'totalTokenCount': 100}

mod.app.state.research_factory = lambda: ResearchService(SourceFixture())
server = uvicorn.Server(uvicorn.Config(mod.app, host='127.0.0.1', port=8018, access_log=False, log_level='warning'))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
checks = []
def run_worker(factory):
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(process_one(mod.DbSession, mod.fernet, factory, analysis_provider=GeminiFixture()))).result()
try:
    for _ in range(100):
        if server.started:
            break
        time.sleep(.05)
    assert server.started
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        for width in [390, 768, 1440]:
            for market in ['NG', 'GH']:
                context = browser.new_context(viewport={'width': width, 'height': 950})
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(type(error).__name__))
                page.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).hostname == '127.0.0.1' else route.abort())
                def check_layout(stage):
                    page.wait_for_function('() => document.fonts.status === "loaded"')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, market, stage)
                    assert page.evaluate('document.fonts.check("16px Syne") && document.fonts.check("16px \\\"DM Sans\\\"")')
                page.goto('http://127.0.0.1:8018/')
                page.locator('[name=query]').fill('Offline fixture clothing business')
                page.locator('[name=country]').select_option(market)
                page.locator('form[action="/research"] button[type=submit]').click()
                page.wait_for_url('**/research')
                check_layout('matches')
                page.locator('form[action="/research/select"] button').first.click()
                page.wait_for_url('**/research/jobs/*')
                job_path = urlsplit(page.url).path
                assert 'Research queued' in page.locator('main').inner_text()
                check_layout('queued')
                run_worker(RejectedFixture)
                page.reload()
                assert 'bounded retry' in page.locator('main').inner_text().lower()
                assert page.locator('time[datetime]').count() >= 2
                check_layout('retry')
                with mod.DbSession() as session:
                    job = session.get(ResearchJob, job_path.rsplit('/', 1)[1])
                    job.lease_until = time.time() - 1
                    session.commit()
                run_worker(mod.app.state.research_factory)
                page.reload()
                page.wait_for_url('**/research/*')
                assert page.locator('[data-analysis-status=completed]').count() == 1
                report_path = urlsplit(page.url).path
                check_layout('report')
                page.goto('http://127.0.0.1:8018/signup')
                email = f'offline-{market.lower()}-{width}@example.org'
                page.locator('[name=email]').fill(email)
                page.locator('[name=password]').fill('OfflineFixturePassword123!')
                page.locator('[name=business_name]').fill('Offline fixture workspace')
                page.locator('[name=country]').select_option(market)
                with page.expect_response(lambda response: response.request.method == 'POST' and urlsplit(response.url).path == '/signup') as signup_response:
                    page.locator('form[action="/signup"] button').click()
                registration_mode = 'new_fixture_account'
                if signup_response.value.status == 429:
                    # Six signups on one loopback address intentionally hit the
                    # real five/hour control. Verify it, then use a verified
                    # fixture account for the remaining save/reopen UI check.
                    assert width == 1440 and market == 'GH'
                    registration_mode = 'expected_signup_throttle_then_existing_fixture_account'
                    email = 'offline-gh-390@example.org'
                    page.goto('http://127.0.0.1:8018/login')
                    page.locator('[name=email]').fill(email)
                    page.locator('[name=password]').fill('OfflineFixturePassword123!')
                    page.locator('form[action="/login"] button').click()
                    page.wait_for_url('**/dashboard')
                else:
                    assert signup_response.value.status == 303
                    page.wait_for_url('**/dashboard')
                    with mod.DbSession() as session:
                        mail = session.scalar(select(MailOutbox).where(MailOutbox.recipient == email))
                        verification = json.loads(mod.fernet.decrypt(mail.payload_cipher.encode()))['url']
                    page.goto(verification)
                    page.wait_for_url('**/dashboard')
                page.goto('http://127.0.0.1:8018' + report_path)
                assert 'saved in your private workspace' in page.locator('main').inner_text()
                with mod.DbSession() as session:
                    record = session.get(ResearchReportRecord, report_path.rsplit('/', 1)[1])
                    assert record.business_id and record.country == market
                    stored_json = record.report_json
                page.locator('form[action="/logout"] button').click()
                page.goto('http://127.0.0.1:8018/login')
                page.locator('[name=email]').fill(email)
                page.locator('[name=password]').fill('OfflineFixturePassword123!')
                page.locator('form[action="/login"] button').click()
                page.wait_for_url('**/dashboard')
                check_layout('dashboard')
                page.goto('http://127.0.0.1:8018' + report_path)
                with mod.DbSession() as session:
                    assert session.get(ResearchReportRecord, report_path.rsplit('/', 1)[1]).report_json == stored_json
                page.goto('http://127.0.0.1:8018/leads')
                page.locator('[name=query]').fill('clothing business')
                page.locator('[name=country]').select_option(market)
                page.locator('form[action="/leads/discover"] button').click()
                page.wait_for_url('**/leads')
                assert page.locator('.prospect-row').count() == 1
                if registration_mode == 'expected_signup_throttle_then_existing_fixture_account':
                    assert page.locator('.lead-status').inner_text() == 'Qualified'
                else:
                    page.get_by_role('link', name='Open prospect', exact=False).click()
                    page.wait_for_url('**/leads/*')
                    assert 'Offline Fixture Clothing Business' in page.locator('main').inner_text()
                    assert 'Offline fixture clothing business and wholesale shop' in page.locator('main').inner_text()
                    check_layout('prospect_detail')
                    page.locator('[name=note]').fill('Offline fixture source lists clothing wholesale; review needed.')
                    with page.expect_response(lambda response: response.request.method == 'POST'
                        and urlsplit(response.url).path.endswith('/qualify')) as qualification_response:
                        page.locator('form[action$="/qualify"] button').click()
                    assert qualification_response.value.status == 303
                    page.wait_for_url('**/leads')
                assert page.locator('.prospect-row').count() == 1
                assert page.locator('.lead-status').inner_text() == 'Qualified'
                check_layout('leads')
                assert not errors, errors
                checks.append({'width': width, 'market': market, 'queued_retry_progress': 'passed',
                    'source_gemini_fixture_report': 'passed', 'fixture_account_verify_claim_relogin_reopen': 'passed', 'registration_mode': registration_mode,
                    'fixture_leads_qualification': 'passed', 'stored_report_unchanged': True,
                    'overflow': False, 'page_errors': 0, 'fonts': 'passed'})
                context.close()
        browser.close()
    result = {'timestamp': datetime.now(timezone.utc).isoformat(), 'mode': 'offline_browser_fixtures',
              'database': 'actual_local_postgresql_isolated_schema', 'provider_network_calls': 0,
              'mail_delivery': 'fixture_outbox_token_only', 'live_provider_verified': False, 'checks': checks}
    (ROOT / 'docs/evidence/m2-hardening-browser.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
finally:
    server.should_exit = True
    thread.join(10)
    mod.engine.dispose()
    with admin.begin() as conn:
        conn.execute(DropSchema(schema, cascade=True))
    admin.dispose()
