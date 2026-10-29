"""Offline-only configuration checks; no real credentials or provider results."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from cryptography.fernet import Fernet
import httpx
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'check-provider-readiness.py'
spec = importlib.util.spec_from_file_location('ayo_provider_readiness', SCRIPT)
readiness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness)


@pytest.fixture
def configured(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith('AYO_') or name in {'GEMINI_API_KEY', 'GEMINI_MODEL', 'FIRECRAWL_API_KEY',
                'SESSION_SECRET', 'TOKEN_ENCRYPTION_KEY', 'DATABASE_URL', 'APP_ORIGIN',
                'RESEND_API_KEY', 'MAIL_FROM'}:
            monkeypatch.delenv(name, raising=False)
    values = {
        'GEMINI_API_KEY': 'offline-fixture-gemini-value',
        'GEMINI_MODEL': 'offline-fixture-model',
        'AYO_GEMINI_BUDGET_MODEL': 'offline-fixture-model',
        'AYO_GEMINI_BUDGET_MAX_INPUT_BYTES': '32768', 'AYO_GEMINI_BUDGET_MAX_OUTPUT_TOKENS': '1500',
        'AYO_GEMINI_BUDGET_THINKING_LEVEL': 'provider_default',
        'FIRECRAWL_API_KEY': 'offline-fixture-firecrawl-value',
        'AYO_PROVIDER_SPEND_AUTHORIZED': '1',
        'AYO_AI_DATA_POLICY': 'reviewed',
        'AYO_RESEARCH_EGRESS_POLICY': 'provider_managed_verified',
        'AYO_RESEARCH_APPROVED_HOSTS': 'merchant.org',
        'AYO_REQUEST_BUDGET_MICROUSD': '100',
        'AYO_REQUEST_CALL_LIMIT': '10',
        'SESSION_SECRET': 'offline-session-fixture-' + 'x' * 32,
        'TOKEN_ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'DATABASE_URL': 'postgresql+psycopg://fixture-user:fixture-password@127.0.0.1/fixture-db',
        'APP_ORIGIN': 'https://ayo.merchant.org',
        'RESEND_API_KEY': 'offline-fixture-mail-value',
        'MAIL_FROM': 'Ayo Test <accounts@merchant.org>',
        'AYO_MAIL_SEND_AUTHORIZED': '1',
    }
    for provider in ('FIRECRAWL', 'GEMINI'):
        values.update({
            f'AYO_{provider}_DAILY_BUDGET_MICROUSD': '1000',
            f'AYO_{provider}_DAILY_CALL_LIMIT': '100',
            f'AYO_{provider}_SCOPE_DAILY_BUDGET_MICROUSD': '100',
            f'AYO_{provider}_SCOPE_DAILY_CALL_LIMIT': '10',
            f'AYO_{provider}_BUDGET_POLICY_VERSION': 'offline-fixture-v1',
            f'AYO_{provider}_BUDGET_POLICY_VALID_UNTIL': str(int(time.time()) + 3600),
        })
    for operation in ('SEARCH', 'FETCH'):
        values[f'AYO_FIRECRAWL_{operation}_RESERVATION_MICROUSD'] = '10'
    values['AYO_GEMINI_ANALYZE_RESERVATION_MICROUSD'] = '10'
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values


def statuses(result, kind='provider_checks'):
    return {check['id']: check['status'] for check in result[kind]}


def test_offline_preflight_never_connects_or_claims_live_success(configured, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError('Readiness must never issue a network request')
    monkeypatch.setattr(socket.socket, 'connect', fail)
    monkeypatch.setattr(httpx.Client, 'request', fail)
    monkeypatch.setattr(httpx.AsyncClient, 'request', fail)
    result = readiness.check_readiness()
    assert result['provider_configuration_ready']
    assert result['account_journey_configuration_ready']
    assert result['mode'] == 'offline_configuration_only'
    assert result['network_requests_made'] == 0
    assert result['live_verified'] is False
    encoded = json.dumps(result)
    for name in ('GEMINI_API_KEY', 'GEMINI_MODEL', 'FIRECRAWL_API_KEY', 'SESSION_SECRET',
                 'TOKEN_ENCRYPTION_KEY', 'DATABASE_URL', 'APP_ORIGIN', 'RESEND_API_KEY', 'MAIL_FROM'):
        assert configured[name] not in encoded


@pytest.mark.parametrize(('name', 'value', 'check'), [
    ('GEMINI_API_KEY', '', 'gemini_credential'),
    ('GEMINI_API_KEY', 'bad\ncredential', 'gemini_credential'),
    ('GEMINI_API_KEY', 'REPLACE_WITH_API_KEY', 'gemini_credential'),
    ('FIRECRAWL_API_KEY', ' key with spaces ', 'firecrawl_credential'),
    ('GEMINI_MODEL', '../../foreign/path', 'gemini_model'),
    ('AYO_PROVIDER_SPEND_AUTHORIZED', '0', 'spend_authorization'),
    ('AYO_AI_DATA_POLICY', '', 'ai_data_policy'),
    ('AYO_RESEARCH_EGRESS_POLICY', '', 'source_egress_policy'),
    ('AYO_RESEARCH_APPROVED_HOSTS', '*.merchant.org', 'approved_source_hosts'),
    ('AYO_RESEARCH_APPROVED_HOSTS', 'localhost', 'approved_source_hosts'),
    ('AYO_RESEARCH_APPROVED_HOSTS', '127.0.0.1', 'approved_source_hosts'),
    ('AYO_RESEARCH_APPROVED_HOSTS', 'https://merchant.org/', 'approved_source_hosts'),
    ('AYO_RESEARCH_APPROVED_HOSTS', 'merchant.org,', 'approved_source_hosts'),
    ('AYO_GEMINI_ANALYZE_RESERVATION_MICROUSD', 'NaN', 'gemini_analyze_budget'),
    ('AYO_GEMINI_ANALYZE_RESERVATION_MICROUSD', '101', 'gemini_analyze_budget'),
    ('AYO_GEMINI_BUDGET_POLICY_VALID_UNTIL', '1', 'gemini_analyze_budget'),
    ('AYO_FIRECRAWL_SCOPE_DAILY_CALL_LIMIT', '0', 'firecrawl_search_budget'),
])
def test_preflight_fails_closed_without_echoing_bad_configuration(configured, monkeypatch, name, value, check):
    monkeypatch.setenv(name, value)
    result = readiness.check_readiness()
    assert not result['provider_configuration_ready']
    assert not result['account_journey_configuration_ready']
    assert statuses(result)[check] == 'blocked'
    assert result['live_verified'] is False
    if len(value) >= 8:
        assert value not in json.dumps(result)


@pytest.mark.parametrize(('name', 'value', 'check'), [
    ('DATABASE_URL', 'sqlite://', 'postgres_configuration'),
    ('SESSION_SECRET', 'short', 'durable_session_secret'),
    ('TOKEN_ENCRYPTION_KEY', 'REPLACE_WITH_FERNET_KEY', 'encryption_key'),
    ('APP_ORIGIN', 'http://public.merchant.org', 'application_origin'),
    ('APP_ORIGIN', 'https://user:password@merchant.org', 'application_origin'),
    ('AYO_PREVIEW_MODE', '1', 'merchant_backend_enabled'),
    ('AYO_MAIL_SEND_AUTHORIZED', '0', 'transactional_mail'),
    ('MAIL_FROM', 'accounts@merchant.org\nBcc:other@merchant.org', 'transactional_mail'),
])
def test_provider_readiness_does_not_hide_account_journey_blockers(configured, monkeypatch, name, value, check):
    monkeypatch.setenv(name, value)
    result = readiness.check_readiness()
    assert result['provider_configuration_ready']
    assert not result['account_journey_configuration_ready']
    assert statuses(result, 'application_checks')[check] == 'blocked'


def test_cli_pass_is_configuration_only_and_never_outputs_credentials(configured):
    completed = subprocess.run([sys.executable, str(SCRIPT)], cwd=SCRIPT.parent.parent,
                               capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0
    result = json.loads(completed.stdout)
    assert result['live_verified'] is False
    assert result['network_requests_made'] == 0
    for name in ('GEMINI_API_KEY', 'FIRECRAWL_API_KEY', 'SESSION_SECRET', 'TOKEN_ENCRYPTION_KEY', 'DATABASE_URL'):
        assert configured[name] not in completed.stdout + completed.stderr


def test_cli_reports_disabled_spending_as_blocked(configured):
    env = dict(os.environ, AYO_PROVIDER_SPEND_AUTHORIZED='0')
    completed = subprocess.run([sys.executable, str(SCRIPT)], cwd=SCRIPT.parent.parent,
                               env=env, capture_output=True, text=True, timeout=15)
    assert completed.returncode == 2
    assert statuses(json.loads(completed.stdout))['spend_authorization'] == 'blocked'
    assert not completed.stderr


def prepared(monkeypatch):
    monkeypatch.setenv('AYO_PROVIDER_SPEND_AUTHORIZED', '0')
    monkeypatch.setenv('AYO_MAIL_SEND_AUTHORIZED', '0')


def test_prepare_mode_passes_with_disabled_switches_without_calls_or_secret_output(configured, monkeypatch):
    prepared(monkeypatch)
    def fail(*_args, **_kwargs):
        raise AssertionError('Preparation must never contact a network or database service')
    monkeypatch.setattr(socket.socket, 'connect', fail)
    monkeypatch.setattr(socket, 'getaddrinfo', fail)
    monkeypatch.setattr(httpx.Client, 'request', fail)
    monkeypatch.setattr(httpx.AsyncClient, 'request', fail)
    result = readiness.check_readiness('prepare')
    assert result['readiness_mode'] == 'prepare'
    assert result['provider_preparation_ready'] and result['account_preparation_ready']
    assert result['provider_configuration_ready'] and result['account_journey_configuration_ready']
    assert result['live_verified'] is False and result['network_requests_made'] == 0
    assert os.getenv('AYO_PROVIDER_SPEND_AUTHORIZED') == '0'
    assert os.getenv('AYO_MAIL_SEND_AUTHORIZED') == '0'
    encoded = json.dumps(result)
    for name in ('GEMINI_API_KEY', 'GEMINI_MODEL', 'FIRECRAWL_API_KEY', 'SESSION_SECRET',
                 'TOKEN_ENCRYPTION_KEY', 'DATABASE_URL', 'APP_ORIGIN', 'RESEND_API_KEY', 'MAIL_FROM'):
        assert configured[name] not in encoded


@pytest.mark.parametrize(('name', 'value', 'check'), [
    ('AYO_PROVIDER_SPEND_AUTHORIZED', '1', 'provider_spending_disabled'),
    ('AYO_MAIL_SEND_AUTHORIZED', '1', 'mail_delivery_disabled'),
    ('AYO_PROVIDER_SPEND_AUTHORIZED', '', 'provider_spending_disabled'),
    ('AYO_MAIL_SEND_AUTHORIZED', '', 'mail_delivery_disabled'),
])
def test_prepare_mode_requires_both_switches_explicitly_disabled(configured, monkeypatch, name, value, check):
    prepared(monkeypatch)
    monkeypatch.setenv(name, value)
    result = readiness.check_readiness('prepare')
    assert not result['provider_preparation_ready'] and not result['account_preparation_ready']
    assert statuses(result)[check] == 'blocked'
    assert result['live_verified'] is False


def test_provider_preparation_does_not_require_account_or_mail_configuration(configured, monkeypatch):
    prepared(monkeypatch)
    for name in ('RESEND_API_KEY', 'MAIL_FROM', 'DATABASE_URL', 'SESSION_SECRET', 'TOKEN_ENCRYPTION_KEY', 'APP_ORIGIN'):
        monkeypatch.delenv(name)
    result = readiness.check_readiness('prepare')
    assert result['provider_preparation_ready']
    assert not result['account_preparation_ready']
    assert statuses(result, 'application_checks')['transactional_mail_configuration'] == 'blocked'
    assert statuses(result)['mail_delivery_disabled'] == 'configured'


@pytest.mark.parametrize('scope', ['provider', 'account'])
def test_prepare_cli_is_offline_and_leaves_delivery_switches_disabled(configured, monkeypatch, scope):
    prepared(monkeypatch)
    completed = subprocess.run([sys.executable, str(SCRIPT), '--mode', 'prepare', '--scope', scope],
                               cwd=SCRIPT.parent.parent, capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0
    result = json.loads(completed.stdout)
    assert result['readiness_mode'] == 'prepare' and result['live_verified'] is False
    assert result['network_requests_made'] == 0
    assert os.getenv('AYO_PROVIDER_SPEND_AUTHORIZED') == '0'
    assert os.getenv('AYO_MAIL_SEND_AUTHORIZED') == '0'
    assert all(configured[name] not in completed.stdout + completed.stderr for name in (
        'GEMINI_API_KEY', 'GEMINI_MODEL', 'FIRECRAWL_API_KEY', 'DATABASE_URL', 'TOKEN_ENCRYPTION_KEY', 'RESEND_API_KEY'))


def test_provider_scope_cli_distinguishes_provider_prep_from_account_prep(configured, monkeypatch):
    prepared(monkeypatch)
    monkeypatch.delenv('RESEND_API_KEY')
    command = [sys.executable, str(SCRIPT), '--mode', 'prepare']
    for scope, expected in [('provider', 0), ('account', 2)]:
        completed = subprocess.run([*command, '--scope', scope], cwd=SCRIPT.parent.parent,
                                   capture_output=True, text=True, timeout=15)
        assert completed.returncode == expected
        assert not completed.stderr
        result = json.loads(completed.stdout)
        assert result['provider_preparation_ready']
        assert not result['account_preparation_ready']


def test_armed_mode_never_masquerades_as_safe_preparation(configured):
    result = readiness.check_readiness('armed')
    assert result['provider_configuration_ready']
    assert result['account_journey_configuration_ready']
    assert result['provider_preparation_ready'] is False
    assert result['account_preparation_ready'] is False


def test_unknown_readiness_mode_is_rejected_without_configuration_values(configured):
    with pytest.raises(ValueError, match='Select prepare or armed readiness mode'):
        readiness.check_readiness('unreviewed-mode')
