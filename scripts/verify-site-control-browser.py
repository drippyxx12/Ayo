"""Real Chromium/HTTP/PostgreSQL flow with synthetic accounts and HTTPS fixtures."""
from datetime import datetime, timezone
import json
import os
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
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    url = make_url(os.environ['AYO_TEST_POSTGRES_URL'])
    if url.get_backend_name() != 'postgresql' or url.host not in {'localhost', '127.0.0.1', '::1'}:
        raise RuntimeError('Only a loopback disposable PostgreSQL schema is supported.')
    schema = 'site_browser_' + secrets.token_hex(8)
    admin = create_engine(url)
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(128)
    listener.setblocking(False)
    origin = 'http://127.0.0.1:' + str(listener.getsockname()[1])
    output = Path(os.environ.get('AYO_BROWSER_OUTPUT_DIR', str(ROOT.parent / 'scratch/ayo-site-browser')))
    output.mkdir(parents=True, exist_ok=True)
    server = thread = None
    created = False
    checks, errors, blocked = [], [], []
    calls = {'robots': 0, 'verification_file': 0}
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
            AYO_PREVIEW_MODE='0', AYO_ON_DEMAND_RESEARCH='0', AYO_ON_DEMAND_GEMINI_AUTHORIZED='0')
        with admin.connect() as connection:
            connection.exec_driver_sql('SET search_path TO "' + schema + '"')
            connection.commit()
            config = Config(str(ROOT / 'alembic.ini'))
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
            connection.commit()
        from ayo import app as mod
        from ayo.identity import IdentityService
        from ayo.public_http import PublicHTTPResponse
        from ayo.site_control_models import SiteControlClaim
        from ayo.site_control_reader import PROOF_PATH, SiteFileReader

        def fixture(url):
            if url.endswith('/robots.txt'):
                calls['robots'] += 1
                body = b'User-agent: *\nAllow: /\n'
            else:
                assert urlsplit(url).path == PROOF_PATH
                calls['verification_file'] += 1
                with mod.DbSession() as session:
                    row = session.scalar(select(SiteControlClaim).where(
                        SiteControlClaim.host == urlsplit(url).hostname, SiteControlClaim.status == 'checking'))
                    assert row and row.token_cipher
                    body = mod.fernet.decrypt(row.token_cipher.encode()) + b'\n'
            return PublicHTTPResponse(url, 200, {'content-type': 'text/plain'}, body)
        mod.app.state.site_file_reader_factory = lambda: SiteFileReader(request=fixture)
        server = uvicorn.Server(uvicorn.Config(mod.app, log_level='error', access_log=False))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        deadline = time.monotonic() + 15
        while not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        password = 'SyntheticSiteProofPassword123!'
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
            try:
                for width in (390, 768, 1440):
                    email = 'site-' + str(width) + '@example.invalid'
                    with mod.DbSession() as session:
                        registration = IdentityService(session).register(email, password, 'Synthetic site-control studio', 'GH')
                        registration.user.email_verified_at = time.time()  # Fixture, not delivered email.
                        session.commit()
                    context = browser.new_context(viewport={'width': width, 'height': 980}, reduced_motion='reduce')
                    try:
                        def restrict(route):
                            if not route.request.url.startswith(origin + '/'):
                                blocked.append(route.request.url)
                                route.abort()
                            else:
                                route.continue_()
                        context.route('**/*', restrict)
                        page = context.new_page()
                        page.set_default_timeout(10000)
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        def login():
                            page.goto(origin + '/login', wait_until='networkidle')
                            page.get_by_label('WORK EMAIL', exact=True).fill(email)
                            page.get_by_label('PASSWORD', exact=True).fill(password)
                            page.get_by_role('button', name='Sign in', exact=False).click()
                            page.wait_for_url('**/dashboard')
                        login()
                        page.goto(origin + '/business', wait_until='networkidle')
                        page.get_by_role('link', name='Verify a website you control', exact=False).click()
                        page.get_by_label('Exact website host').fill('browser-' + str(width) + '.example.org')
                        before = dict(calls)
                        page.get_by_role('button', name='Create verification file', exact=False).click()
                        page.wait_for_load_state('networkidle')
                        assert calls == before
                        detail_path = urlsplit(page.url).path
                        assert page.locator('.site-proof-text').inner_text().startswith('ayo-site-verification=')
                        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
                        page.screenshot(path=str(output / ('instructions-' + str(width) + '.png')), full_page=True)
                        page.get_by_role('button', name='Check verification file', exact=True).click()
                        page.wait_for_load_state('networkidle')
                        assert page.get_by_text('HTTPS file control verified', exact=False).is_visible()
                        assert calls == {'robots': before['robots'] + 1, 'verification_file': before['verification_file'] + 1}
                        with mod.DbSession() as session:
                            row = session.get(SiteControlClaim, detail_path.rsplit('/', 1)[1])
                            assert row.status == 'verified' and row.token_cipher is None and row.proof_body_sha256
                        page.get_by_role('button', name='Sign out', exact=False).click()
                        login()
                        page.goto(origin + detail_path, wait_until='networkidle')
                        assert page.get_by_text('HTTPS file control verified', exact=False).is_visible()
                        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
                        page.screenshot(path=str(output / ('verified-' + str(width) + '.png')), full_page=True)
                        page.get_by_role('button', name='Revoke this workspace', exact=False).click()
                        page.wait_for_load_state('networkidle')
                        assert page.get_by_text('This workspace has revoked', exact=False).is_visible()
                        assert page.get_by_role('link', name='Continue with your research', exact=False).is_visible()
                        checks.append({'width': width, 'create_check_relogin_reopen_revoke': True,
                            'no_horizontal_overflow': True, 'fixed_two_fixture_gets': True})
                    finally:
                        context.close()
            finally:
                browser.close()
        assert not errors and not blocked
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
    receipt = {'date': datetime.now(timezone.utc).isoformat(), 'mode': 'offline_fixture_site_control_browser',
        'story': 'Business → create challenge → explicit file check → logout/login/reopen → revoke → research available',
        'database': 'actual isolated PostgreSQL17 schema migrated through 0009', 'checks': checks,
        'fixture_http_calls': calls, 'real_website_requests': 0, 'real_provider_calls': 0,
        'provider_cost_usd': 0, 'mail_delivered': False, 'domain_file_published': False,
        'screenshots': 'Synthetic fixtures in local scratch output, not hosted/live domain acceptance',
        'page_errors': errors, 'forbidden_requests': blocked,
        'cleanup': {'server_stopped': not thread.is_alive(), 'schema_removed': True}}
    (ROOT / 'docs/evidence/site-control-browser.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed_widths': [check['width'] for check in checks], 'real_provider_calls': 0,
                      'cleanup': receipt['cleanup']}))


if __name__ == '__main__':
    main()
