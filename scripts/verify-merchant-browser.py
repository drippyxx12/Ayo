"""Loopback browser verification with disposable PostgreSQL and OFFLINE fixtures.

Run with AYO_TEST_POSTGRES_URL pointing to a local disposable test database.
No private runtime loader, real provider, delivered mail, outreach or sale is used.
The script migrates a fresh schema, generates synthetic signing/encryption keys,
forbids browser egress and cleans its server/database in finally blocks.
"""
from datetime import datetime, timedelta, timezone
import hashlib
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
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RECEIPT = ROOT / 'docs/evidence/merchant-platform-browser.json'
PASSWORD = 'OfflineBrowserFixturePassword123!'
WIDTHS = ((390, 'NG'), (768, 'GH'), (1440, 'NG'))


def main():
    pg_url = make_url(os.environ['AYO_TEST_POSTGRES_URL'])
    if pg_url.get_backend_name() != 'postgresql' or pg_url.host not in {'127.0.0.1', 'localhost', '::1'}:
        raise RuntimeError('Use a loopback PostgreSQL test database; remote databases are refused.')
    schema = 'merchant_browser_' + secrets.token_hex(8)
    admin = create_engine(pg_url)
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(128)
    listener.setblocking(False)
    port = listener.getsockname()[1]
    origin = 'http://127.0.0.1:' + str(port)
    server, thread, mod = None, None, None
    schema_created = False
    result = None
    counters = {'blocked_private_analysis_attempts': 0, 'unexpected_source_factory_calls': 0}
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        schema_created = True
        # Remove inherited provider configuration by name without inspecting it.
        for name in ('FIRECRAWL_API_KEY', 'GEMINI_API_KEY', 'GEMINI_MODEL', 'ANTHROPIC_API_KEY',
                     'ANTHROPIC_MODEL', 'RESEND_API_KEY', 'SHOPIFY_CLIENT_ID', 'SHOPIFY_CLIENT_SECRET'):
            os.environ.pop(name, None)
        os.environ.update(ENVIRONMENT='development', SESSION_SECRET=secrets.token_urlsafe(48),
            TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(), APP_ORIGIN=origin,
            DATABASE_URL=pg_url.update_query_dict({'options': '-csearch_path=' + schema}).render_as_string(hide_password=False),
            AYO_PROVIDER_SPEND_AUTHORIZED='0', AYO_MAIL_SEND_AUTHORIZED='0', AYO_PREVIEW_MODE='0',
            AYO_AI_PROVIDER='gemini', AYO_AI_DATA_POLICY='public_only_reviewed')
        with admin.connect() as connection:
            connection.exec_driver_sql('SET search_path TO "' + schema + '"')
            connection.commit()
            config = Config(str(ROOT / 'alembic.ini'))
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
            migration = connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
            connection.commit()
        from ayo import app as mod
        from ayo.assistant_models import AssistantConversation, AssistantMessage, AssistantToolRun
        from ayo.intelligence import IntelligenceError
        from ayo.lead_models import LeadList, LeadListItem, LeadNote, OutreachDraft
        from ayo.leads import LeadCandidate
        from ayo.merchant_models import BusinessProfile, Task
        from ayo.models import AuditEvent, Business, FoundingGrant, Lead, MailOutbox, Membership, ResearchReportRecord, User
        from ayo.report_storage import ReportStore
        from ayo.research import PublicProduct, ResearchError, ResearchReport, SourceDocument

        class BlockedPrivateAnalysis:
            async def analyze(self, context):
                counters['blocked_private_analysis_attempts'] += 1
                assert context.evidence
                raise IntelligenceError('private_analysis_not_authorized',
                    'Offline browser fixture: private workspace inference is unavailable under the public-only policy.')

        def no_source_factory():
            counters['unexpected_source_factory_calls'] += 1
            raise ResearchError('provider_not_configured', 'Offline browser fixture: source providers are disabled.')

        mod.app.state.intelligence_factory = BlockedPrivateAnalysis
        mod.app.state.research_factory = no_source_factory
        server = uvicorn.Server(uvicorn.Config(mod.app, host='127.0.0.1', port=port,
            access_log=False, log_level='warning'))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        for _ in range(100):
            if server.started:
                break
            if not thread.is_alive():
                raise RuntimeError('Loopback browser server stopped before startup.')
            time.sleep(.05)
        assert server.started, 'Loopback browser server did not start.'

        def seed_saved_fixtures(user_id, business_id, width, market):
            now = datetime.now(timezone.utc)
            report_ids, report_hashes = [], {}
            for label, price, captured in [('earlier', '40.00', now - timedelta(days=21)),
                                           ('latest', '50.00', now - timedelta(minutes=5))]:
                body = (f'Offline Fixture Tote listed for {price}.\nCategory: Accessories\n'
                        'Instagram\nDelivery information is available on request.\n'
                        'Explicit synthetic browser source; no real business was researched.')
                source_id = f'offline-page-{width}-{label}'
                source = SourceDocument(id=source_id, url='https://offline-browser-fixture.org/',
                    retrieved_at=captured, title='Offline Fixture Shop', excerpt=body, content=body,
                    source_hash=hashlib.sha256(body.encode()).hexdigest(),
                    html_source_hash=hashlib.sha256(('offline markup ' + body).encode()).hexdigest(),
                    product_observations=(PublicProduct(name='Offline Fixture Tote', listed_price=price,
                        currency='NGN' if market == 'NG' else 'GHS'),), channel_observations=('Instagram',),
                    provider='offline-browser-fixture', provider_receipt_id='offline-receipt-' + label)
                report = ResearchReport(business_name='Offline Fixture Research — ' + label,
                    target_url=source.url, country=market, status='PARTIAL', source_documents=(source,),
                    claims=({'text': body.splitlines()[0], 'kind': 'OBSERVED', 'evidence_ids': (source_id,),
                             'observed_at': captured},),
                    opportunities=({'title': 'Review fixture delivery policy',
                        'description': 'Review the retained delivery information with your team.',
                        'evidence_ids': (source_id,), 'next_step': 'Check the saved source before making a plan.'},),
                    limitations=('Explicit offline browser source; no source or model provider was called.',),
                    created_at=captured)
                with mod.DbSession() as session:
                    store = ReportStore(session, clock=lambda: captured.timestamp())
                    anonymous_id = 'offline-browser-' + secrets.token_urlsafe(32)
                    row, token = store.save_preview(report, anonymous_id)
                    store.claim(token, anonymous_id, user_id, business_id)
                    session.commit()
                    report_ids.append(row.id)
                    report_hashes[row.id] = hashlib.sha256(row.report_json.encode()).hexdigest()
            candidate = LeadCandidate(id='offline-prospect-' + str(width), name='Offline Fixture Retailer',
                url='https://offline-retailer-fixture.org/', country=market,
                city='Lagos' if market == 'NG' else 'Accra', source_id='offline-discovery-' + str(width),
                source_url='https://offline-directory-fixture.org/',
                source_excerpt='Offline Fixture Retailer is a synthetic retail clothing business. No real prospect was discovered.',
                discovered_at=now, fit_reasons=('Synthetic clothing retail fit for browser verification.',),
                fit_evidence_ids=('offline-discovery-' + str(width),))
            with mod.DbSession() as session:
                row = Lead(business_id=business_id, name=candidate.name, url=candidate.url, country=market,
                    fit_reason=candidate.fit_reasons[0], evidence_json=candidate.model_dump_json())
                session.add(row)
                session.commit()
                return report_ids, report_hashes, row.id

        checks = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                args=['--no-sandbox'])
            try:
                for width, market in WIDTHS:
                    browser_context = browser.new_context(viewport={'width': width, 'height': 950},
                        reduced_motion='reduce')
                    page = browser_context.new_page()
                    page.set_default_timeout(12000)
                    page_errors, network_failures, forbidden_requests, http_checks, screen_checks = [], [], [], [], []
                    page.on('pageerror', lambda error: page_errors.append(type(error).__name__))
                    page.on('requestfailed', lambda request: network_failures.append({
                        'path': urlsplit(request.url).path, 'failure': request.failure}))

                    def restrict_network(route):
                        parsed = urlsplit(route.request.url)
                        if parsed.scheme == 'http' and parsed.hostname == '127.0.0.1' and parsed.port == port:
                            route.continue_()
                        else:
                            forbidden_requests.append({'scheme': parsed.scheme, 'host': parsed.hostname, 'path': parsed.path})
                            route.abort()
                    browser_context.route('**/*', restrict_network)

                    def check_screen(stage):
                        page.evaluate('''async () => {
                            await Promise.all(['16px Syne', '16px "DM Sans"', '16px "DM Mono"']
                                .map(font => document.fonts.load(font)));
                        }''')
                        page.wait_for_function('() => document.fonts.status === "loaded"')
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, stage, 'horizontal overflow')
                        assert page.evaluate('document.fonts.check("16px Syne") && document.fonts.check(\'16px "DM Sans"\') && document.fonts.check(\'16px "DM Mono"\')')
                        unlabeled = page.locator('input:not([type=hidden]),select,textarea').evaluate_all('''elements => elements.filter(element =>
                            !element.labels?.length && !element.getAttribute('aria-label') && !element.getAttribute('aria-labelledby'))
                            .map(element => ({tag:element.tagName,id:element.id,name:element.name}))''')
                        assert not unlabeled, (stage, unlabeled)
                        assert page.locator('main#main-content').count() == 1, (stage, 'missing main landmark')
                        assert page.locator('a.skip-link[href="#main-content"]').count() == 1
                        screen_checks.append({'stage': stage, 'horizontal_overflow': False, 'fonts_loaded': True,
                            'unlabeled_form_controls': 0, 'main_and_skip_link': True})

                    def visit(path, stage, expected=200):
                        response = page.goto(origin + path, wait_until='networkidle')
                        assert response is not None and response.status == expected, (stage, response.status if response else None)
                        http_checks.append({'stage': stage, 'method': 'GET', 'path': path.split('?', 1)[0], 'status': response.status})
                        if expected == 200:
                            check_screen(stage)
                        return response

                    def submit(form, path, stage, expected=303):
                        with page.expect_response(lambda response: response.request.method == 'POST'
                            and urlsplit(response.url).path == path) as response_info:
                            form.get_by_role('button').first.click()
                        response = response_info.value
                        assert response.status == expected, (stage, response.status, response.text()[:500])
                        page.wait_for_load_state('networkidle')
                        http_checks.append({'stage': stage, 'method': 'POST', 'path': path, 'status': response.status})
                        check_screen(stage)

                    try:
                        email = f'offline-merchant-{width}@example.org'
                        visit('/', 'public_intake')
                        visit('/signup', 'registration')
                        signup = page.locator('form[action="/signup"]')
                        signup.get_by_label('WORK EMAIL').fill(email)
                        signup.get_by_label('BUSINESS NAME').fill('Offline fixture workspace ' + str(width))
                        signup.get_by_label('YOUR MARKET').select_option(market)
                        signup.get_by_label('PASSWORD', exact=True).fill(PASSWORD)
                        submit(signup, '/signup', 'account_registered')
                        with mod.DbSession() as session:
                            user = session.scalar(select(User).where(User.email == email))
                            user_id = user.id
                            business_id = session.scalar(select(Membership.business_id).where(Membership.user_id == user_id))
                            mail = session.scalar(select(MailOutbox).where(MailOutbox.user_id == user_id,
                                MailOutbox.kind == 'verify_email'))
                            verification_url = json.loads(mod.fernet.decrypt(mail.payload_cipher.encode()))['url']
                        with page.expect_response(lambda response: urlsplit(response.url).path == '/verify-email') as verification:
                            page.goto(verification_url, wait_until='networkidle')
                        assert verification.value.status == 303
                        http_checks.append({'stage': 'fixture_outbox_verification', 'method': 'GET', 'path': '/verify-email', 'status': verification.value.status})
                        report_ids, original_report_hashes, lead_id = seed_saved_fixtures(user_id, business_id, width, market)
                        earlier_id, latest_id = report_ids
                        visit('/business', 'profile_before_edit')
                        profile = page.locator('form[action="/business"]')
                        business_name = 'Offline merchant studio ' + str(width)
                        profile.get_by_label('Business name', exact=True).fill(business_name)
                        profile.get_by_label('What does your business offer?').fill('Offline owner-provided handmade clothing offer')
                        profile.get_by_label('Products or services').fill('Fixture shirts and totes')
                        profile.get_by_label('Who are you trying to reach?').fill('Independent clothing retailers')
                        profile.get_by_label('Your business goals').fill('Review delivery information with the team')
                        profile.get_by_label('City or area', exact=False).fill('Lagos' if market == 'NG' else 'Accra')
                        submit(profile, '/business', 'profile_saved')
                        assert 'OWNER_PROVIDED_UNVERIFIED' in page.locator('main').inner_text()
                        visit('/dashboard', 'home_actual_saved_records')
                        assert page.locator('.workspace-summary dd').all_text_contents() == ['2', '1', '0']
                        nav_link = page.locator('.workspace-nav a[href="/research/library"]')
                        nav_link.focus()
                        assert nav_link.evaluate('element => element === document.activeElement')
                        page.keyboard.press('Enter')
                        page.wait_for_url('**/research/library')
                        page.wait_for_load_state('networkidle')
                        check_screen('keyboard_navigation_to_research')
                        page.get_by_label('SEARCH TITLE OR TARGET URL').fill('latest')
                        page.get_by_role('button', name='Apply filters').click()
                        page.wait_for_load_state('networkidle')
                        assert page.locator('.rw-library-record').count() == 1
                        assert 'latest' in page.locator('.rw-library-record').inner_text()
                        check_screen('research_filter')
                        visit('/research/library', 'research_library_two_snapshots')
                        page.get_by_label('LEFT REPORT', exact=True).select_option(earlier_id)
                        page.get_by_label('RIGHT REPORT', exact=True).select_option(latest_id)
                        page.get_by_role('button', name='Compare saved evidence').click()
                        page.wait_for_load_state('networkidle')
                        assert 'Snapshot history.' in page.locator('main').inner_text()
                        assert '40.00' in page.locator('main').inner_text() and '50.00' in page.locator('main').inner_text()
                        check_screen('research_compare_history')
                        visit('/research/library/' + latest_id, 'research_evidence_inspection')
                        assert 'Category: Accessories' in page.locator('main').inner_text()
                        assert 'Instagram' in page.locator('main').inner_text()
                        assert page.locator('a[href="#source-1"]').count() > 0
                        page.get_by_role('link', name='Create a linked task', exact=False).first.click()
                        page.wait_for_load_state('networkidle')
                        assert page.locator('form[action="/work/tasks"] input[name=source_report_id]').input_value() == latest_id
                        check_screen('work_from_saved_source')
                        create_task = page.locator('form[action="/work/tasks"]')
                        task_title = 'Review saved delivery evidence ' + str(width)
                        create_task.get_by_label('What needs to happen?').fill(task_title)
                        create_task.get_by_label('Details', exact=False).fill('Internal review only; no external action.')
                        create_task.get_by_label('Due date', exact=False).fill('2026-12-15')
                        submit(create_task, '/work/tasks', 'source_task_created')
                        task_article = page.locator('.task-record').filter(has=page.get_by_role('heading', name=task_title, exact=True))
                        task_article.locator('summary').click()
                        edit_task = task_article.locator('form')
                        task_id = edit_task.get_attribute('action').rsplit('/', 1)[1]
                        edit_task.get_by_label('Status', exact=True).select_option('done')
                        submit(edit_task, '/work/tasks/' + task_id, 'merchant_task_completion_recorded')
                        assert 'No external action, reply or sale is verified' in page.locator('main').inner_text()
                        visit('/leads', 'prospect_library')
                        list_form = page.locator('form[action="/leads/lists"]')
                        list_form.get_by_label('LIST NAME').fill('Offline retailer shortlist ' + str(width))
                        list_form.get_by_label('CONTEXT', exact=False).fill('Synthetic list for manual review')
                        submit(list_form, '/leads/lists', 'prospect_list_created')
                        with mod.DbSession() as session:
                            list_id = session.scalar(select(LeadList.id).where(LeadList.business_id == business_id))
                        visit('/leads/' + lead_id, 'prospect_detail')
                        add_to_list = page.locator(f'form[action="/leads/lists/{list_id}/items"]')
                        submit(add_to_list, f'/leads/lists/{list_id}/items', 'prospect_added_to_list')
                        qualify = page.locator(f'form[action="/leads/{lead_id}/qualify"]')
                        qualify.get_by_label('WHY IS THIS BUSINESS A FIT?', exact=False).fill('Offline source explicitly describes a retail clothing business; manual fit review only.')
                        submit(qualify, f'/leads/{lead_id}/qualify', 'prospect_qualified_after_review')
                        visit('/leads/' + lead_id, 'qualified_prospect_detail')
                        note = page.locator(f'form[action="/leads/{lead_id}/notes"]')
                        note.get_by_label('ADD A WORKSPACE NOTE').fill('Offline private note: review fit before contacting anyone.')
                        submit(note, f'/leads/{lead_id}/notes', 'prospect_note_saved')
                        draft = page.locator(f'form[action="/leads/{lead_id}/drafts"]')
                        draft.get_by_label('YOUR OFFER, IN YOUR WORDS').fill('We make small-batch clothing for independent retailers.')
                        submit(draft, f'/leads/{lead_id}/drafts', 'sourced_draft_prepared')
                        draft_edit = page.locator(f'form[action^="/leads/{lead_id}/drafts/"]')
                        draft_path = draft_edit.get_attribute('action')
                        draft_edit.get_by_label('SUBJECT', exact=True).fill('Offline fixture introduction for review')
                        draft_edit.get_by_label('EDIT YOUR DRAFT').fill(draft_edit.get_by_label('EDIT YOUR DRAFT').input_value()
                            + '\n\nReviewed internally; no message sent.')
                        submit(draft_edit, draft_path, 'reviewed_draft_saved')
                        assert 'Draft only.' in page.locator('main').inner_text()
                        followup = page.locator(f'form[action="/leads/{lead_id}/followups"]')
                        followup.get_by_label('NEXT STEP', exact=True).fill('Review retailer follow-up ' + str(width))
                        followup.get_by_label('DETAILS', exact=False).fill('Review permission and source freshness. No send scheduled.')
                        followup.get_by_label('DUE DATE', exact=False).fill('2026-12-16')
                        submit(followup, f'/leads/{lead_id}/followups', 'lead_followup_task_saved')
                        visit('/work', 'work_includes_lead_followup')
                        assert page.locator('.task-record').count() == 2
                        visit('/ayo', 'ayo_conversation_library')
                        conversation_form = page.locator('form[action="/ayo/conversations"]')
                        conversation_form.get_by_label('NEW CONVERSATION').fill('Offline next move ' + str(width))
                        submit(conversation_form, '/ayo/conversations', 'conversation_created')
                        conversation_path = urlsplit(page.url).path
                        message = page.locator(f'form[action="{conversation_path}/messages"]')
                        question = 'What should I focus on next?\nUse only my saved workspace facts.'
                        message.get_by_label('WHAT WOULD YOU LIKE TO UNDERSTAND?').fill(question)
                        submit(message, conversation_path + '/messages', 'workspace_reads_saved_private_inference_blocked')
                        assert 'No AI answer was generated' in page.locator('main').inner_text()
                        assert 'Workspace facts' in page.locator('main').inner_text()
                        assert page.locator('.assistant-tool').count() == 5
                        assert 'OWNER_PROVIDED_UNVERIFIED' in page.locator('main').inner_text()
                        assert task_title in page.locator('main').inner_text()
                        submit(page.locator('form[action="/logout"]'), '/logout', 'logout')
                        visit('/login', 'relogin')
                        login = page.locator('form[action="/login"]')
                        login.get_by_label('WORK EMAIL').fill(email)
                        login.get_by_label('PASSWORD', exact=True).fill(PASSWORD)
                        submit(login, '/login', 'relogin_persistent_workspace')
                        visit(conversation_path, 'reopened_saved_conversation')
                        assert 'What should I focus on next?' in page.locator('main').inner_text()
                        visit('/research/library/' + latest_id, 'reopened_saved_evidence')
                        visit('/business', 'reopened_profile')
                        assert page.get_by_label('Your business goals').input_value() == 'Review delivery information with the team'
                        visit('/business/setup', 'second_workspace_setup')
                        setup = page.locator('form[action="/business/setup"]')
                        setup.get_by_label('Business name', exact=True).fill('Offline second workspace ' + str(width))
                        setup.get_by_label('Market', exact=True).select_option('GH' if market == 'NG' else 'NG')
                        submit(setup, '/business/setup', 'second_workspace_created')
                        with mod.DbSession() as session:
                            second_id = session.scalar(select(Business.id).join(Membership, Membership.business_id == Business.id)
                                .where(Membership.user_id == user_id, Business.id != business_id))
                        assert page.locator('.workspace-summary dd').all_text_contents() == ['0', '0', '0']
                        for path, stage, absent in [('/work', 'isolated_workspace_work', task_title),
                            ('/leads', 'isolated_workspace_leads', 'Offline Fixture Retailer'),
                            ('/research/library', 'isolated_workspace_research', 'Offline Fixture Research'),
                            ('/ayo', 'isolated_workspace_conversations', 'Offline next move ' + str(width))]:
                            visit(path, stage)
                            assert absent not in page.locator('main').inner_text(), stage
                        for path, stage in [('/research/library/' + latest_id, 'other_workspace_report_denied'),
                            ('/leads/' + lead_id, 'other_workspace_lead_denied'),
                            (conversation_path, 'other_workspace_conversation_denied')]:
                            visit(path, stage, expected=404)
                        visit('/settings', 'workspace_switch_settings')
                        switch = page.locator('form[action="/business/switch"]')
                        switch.get_by_label('Choose a workspace you belong to').select_option(business_id)
                        submit(switch, '/business/switch', 'original_workspace_restored')
                        assert page.locator('.workspace-summary dd').all_text_contents() == ['2', '1', '1']
                        visit('/activity', 'real_audit_activity')
                        visit('/work', 'final_persisted_work')
                        assert page.locator('.task-record').count() == 2
                        with mod.DbSession() as session:
                            profile_row = session.get(BusinessProfile, business_id)
                            task_rows = session.scalars(select(Task).where(Task.business_id == business_id)).all()
                            draft_row = session.scalar(select(OutreachDraft).where(OutreachDraft.business_id == business_id))
                            assistant_row = session.scalar(select(AssistantMessage).where(AssistantMessage.business_id == business_id,
                                AssistantMessage.role == 'assistant'))
                            user_message = session.scalar(select(AssistantMessage).where(AssistantMessage.business_id == business_id,
                                AssistantMessage.role == 'user'))
                            current_hashes = {row.id: hashlib.sha256(row.report_json.encode()).hexdigest()
                                for row in session.scalars(select(ResearchReportRecord).where(ResearchReportRecord.business_id == business_id))}
                            notes_count = session.scalar(select(func.count()).select_from(LeadNote).where(LeadNote.business_id == business_id))
                            lists_count = session.scalar(select(func.count()).select_from(LeadListItem).where(LeadListItem.business_id == business_id))
                            message_count = session.scalar(select(func.count()).select_from(AssistantMessage).where(AssistantMessage.business_id == business_id))
                            tool_count = session.scalar(select(func.count()).select_from(AssistantToolRun).where(AssistantToolRun.business_id == business_id))
                            audit_actions = set(session.scalars(select(AuditEvent.action).where(AuditEvent.business_id == business_id)))
                            assert session.get(User, user_id).email_verified_at is not None
                            assert profile_row.goals == 'Review delivery information with the team'
                            assert profile_row.source_classification == 'OWNER_PROVIDED_UNVERIFIED'
                            assert session.get(Business, business_id).name == business_name
                            assert len(task_rows) == 2 and any(row.source_report_id == latest_id and row.status == 'done' for row in task_rows)
                            assert any(row.source_lead_id == lead_id and row.status == 'open' for row in task_rows)
                            assert notes_count == lists_count == 1
                            assert draft_row.version == 2 and draft_row.status == 'draft' and draft_row.provenance == 'merchant_edited'
                            assert session.get(Lead, lead_id).status == 'qualified'
                            assert current_hashes == original_report_hashes
                            assert assistant_row.status == 'blocked' and assistant_row.error_code == 'private_analysis_not_authorized'
                            assert user_message.content == question and '\r' not in draft_row.body
                            assert json.loads(assistant_row.result_json) == {} and message_count == 2 and tool_count == 5
                            assert {'business.profile_updated', 'task.created', 'task.updated', 'lead.qualified'} <= audit_actions
                            assert session.scalar(select(func.count()).select_from(FoundingGrant).where(FoundingGrant.user_id == user_id)) == 1
                            isolated_counts = {model.__tablename__: session.scalar(select(func.count()).select_from(model).where(model.business_id == second_id))
                                for model in (ResearchReportRecord, Lead, BusinessProfile, Task, AssistantConversation)}
                            assert all(value == 0 for value in isolated_counts.values())
                        assert not page_errors and not network_failures and not forbidden_requests, (page_errors, network_failures, forbidden_requests)
                        checks.append({'width': width, 'market': market, 'status': 'passed',
                            'flows': ['register_verify_fixture_outbox', 'profile_name_offer_audience_goals',
                                'library_filter_source_inspection_snapshot_comparison', 'source_linked_task_completion',
                                'prospect_list_add_qualification_note', 'sourced_draft_review_without_send',
                                'lead_followup_task', 'conversation_workspace_reads_blocked_private_ai',
                                'logout_relogin_reopen', 'workspace_switch_isolation_and_return', 'audit_activity'],
                            'http_checks': http_checks, 'screen_checks': screen_checks,
                            'keyboard_navigation': 'focused research navigation link and Enter followed its destination',
                            'database_checks': {'verified_user': True, 'saved_profile_version': profile_row.version,
                                'source_classification': profile_row.source_classification, 'immutable_saved_reports': 2,
                                'task_count': 2, 'source_linked_task_status': 'done', 'lead_followup_status': 'open',
                                'lead_status': 'qualified', 'list_item_count': lists_count, 'note_count': notes_count,
                                'draft_status': draft_row.status, 'draft_version': draft_row.version,
                                'assistant_message_count': message_count, 'assistant_tool_run_count': tool_count,
                                'assistant_status': assistant_row.status, 'assistant_error_code': assistant_row.error_code,
                                'browser_multiline_forms_saved_as_lf': True,
                                'assistant_generated_result': False, 'audit_action_types': sorted(audit_actions),
                                'founding_grants_for_account': 1, 'second_workspace_record_counts': isolated_counts},
                            'page_errors': page_errors, 'network_failures': network_failures,
                            'forbidden_browser_requests': forbidden_requests})
                        print(json.dumps({'width': width, 'market': market, 'status': 'passed'}), flush=True)
                    finally:
                        browser_context.close()
            finally:
                browser.close()
        assert counters == {'blocked_private_analysis_attempts': 3, 'unexpected_source_factory_calls': 0}, counters
        result = {'timestamp': datetime.now(timezone.utc).isoformat(), 'mode': 'offline_fixture_merchant_browser',
            'story': 'Merchant account → profile → saved evidence → internal work and prospect drafts → bounded workspace reads → persistent reopening and tenant isolation.',
            'database': 'actual_local_postgresql_disposable_schema', 'migration_revision': migration,
            'signing_and_encryption': 'fresh synthetic ephemeral keys; never recorded',
            'provider_network_calls': 0, 'source_acquisition': 'two offline snapshots and one organization fixture seeded through validated local services and DB',
            'ai': 'deterministic saved-record reads; explicit fixture private-policy denial; no model response generated',
            'mail_delivery': 'fixture encrypted outbox verification link only; no delivered mail',
            'external_operations': 'none: no send, provider write, payment, reply or sale',
            'live_provider_verified': False, 'screenshots': 'none; receipt records actual interactions and DB assertions',
            'counters': counters, 'checks': checks}
    finally:
        if server:
            server.should_exit = True
        if thread:
            thread.join(10)
            if thread.is_alive():
                server.force_exit = True
                thread.join(5)
        listener.close()
        if mod:
            mod.engine.dispose()
        if schema_created:
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()
    assert result is not None
    result['cleanup'] = {'loopback_server_stopped': not thread.is_alive(), 'disposable_schema_removed': True}
    assert result['cleanup']['loopback_server_stopped']
    RECEIPT.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'widths': [width for width, _ in WIDTHS],
        'provider_network_calls': 0, 'receipt': str(RECEIPT.relative_to(ROOT)), 'cleanup': result['cleanup']}))


if __name__ == '__main__':
    main()
