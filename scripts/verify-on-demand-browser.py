"""Bounded worker-command browser flow; real PostgreSQL, all sources synthetic."""
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


def main():
    url = make_url(os.environ['AYO_TEST_POSTGRES_URL'])
    if url.get_backend_name() != 'postgresql' or url.host not in {'localhost', '127.0.0.1', '::1'}:
        raise RuntimeError('Only a loopback disposable PostgreSQL schema is supported.')
    schema = 'on_demand_browser_' + secrets.token_hex(8)
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
            AYO_ON_DEMAND_RESEARCH='1', AYO_ON_DEMAND_GEMINI_AUTHORIZED='0')
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
                await asyncio.sleep(6)  # Forces a status poll during the worker command.
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

        mod.app.state.research_factory = lambda: ResearchService(Provider())
        server = uvicorn.Server(uvicorn.Config(mod.app, log_level='error', access_log=False))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        deadline = time.monotonic() + 15
        while not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        request_counts = {'dispatch': 0, 'updates': 0}
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
            try:
                for width in (390, 768, 1440):
                    context = browser.new_context(viewport={'width': width, 'height': 950})
                    def restrict(route):
                        if urlsplit(route.request.url).hostname != '127.0.0.1':
                            blocked_requests.append('non-loopback request')
                            route.abort()
                        else:
                            route.continue_()
                    context.route('**/*', restrict)
                    page = context.new_page()
                    page.set_default_timeout(12000)
                    page.on('pageerror', lambda error: page_errors.append(str(error)))
                    def count(request):
                        if request.method == 'POST' and urlsplit(request.url).path.endswith('/dispatch'):
                            request_counts['dispatch'] += 1
                        if request.method == 'GET' and urlsplit(request.url).path.endswith('/updates'):
                            request_counts['updates'] += 1
                    page.on('request', count)
                    try:
                        before = dict(request_counts)
                        print(json.dumps({'width': width, 'stage': 'opening_intake'}), flush=True)
                        page.goto(origin, wait_until='networkidle')
                        page.locator('input[name=query]').fill('https://offline-browser-fixture.org/')
                        page.locator('select[name=country]').select_option('GH')
                        with page.expect_response(lambda response: response.request.method == 'POST'
                                                  and urlsplit(response.url).path.endswith('/dispatch'),
                                                  timeout=20000) as command_response:
                            page.get_by_role('button', name='Start with my business').click()
                        assert command_response.value.status == 200
                        print(json.dumps({'width': width, 'stage': 'worker_response_received'}), flush=True)
                        # Navigation consumes the command body in workspace.js.
                        # Inspect the persisted outcome below; Chromium discards
                        # old response bodies after navigating to the report.
                        page.wait_for_url(lambda url: re.fullmatch(r'/research/[A-Za-z0-9_-]+', urlsplit(url).path) is not None,
                                          timeout=20000)
                        page.wait_for_load_state('networkidle')
                        print(json.dumps({'width': width, 'stage': 'report_opened'}), flush=True)
                        report_id = urlsplit(page.url).path.rsplit('/', 1)[1]
                        assert page.locator('[data-analysis-status=unavailable]').is_visible()
                        assert 'partial research with source observations only' in page.locator('main').inner_text()
                        assert '85.00' in page.locator('main').inner_text()
                        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
                        assert request_counts['dispatch'] == before['dispatch'] + 1
                        assert request_counts['updates'] >= before['updates'] + 1
                        with mod.DbSession() as session:
                            job = session.scalar(select(ResearchJob).where(ResearchJob.report_id == report_id))
                            stored = session.get(ResearchReportRecord, report_id)
                            assert job.status == 'succeeded' and job.attempts == 1
                            assert stored.status == 'PARTIAL'
                            assert json.loads(stored.report_json)['analysis_error_code'] == 'model_not_authorized_for_on_demand'
                        page.screenshot(path=str(output / ('source-report-' + str(width) + '.png')), full_page=True)
                        checks.append({'width': width, 'submitted_url': True, 'one_explicit_worker_post': True,
                            'status_poll_during_command': True, 'automatic_report_open': True,
                            'source_evidence_visible': True, 'source_only_not_ai': True,
                            'attempts': 1, 'no_horizontal_overflow': True})
                    finally:
                        context.close()
                context = browser.new_context(viewport={'width': 390, 'height': 950}, java_script_enabled=False)
                context.route('**/*', restrict)
                page = context.new_page()
                page.goto(origin)
                page.locator('input[name=query]').fill('https://offline-browser-fixture.org/')
                page.get_by_role('button', name='Start with my business').press('Enter')
                assert '/research/jobs/' in page.url
                page.get_by_role('button', name='Run this research').press('Enter')
                page.wait_for_url(lambda url: re.fullmatch(r'/research/[A-Za-z0-9_-]+', urlsplit(url).path) is not None,
                                  timeout=20000)
                assert page.locator('[data-analysis-status=unavailable]').is_visible()
                context.close()
                assert calls['fixture_sources'] == 4 and calls['fixture_models'] == 0
            finally:
                browser.close()
        assert not page_errors and not blocked_requests
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
    receipt = {'date': datetime.now(timezone.utc).isoformat(), 'mode': 'offline_fixture_on_demand_worker_browser',
        'story': 'Public URL -> queued command -> exactly one worker POST -> polling -> source report',
        'database': 'actual isolated PostgreSQL17 schema', 'checks': checks, 'fixture_calls': calls,
        'javascript_disabled_manual_post': True, 'new_real_provider_calls': 0, 'mail_delivery': False,
        'public_deployment': False, 'page_errors': page_errors, 'forbidden_requests': blocked_requests,
        'cleanup': {'server_stopped': not thread.is_alive(), 'schema_removed': True}}
    target = ROOT / 'docs/evidence/on-demand-worker-browser.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'widths': [entry['width'] for entry in checks], 'passed': len(checks),
                      'fixture_sources': calls['fixture_sources'], 'fixture_models': calls['fixture_models'],
                      'no_javascript': True, 'cleanup': receipt['cleanup']}))


if __name__ == '__main__':
    main()
