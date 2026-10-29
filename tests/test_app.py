import base64
import hashlib
import hmac
import re
import secrets
import time
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from ayo import app as mod
from ayo.database import make_engine, session_factory

client = TestClient(mod.app, base_url='http://testserver', follow_redirects=False)


@pytest.fixture(autouse=True)
def isolated_alpha_database(tmp_path, monkeypatch):
    engine = make_engine('sqlite:///' + str(tmp_path / 'alpha.db'))
    mod.Base.metadata.create_all(engine)
    monkeypatch.setattr(mod, 'DbSession', session_factory(engine))
    monkeypatch.setattr(mod, 'ORIGIN', 'http://testserver')
    monkeypatch.setattr(mod, 'SHOPIFY_ID', 'test-id')
    monkeypatch.setattr(mod, 'SHOPIFY_SECRET', 'test-secret')
    client.cookies.clear()
    yield
    client.cookies.clear()
    engine.dispose()


def csrf(path='/signup'):
    r = client.get(path)
    assert r.status_code == 200
    return re.search(r'name="csrf" value="([^"]+)"', r.text).group(1)


def register(email=None):
    email = email or f'{secrets.token_hex(5)}@example.com'
    token = csrf('/signup')
    r = client.post('/signup', data={'csrf': token, 'email': email, 'password': 'VerySecurePassword123!', 'business_name': 'Test merchant', 'country': 'NG'}, follow_redirects=False)
    assert r.status_code == 303, r.text
    assert r.headers['location'] == '/dashboard'
    # The fixture represents a verified account before provider authorization.
    with mod.DbSession() as sess:
        user = sess.scalar(select(mod.User).where(mod.User.email == email))
        user.email_verified_at = time.time()
        sess.commit()
    return email


def signed_params(shop, state):
    params = {'code': 'legitimate-code', 'shop': shop, 'state': state, 'timestamp': str(int(time.time()))}
    body = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
    params['hmac'] = hmac.new(b'test-secret', body.encode(), hashlib.sha256).hexdigest()
    return params


class FakeResponse:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code
    def json(self):
        return self.body


class MockShopify:
    def __init__(self, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, *_):
        pass
    async def post(self, url, **kwargs):
        if url.endswith('/admin/oauth/access_token'):
            if kwargs['data'].get('grant_type') == 'refresh_token':
                return FakeResponse({'access_token':'fresh-token','refresh_token':'fresh-refresh', 'expires_in':3600,'refresh_token_expires_in':7776000})
            return FakeResponse({'access_token':'real-token-from-shopify','refresh_token':'refresh-from-shopify','scope':'read_products,read_orders', 'expires_in':3600, 'refresh_token_expires_in':7776000})
        payload = kwargs['json']
        if 'shop {' in payload['query']:
            return FakeResponse({'data':{'shop':{'name':'Real Merchant Under Test','currencyCode':'USD'}}})
        if 'products(' in payload['query']:
            return FakeResponse({'data':{'products':{'nodes':[{'id':'gid://shopify/Product/123', 'title':'Actual product from API', 'status':'ACTIVE','totalInventory':12}], 'pageInfo':{'hasNextPage': False, 'endCursor':None}}}})
        if 'orders(' in payload['query']:
            dt = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            return FakeResponse({'data':{'orders':{'nodes':[{'id':'gid://shopify/Order/1','processedAt':dt,'cancelledAt':None, 'displayFinancialStatus':'PAID','currentTotalPriceSet':{'shopMoney':{'amount':'259.50','currencyCode':'USD'}}}], 'pageInfo':{'hasNextPage':False,'endCursor':None}}}})
        raise AssertionError(url)


def test_registration_login_and_csrf():
    email = register()
    assert client.get('/connections').status_code == 200
    assert 'No business data yet.' in client.get('/connections').text
    assert client.post('/logout', data={'csrf':'bad'}).status_code == 403
    assert client.post('/logout', data={'csrf': csrf('/connections')}).status_code == 303
    assert client.get('/connections').status_code == 303
    tok = csrf('/login')
    assert client.post('/login', data={'csrf': tok, 'email':email,'password':'wrongpass'}).status_code == 200
    good = client.post('/login', data={'csrf': csrf('/login'), 'email':email,'password':'VerySecurePassword123!'}, follow_redirects=False)
    assert good.status_code == 303


def test_shop_domain_rejects_ssrf_and_invalid_hmac():
    assert mod.shop_domain('real-store.myshopify.com') == 'real-store.myshopify.com'
    for host in ['https://evil.com', 'foo.myshopify.com.evil.com', '127.0.0.1', 'a.myshopify.com@localhost']:
        try:
            mod.shop_domain(host)
        except Exception:
            pass
        else:
            raise AssertionError(host)
    assert not mod.oauth_valid({'state':'abc', 'hmac':'0'*64})
    assert not mod.webhook_valid(b'hello', 'invalid')


def test_connect_callback_sync_real_source_and_uninstall(monkeypatch):
    register()
    monkeypatch.setattr(mod.httpx, 'AsyncClient', MockShopify)
    tok = csrf('/connections')
    connect = client.post('/shopify/connect', data={'csrf':tok,'shop':'owned-alpha.myshopify.com'})
    assert connect.status_code == 303
    redirect = urlparse(connect.headers['location'])
    assert redirect.netloc == 'owned-alpha.myshopify.com'
    state = parse_qs(redirect.query)['state'][0]
    bad = signed_params('owned-alpha.myshopify.com', 'incorrect')
    assert client.get('/shopify/callback', params=bad).status_code == 403
    # invalid state consumed: new authorization required
    connect = client.post('/shopify/connect', data={'csrf':csrf('/connections'),'shop':'owned-alpha.myshopify.com'})
    state = parse_qs(urlparse(connect.headers['location']).query)['state'][0]
    good = client.get('/shopify/callback', params=signed_params('owned-alpha.myshopify.com', state))
    assert good.status_code == 303
    assert good.headers['location'].startswith('/connections')
    # Replaying a captured browser cookie cannot restore consumed server state.
    assert client.get('/shopify/callback', params=signed_params('owned-alpha.myshopify.com', state)).status_code == 403
    assert 'Import store data' in client.get('/connections').text
    # real API mock returns data; no seeded data or default revenue
    result = client.post('/shopify/sync', data={'csrf':csrf('/connections')})
    assert result.status_code == 303, result.text
    html = client.get('/connections').text
    assert '259.50' in html
    assert 'Actual product from API' in html
    assert 'Real Merchant Under Test' in html
    with mod.DbSession() as sess:
        stored = sess.scalar(select(mod.Shop).where(mod.Shop.domain == 'owned-alpha.myshopify.com'))
        assert stored and stored.token_cipher != 'real-token-from-shopify'
        assert mod.fernet.decrypt(stored.token_cipher.encode()).decode() == 'real-token-from-shopify'
    payload = b'{"shop_id":12345,"myshopify_domain":"owned-alpha.myshopify.com"}'
    sig = base64.b64encode(hmac.new(b'test-secret', payload, hashlib.sha256).digest()).decode()
    badwebhook = client.post('/shopify/webhooks/app/uninstalled', content=payload, headers={'X-Shopify-Hmac-Sha256':'broken','X-Shopify-Shop-Domain':'owned-alpha.myshopify.com'})
    assert badwebhook.status_code == 401
    webhook = client.post('/shopify/webhooks/app/uninstalled', content=payload, headers={'X-Shopify-Hmac-Sha256':sig, 'X-Shopify-Shop-Domain':'owned-alpha.myshopify.com'})
    assert webhook.status_code == 200
    assert 'No business data yet.' in client.get('/connections').text


def test_users_cannot_take_over_other_stores():
    register()
    with mod.DbSession() as sess:
        user = sess.scalar(select(mod.User).order_by(mod.User.id.desc()))
        row = mod.Shop(user_id=user.id, domain='already-taken.myshopify.com',token_cipher='cipher',granted_scopes='read_products')
        sess.add(row)
        sess.commit()
    client.post('/logout', data={'csrf':csrf('/connections')})
    register()
    stolen = client.post('/shopify/connect', data={'csrf':csrf('/connections'),'shop':'already-taken.myshopify.com'})
    assert stolen.status_code == 409


def test_ayo_answers_are_based_on_synced_records_and_provenance():
    register()
    # No connection/data: explicitly refuses to invent business answers.
    r = client.post('/ask/commerce', data={'csrf':csrf('/connections'), 'question':'How much did I make?'}, follow_redirects=False)
    assert r.status_code == 303
    assert 'never invents business answers' in client.get('/connections').text
    # Previous test's store was removed: manually insert a snapshot with known values from sync-like store data.
    from datetime import datetime
    with mod.DbSession() as sess:
        user = sess.scalar(select(mod.User).order_by(mod.User.id.desc()))
        sess.add(mod.Shop(user_id=user.id,domain='query-store.myshopify.com',token_cipher='encrypted',granted_scopes='read_orders,read_products'))
        sess.add(mod.Snapshot(user_id=user.id,domain='query-store.myshopify.com',currency='NGN',shop_name='My Actual Shop',product_count=7,paid_order_count=2,paid_order_value_minor=803050,paid_order_days='[]',products_json='[{"title":"Camera lens","inventory":2,"status":"ACTIVE"}]',orders_limited=0,products_limited=0,synced_at=time.time()))
        sess.commit()
    r=client.post('/ask/commerce', data={'csrf':csrf('/connections'), 'question':'What is low in stock?'}, follow_redirects=False)
    assert r.status_code==303
    assert 'Camera lens (2 units)' in client.get('/connections').text
    r=client.post('/ask/commerce', data={'csrf':csrf('/connections'), 'question':'What is revenue?'}, follow_redirects=False)
    assert r.status_code==303
    assert 'NGN 8,030.50' in client.get('/connections').text
    r=client.post('/ask/commerce', data={'csrf':csrf('/connections'), 'question':'Tell me my ROAS'}, follow_redirects=False)
    assert r.status_code==303
    assert 'cannot calculate that accurately' in client.get('/connections').text
