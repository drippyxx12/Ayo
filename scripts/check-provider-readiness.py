#!/usr/bin/env python3
"""Offline configuration preflight. Never sends credentials or contacts a provider.

A pass means the local configuration is consistent, not that credentials, model
access, source permissions, database connectivity or real workflows are verified.
"""
from __future__ import annotations

import argparse
from email.utils import parseaddr
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

# Support execution by path without importing the ASGI app or reading .env files.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _credential_present(name: str) -> bool:
    from ayo.provider_config import valid_api_key
    return valid_api_key(os.getenv(name, ''))


def _approved_hosts() -> bool:
    from ayo.website_research import normalize_public_url

    hosts = [part.strip().lower() for part in os.getenv('AYO_RESEARCH_APPROVED_HOSTS', '').split(',')]
    if not hosts or not all(hosts):
        return False
    try:
        for host in hosts:
            if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host):
                return False
            parsed = urlsplit(normalize_public_url('https://' + host + '/'))
            if parsed.hostname != host:
                return False
    except (ValueError, TypeError):
        return False
    return True


def _origin() -> bool:
    try:
        value = urlsplit(os.getenv('APP_ORIGIN', ''))
        return (value.scheme == 'https' or
                (value.scheme == 'http' and value.hostname in {'localhost', '127.0.0.1', '::1'})) and bool(
                    value.hostname) and not (value.username or value.password or value.query or value.fragment) and value.path in {'', '/'}
    except ValueError:
        return False


def _fernet_configured() -> bool:
    from cryptography.fernet import Fernet

    try:
        Fernet(os.getenv('TOKEN_ENCRYPTION_KEY', '').encode())
        return True
    except (ValueError, TypeError):
        return False


def check_readiness(mode: str = 'armed') -> dict:
    """Return only fixed check IDs/statuses; no user configuration values."""
    if mode not in {'prepare', 'armed'}:
        raise ValueError('Select prepare or armed readiness mode.')
    checks = []

    def check(identifier: str, passed: bool, detail: str):
        checks.append({'id': identifier, 'status': 'configured' if passed else 'blocked', 'detail': detail})

    check('gemini_credential', _credential_present('GEMINI_API_KEY'), 'Presence and basic syntax only; validity is unverified.')
    from ayo.provider_config import valid_model_id
    check('gemini_model', valid_model_id(os.getenv('GEMINI_MODEL', '')),
          'An explicit server model identifier is required; availability and capability are unverified.')
    check('firecrawl_credential', _credential_present('FIRECRAWL_API_KEY'), 'Presence and basic syntax only; validity is unverified.')
    if mode == 'prepare':
        check('provider_spending_disabled', os.getenv('AYO_PROVIDER_SPEND_AUTHORIZED') == '0',
              'Preparation requires the provider spending switch explicitly disabled; this check never changes it.')
        check('mail_delivery_disabled', os.getenv('AYO_MAIL_SEND_AUTHORIZED') == '0',
              'Preparation requires the mail delivery switch explicitly disabled; no mail credentials are needed for provider-only preparation.')
    else:
        check('spend_authorization', os.getenv('AYO_PROVIDER_SPEND_AUTHORIZED') == '1', 'Enable only after separate owner approval for a bounded real test.')
    check('ai_data_policy', os.getenv('AYO_AI_DATA_POLICY') in {'reviewed', 'public_only_reviewed'}, 'Operator attestation; public-only review does not authorize private analysis. Vendor retention, training and jurisdiction review remain independent evidence.')
    check('source_egress_policy', os.getenv('AYO_RESEARCH_EGRESS_POLICY') == 'provider_managed_verified', 'Operator attestation; it does not independently establish redirect, robots or network safety.')
    check('approved_source_hosts', _approved_hosts(), 'At least one exact public host is required; wildcards, addresses and private targets are rejected.')
    for provider, operation in (('firecrawl', 'search'), ('firecrawl', 'fetch'), ('gemini', 'analyze')):
        try:
            from ayo.budgets import BudgetError, BudgetPolicy
            try:
                BudgetPolicy.from_env(provider, operation)
                valid = True
            except BudgetError:
                valid = False
        except ImportError:
            valid = False
        check(f'{provider}_{operation}_budget', valid, 'A complete, consistent and unexpired reviewed reservation/call policy is required.')
    provider_ready = all(item['status'] == 'configured' for item in checks)

    app_checks = []
    session_secret = os.getenv('SESSION_SECRET', '')
    app_checks.append({'id': 'durable_session_secret', 'status': 'configured' if len(session_secret) >= 32 and not session_secret.startswith('REPLACE_') else 'blocked'})
    app_checks.append({'id': 'encryption_key', 'status': 'configured' if _fernet_configured() else 'blocked'})
    db = os.getenv('DATABASE_URL', '')
    try:
        parsed_db = urlsplit(db)
        pg_configured = parsed_db.scheme in {'postgres', 'postgresql', 'postgresql+psycopg'} and bool(parsed_db.hostname and parsed_db.path.strip('/'))
    except ValueError:
        pg_configured = False
    app_checks.append({'id': 'postgres_configuration', 'status': 'configured' if pg_configured else 'blocked'})
    app_checks.append({'id': 'application_origin', 'status': 'configured' if _origin() else 'blocked'})
    app_checks.append({'id': 'merchant_backend_enabled', 'status': 'blocked' if os.getenv('AYO_PREVIEW_MODE') == '1' else 'configured'})
    sender = os.getenv('MAIL_FROM', '')
    sender_address = parseaddr(sender)[1]
    mail_configured = (_credential_present('RESEND_API_KEY') and not any(c in sender for c in '\r\n') and
                       bool(re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+', sender_address)))
    mail_ready = mail_configured and (mode == 'prepare' or os.getenv('AYO_MAIL_SEND_AUTHORIZED') == '1')
    app_checks.append({'id': 'transactional_mail_configuration' if mode == 'prepare' else 'transactional_mail',
                       'status': 'configured' if mail_ready else 'blocked'})
    account_ready = provider_ready and all(item['status'] == 'configured' for item in app_checks)
    return {
        'schema_version': 1,
        'mode': 'offline_configuration_only',
        'readiness_mode': mode,
        'network_requests_made': 0,
        'live_verified': False,
        'provider_configuration_ready': provider_ready,
        'account_journey_configuration_ready': account_ready,
        'provider_preparation_ready': mode == 'prepare' and provider_ready,
        'account_preparation_ready': mode == 'prepare' and account_ready,
        'provider_checks': checks,
        'application_checks': app_checks,
        'remaining_verification': [
            'Credentials and model access require a separately authorized actual provider request.',
            'Approved sources need documented permission, robots/terms and egress review.',
            'Configured reservations are conservative budget debits, not measured invoice costs.',
            'Database migrations, connectivity, backup/restore, email delivery and end-to-end outcomes are not tested here.',
            'An offline pass never authorizes spending, outreach, merchant writes or deployment.',
            'Preparation mode requires disabled provider and mail switches; armed mode checks existing switch configuration only and never enables it.',
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('prepare', 'armed'), default='armed',
                        help='prepare checks configuration while provider/mail switches remain disabled; armed preserves the original offline readiness check.')
    parser.add_argument('--scope', choices=('provider', 'account'), default='account',
                        help='provider excludes account/database/mail configuration; account checks the complete account journey configuration.')
    args = parser.parse_args()
    result = check_readiness(args.mode)
    print(json.dumps(result, indent=2))
    return 0 if result['provider_configuration_ready' if args.scope == 'provider' else 'account_journey_configuration_ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
