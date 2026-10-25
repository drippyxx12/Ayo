"""Security and money regressions using isolated accounts and offline providers."""
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Also support running this module alone. Other modules may already import app.
os.environ.setdefault('ENVIRONMENT', 'test')
os.environ.setdefault('SESSION_SECRET', 'isolated-regression-session-secret-over-32-characters')
os.environ.setdefault('TOKEN_ENCRYPTION_KEY', Fernet.generate_key().decode())
os.environ.setdefault('APP_ORIGIN', 'http://testserver')
os.environ.setdefault('SHOPIFY_CLIENT_ID', 'test-id')
os.environ.setdefault('SHOPIFY_CLIENT_SECRET', 'test-secret')
_bootstrap_directory = tempfile.TemporaryDirectory(prefix='ayo-security-tests-')
os.environ.setdefault('DATABASE_URL', f'sqlite:///{_bootstrap_directory.name}/bootstrap.db')

from ayo import app as mod


@pytest.fixture
def merchant(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "regressions.db"}',
                           connect_args={'check_same_thread': False})
    mod.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(mod, 'DbSession', sessions)
    monkeypatch.setattr(mod, 'ORIGIN', 'http://testserver')
    with sessions() as sess:
        user = mod.User(email='owner@example.test', password_hash=mod.password_hash('SecurePassword123!'))
        sess.add(user)
        sess.flush()
        user_id = user.id
        sess.add(mod.Shop(user_id=user_id, domain='current-shop.myshopify.com',
                          token_cipher=mod.fernet.encrypt(b'offline-provider-fixture').decode(),
                          token_expires_at=time.time() + 3600, granted_scopes='read_products,read_orders'))
        sess.add(mod.Snapshot(user_id=user_id, domain='current-shop.myshopify.com',
                             currency='NGN', shop_name='Previously synchronized shop', product_count=1,
                             paid_order_count=2, paid_order_value_minor=12345,
                             paid_order_days='[]', products_json='[]', orders_limited=0,
                             products_limited=0, synced_at=1000))
        sess.commit()
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as client:
        token = token_from(client.get('/login'))
        response = client.post('/login', data={'csrf': token, 'email': 'owner@example.test',
                                              'password': 'SecurePassword123!'})
        assert response.status_code == 303
        yield SimpleNamespace(client=client, sessions=sessions, user_id=user_id)
    engine.dispose()


def token_from(response):
    assert response.status_code == 200
    return re.search(r'name="csrf" value="([^"]+)"', response.text).group(1)


@pytest.mark.parametrize('expected,supplied', [(None, ''), ('', ''), ('token', ''), ('token', 'wrong')])
def test_csrf_requires_nonempty_server_token(expected, supplied):
    request = Request({'type': 'http', 'headers': [], 'session': {'csrf': expected}})
    with pytest.raises(HTTPException) as error:
        mod.form_guard(request, supplied)
    assert error.value.status_code == 403


def test_unicode_csrf_is_rejected_without_server_error(merchant):
    response = merchant.client.post('/logout', data={'csrf': 'incorrect-\N{SNOWMAN}'})
    assert response.status_code == 403
    assert merchant.client.get('/connections').status_code == 200


@pytest.mark.parametrize('password', ['short', 'x' * 201])
def test_invalid_login_password_length_never_runs_scrypt(merchant, monkeypatch, password):
    def unexpected_hash(*args):
        pytest.fail('Malformed login input reached password hashing')
    monkeypatch.setattr('ayo.identity.hashlib.scrypt', unexpected_hash)
    response = merchant.client.post('/login', data={
        'csrf': token_from(merchant.client.get('/login')),
        'email': 'owner@example.test', 'password': password})
    assert response.status_code == 200
    assert 'Invalid email or password' in response.text


def test_personalized_pages_are_not_cacheable(merchant):
    response = merchant.client.get('/connections')
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.headers['pragma'] == 'no-cache'


@pytest.mark.parametrize('connection_exists', [True, False])
def test_ask_rejects_stale_or_orphaned_snapshot(merchant, connection_exists):
    with merchant.sessions() as sess:
        snapshot = sess.scalar(select(mod.Snapshot).where(mod.Snapshot.user_id == merchant.user_id))
        snapshot.domain = 'former-shop.myshopify.com'
        if not connection_exists:
            sess.delete(sess.scalar(select(mod.Shop).where(mod.Shop.user_id == merchant.user_id)))
        sess.commit()
    response = merchant.client.post('/ask/commerce', data={
        'csrf': token_from(merchant.client.get('/connections')), 'question': 'What is revenue?'})
    assert response.status_code == 303
    html = merchant.client.get('/connections').text
    assert 'never invents business answers' in html
    assert '123.45' not in html


def order(amount='100.50', currency='NGN', **changes):
    result = {'processedAt': datetime.now(timezone.utc).isoformat(), 'cancelledAt': None,
              'displayFinancialStatus': 'PAID', 'currentTotalPriceSet': {
                  'shopMoney': {'amount': amount, 'currencyCode': currency}}}
    result.update(changes)
    return result


def provider_orders(monkeypatch, orders):
    async def gql(*args, **kwargs):
        return {'shop': {'name': 'Offline provider fixture', 'currencyCode': 'NGN'}}
    async def get_pages(domain, token, query, **kwargs):
        assert token == 'offline-provider-fixture'
        return ([] if query == mod.PRODUCT_QUERY else orders), False
    monkeypatch.setattr(mod, 'gql', gql)
    monkeypatch.setattr(mod, 'get_pages', get_pages)


@pytest.mark.parametrize('bad_order', [
    order('NaN'), order('sNaN'), order('Infinity'), order('-Infinity'), order('-0.01'),
    order('100.50', 'GHS'), order('100.50', None), order('invalid'),
    order(processedAt='invalid'), order(processedAt='2026-10-25T03:00:00'),
])
def test_invalid_order_money_preserves_previous_snapshot(merchant, monkeypatch, bad_order):
    provider_orders(monkeypatch, [order(), bad_order])
    response = merchant.client.post('/shopify/sync', data={
        'csrf': token_from(merchant.client.get('/connections'))})
    assert response.status_code == 502
    assert 'Previous synchronized data was preserved' in response.text
    with merchant.sessions() as sess:
        snapshot = sess.scalar(select(mod.Snapshot).where(mod.Snapshot.user_id == merchant.user_id))
        assert snapshot.currency == 'NGN'
        assert snapshot.shop_name == 'Previously synchronized shop'
        assert snapshot.paid_order_count == 2
        assert snapshot.paid_order_value_minor == 12345
        assert snapshot.synced_at == 1000


def test_valid_paid_order_totals_exclude_unpaid_orders(merchant, monkeypatch):
    provider_orders(monkeypatch, [order('100.50'),
                                order('25.25', displayFinancialStatus='PARTIALLY_REFUNDED'),
                                order('invalid', displayFinancialStatus='PENDING')])
    response = merchant.client.post('/shopify/sync', data={
        'csrf': token_from(merchant.client.get('/connections'))})
    assert response.status_code == 303
    with merchant.sessions() as sess:
        snapshot = sess.scalar(select(mod.Snapshot).where(mod.Snapshot.user_id == merchant.user_id))
        assert snapshot.paid_order_count == 2
        assert snapshot.paid_order_value_minor == 12575
