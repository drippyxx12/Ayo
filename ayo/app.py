"""Ayo alpha: real accounts, Shopify merchant OAuth, live read-only sync.

Not production-hardened: email verification, billing, queued sync, distributed rate
limits, compliance review, migrations, monitoring and third-party audits remain.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from ayo.database import make_engine, session_factory
from ayo.models import Base, User, Shop, Snapshot, AuthSession
from ayo.identity import IdentityService, token_hash
from ayo.money import display_minor, minor_units
from ayo.public_research import prepare_public_research
from ayo.website_research import SiteInputError

ROOT = Path(__file__).resolve().parent.parent
ENV = os.getenv('ENVIRONMENT', 'development')
PREVIEW_MODE = os.getenv('AYO_PREVIEW_MODE') == '1'
ORIGIN = os.getenv('APP_ORIGIN', 'http://localhost:8000').rstrip('/')
SHOPIFY_ID = os.getenv('SHOPIFY_CLIENT_ID', '')
SHOPIFY_SECRET = os.getenv('SHOPIFY_CLIENT_SECRET', '')
SHOPIFY_API_VERSION = os.getenv('SHOPIFY_API_VERSION', '2026-10')
SCOPES = 'read_products,read_orders'
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{ROOT / "ayo.db"}')
SESSION_SECRET = os.getenv('SESSION_SECRET', '')
ENCRYPTION_KEY = os.getenv('TOKEN_ENCRYPTION_KEY', '')
if ENV == 'production':
    if not ORIGIN.startswith('https://'):
        raise RuntimeError('APP_ORIGIN must use HTTPS in production')
    if len(SESSION_SECRET) < 32 or not ENCRYPTION_KEY or 'REPLACE_' in ENCRYPTION_KEY:
        raise RuntimeError('Missing production session secret / Fernet key')
    if DATABASE_URL.startswith('sqlite:'):
        raise RuntimeError('SQLite is not supported for production deployment')
if not SESSION_SECRET:
    if ENV != 'test':
        print('WARNING: ephemeral session signing key; set SESSION_SECRET before real use.')
    SESSION_SECRET = secrets.token_urlsafe(48)
if not ENCRYPTION_KEY:
    if ENV != 'test':
        print('WARNING: ephemeral encryption key; set TOKEN_ENCRYPTION_KEY before real use.')
    ENCRYPTION_KEY = Fernet.generate_key().decode()
fernet = Fernet(ENCRYPTION_KEY.encode())

engine = make_engine(DATABASE_URL)
DbSession = session_factory(engine)
# Legacy offline fixtures initialize only their isolated test schema. Every
# development/staging/production database is managed explicitly by Alembic.
if ENV == 'test':
    Base.metadata.create_all(engine)
app = FastAPI(title='Ayo — Real Merchant Alpha', docs_url=None if ENV == 'production' else '/api-docs')
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, session_cookie='ayo_session', max_age=60*60*24*7, same_site='lax', https_only=ORIGIN.startswith('https://'))
app.mount('/static', StaticFiles(directory=str(ROOT / 'static')), name='static')
TEMPLATE = Environment(loader=FileSystemLoader(str(ROOT / 'templates')), autoescape=select_autoescape(['html']))
TEMPLATE.globals['preview_mode'] = PREVIEW_MODE


@app.middleware('http')
async def security_headers(request: Request, call_next):
    if PREVIEW_MODE and request.url.path not in {'/', '/research'} and not request.url.path.startswith('/static/'):
        response = HTMLResponse(TEMPLATE.get_template('preview_unavailable.html').render(), status_code=503)
    else:
        response = await call_next(request)
    # Dynamic pages contain account data, CSRF values or authorization responses.
    # Keep these out of browser history caches and shared intermediary caches.
    if not request.url.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['Pragma'] = 'no-cache'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data:; style-src 'self'"
    if ORIGIN.startswith('https://'):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


def db():
    with DbSession() as sess:
        yield sess


def render(request, name, **context):
    if 'csrf' not in request.session:
        request.session['csrf'] = secrets.token_urlsafe(32)
    return HTMLResponse(TEMPLATE.get_template(name).render(request=request, csrf=request.session['csrf'], **context))


def form_guard(request: Request, csrf: str):
    expected = request.session.get('csrf')
    if (not isinstance(expected, str) or not expected or
            not isinstance(csrf, str) or not csrf or
            not secrets.compare_digest(csrf.encode('utf-8'), expected.encode('utf-8'))):
        raise HTTPException(403, 'Invalid request verification')
    # CSRF token is sufficient, and origin checked for browsers that send it.
    origin = request.headers.get('origin')
    if origin and origin.rstrip('/') != ORIGIN:
        raise HTTPException(403, 'Incorrect origin')


def password_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return 'scrypt$' + salt.hex() + '$' + digest.hex()


def password_verify(password, encoded):
    try:
        _, salt, encoded_digest = encoded.split('$')
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
        return secrets.compare_digest(digest, bytes.fromhex(encoded_digest))
    except (ValueError, TypeError):
        return False


def session_user(request, sess):
    return IdentityService(sess).resolve_session(request.session.get('sid'))


def must_user(request, sess):
    user = session_user(request, sess)
    if not user:
        raise HTTPException(401, 'Sign in required')
    return user


def private_insight(request, sess, message=None):
    record = IdentityService(sess).session_record(request.session.get('sid'))
    if record is None:
        return None
    if message is not None:
        record.flash_json = json.dumps({'insight': message})
        sess.commit()
        return None
    value = json.loads(record.flash_json).get('insight') if record.flash_json else None
    record.flash_json = None
    sess.commit()
    return value


def shop_domain(shop: str):
    shop = shop.strip().lower()
    # STRICT allowlist prevents token exchange SSRF / user-supplied host injection.
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,62}\.myshopify\.com', shop):
        raise HTTPException(400, 'Enter a valid .myshopify.com store domain')
    return shop


def oauth_valid(params):
    supplied = params.get('hmac', '')
    if not isinstance(supplied, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', supplied):
        return False
    signed = '&'.join(f'{k}={v}' for k, v in sorted(params.items()) if k not in ('hmac', 'signature'))
    expected = hmac.new(SHOPIFY_SECRET.encode(), signed.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied.lower(), expected)


def webhook_valid(body: bytes, signature: str):
    if not SHOPIFY_SECRET or not signature:
        return False
    digest = base64.b64encode(hmac.new(SHOPIFY_SECRET.encode(), body, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(digest, signature)


@app.get('/', response_class=HTMLResponse)
def landing(request: Request, sess: Session = Depends(db)):
    return render(request, 'landing.html', user=session_user(request, sess), values={})


@app.post('/research/intake', response_class=HTMLResponse)
def public_research(
    request: Request,
    query: str = Form(''),
    country: str = Form(''),
    city: str = Form(''),
    no_website: bool = Form(False),
    owner_facts: str = Form(''),
    csrf: str = Form(...),
    sess: Session = Depends(db),
):
    """Public intake only: no fetch, provider call, claim or persistence."""
    form_guard(request, csrf)
    try:
        preview = prepare_public_research(query, country, city, no_website, owner_facts)
    except SiteInputError as exc:
        response = render(request, 'landing.html', user=session_user(request, sess), values={}, error=str(exc))
        response.status_code = 400
        return response
    response = render(request, 'research.html', user=session_user(request, sess), preview=preview)
    if preview.status in {'search_not_configured', 'secure_fetch_not_configured'}:
        response.status_code = 503
    return response


@app.get('/connections', response_class=HTMLResponse)
def dashboard(request: Request, sess: Session = Depends(db)):
    user = session_user(request, sess)
    if not user:
        return RedirectResponse('/login', 303)
    sh = sess.scalar(select(Shop).where(Shop.user_id == user.id))
    snapshot = sess.scalar(select(Snapshot).where(Snapshot.user_id == user.id))
    data = None
    if snapshot and sh and snapshot.domain == sh.domain:
        data = {'name': snapshot.shop_name,
                'currency': snapshot.currency,
                'product_count': snapshot.product_count,
                'paid_order_count': snapshot.paid_order_count,
                'paid_order_value': display_minor(snapshot.paid_order_value_minor, snapshot.currency),
                'daily': json.loads(snapshot.paid_order_days),
                'products': json.loads(snapshot.products_json),
                'synced_at': datetime.fromtimestamp(snapshot.synced_at, timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
                'limited': bool(snapshot.orders_limited or snapshot.products_limited)}
    insight = private_insight(request, sess)
    return render(request, 'dashboard.html', user=user, shop=sh, data=data, insight=insight, shopify_available=bool(SHOPIFY_ID and SHOPIFY_SECRET))


@app.post('/shopify/connect')
def shopify_connect(request: Request, shop: str = Form(...), csrf: str = Form(...), sess: Session = Depends(db)):
    user = must_user(request, sess)
    form_guard(request, csrf)
    IdentityService(sess).require_verified_user(user.id)
    if not SHOPIFY_ID or not SHOPIFY_SECRET:
        raise HTTPException(503, 'Shopify credentials not yet configured on Ayo server')
    domain = shop_domain(shop)
    existing = sess.scalar(select(Shop).where(Shop.domain == domain))
    if existing and existing.user_id != user.id:
        raise HTTPException(409, 'Store already linked to another account')
    state = secrets.token_urlsafe(32)
    record = IdentityService(sess).session_record(request.session.get('sid'))
    record.oauth_state_hash = token_hash(state)
    record.oauth_shop = domain
    record.oauth_started_at = time.time()
    sess.commit()
    redirect_uri = f'{ORIGIN}/shopify/callback'
    params = urlencode({'client_id': SHOPIFY_ID, 'scope': SCOPES, 'redirect_uri': redirect_uri, 'state': state})
    return RedirectResponse(f'https://{domain}/admin/oauth/authorize?{params}', 303)


@app.get('/shopify/callback')
async def shopify_callback(request: Request, sess: Session = Depends(db)):
    user = must_user(request, sess)
    if not SHOPIFY_ID or not SHOPIFY_SECRET:
        raise HTTPException(503, 'Shopify credentials missing')
    params = dict(request.query_params)
    if len(list(request.query_params.multi_items())) != len(params):
        raise HTTPException(400, 'Duplicate authorization parameters are not supported')
    shop = shop_domain(params.get('shop', ''))
    if not oauth_valid(params):
        raise HTTPException(403, 'Invalid Shopify signature')
    try:
        stamp = int(params.get('timestamp', '0'))
    except ValueError:
        raise HTTPException(400, 'Invalid Shopify timestamp')
    if abs(time.time() - stamp) > 300:
        raise HTTPException(403, 'Expired Shopify authorization response')
    # Read and consume under a database row lock, never from replayable cookies.
    record = sess.scalar(select(AuthSession).where(
        AuthSession.token_hash == token_hash(request.session.get('sid', ''))).with_for_update())
    state_hash, session_shop, started = (record.oauth_state_hash, record.oauth_shop, record.oauth_started_at) if record else (None, None, None)
    if record:
        record.oauth_state_hash = record.oauth_shop = record.oauth_started_at = None
    sess.commit()
    if not state_hash or not secrets.compare_digest(state_hash, token_hash(params.get('state', ''))) or session_shop != shop or not started or time.time() - started > 600:
        raise HTTPException(403, 'Shopify authorization state expired or mismatched')
    code = params.get('code')
    if not code:
        raise HTTPException(400, 'Shopify authorization was not completed')
    existing = sess.scalar(select(Shop).where(Shop.domain == shop))
    if existing and existing.user_id != user.id:
        raise HTTPException(409, 'Store linked to another account')
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(f'https://{shop}/admin/oauth/access_token', data={
            'client_id': SHOPIFY_ID, 'client_secret': SHOPIFY_SECRET, 'code': code, 'expiring': '1'},
            headers={'Accept': 'application/json'})
    if resp.status_code != 200:
        raise HTTPException(502, 'Shopify rejected access token exchange')
    body = resp.json()
    granted = set(str(body.get('scope', '')).split(','))
    if not set(SCOPES.split(',')).issubset(granted):
        raise HTTPException(403, 'Shopify did not grant all required read-only permissions')
    if not body.get('access_token') or not body.get('refresh_token'):
        raise HTTPException(502, 'Expiring offline Shopify token not provided')
    now = time.time()
    row = existing or Shop(user_id=user.id, domain=shop)
    row.user_id = user.id
    row.token_cipher = fernet.encrypt(body['access_token'].encode()).decode()
    row.refresh_cipher = fernet.encrypt(body['refresh_token'].encode()).decode()
    row.token_expires_at = now + int(body.get('expires_in', 3600))
    row.refresh_expires_at = now + int(body.get('refresh_token_expires_in', 7776000))
    row.granted_scopes = body.get('scope', '')
    sess.add(row)
    sess.commit()
    return RedirectResponse('/connections?connected=1', 303)


async def fresh_token(sh: Shop, sess: Session):
    # Serialize rotation across PostgreSQL workers, re-reading the winning token.
    sess.refresh(sh, with_for_update=True)
    now = time.time()
    if sh.token_expires_at and sh.token_expires_at > now + 120:
        return fernet.decrypt(sh.token_cipher.encode()).decode()
    if not sh.refresh_cipher or (sh.refresh_expires_at and sh.refresh_expires_at < now):
        raise HTTPException(403, 'Shopify authentication expired. Reconnect the store.')
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(f'https://{sh.domain}/admin/oauth/access_token', data={
            'client_id': SHOPIFY_ID, 'client_secret': SHOPIFY_SECRET,
            'grant_type': 'refresh_token',
            'refresh_token': fernet.decrypt(sh.refresh_cipher.encode()).decode()},
            headers={'Accept': 'application/json'})
    if resp.status_code != 200:
        raise HTTPException(502, 'Unable to refresh Shopify authorization. Reconnect the store.')
    body = resp.json()
    if not body.get('access_token') or not body.get('refresh_token'):
        raise HTTPException(502, 'Shopify token rotation response incomplete')
    sh.token_cipher = fernet.encrypt(body['access_token'].encode()).decode()
    sh.refresh_cipher = fernet.encrypt(body['refresh_token'].encode()).decode()
    sh.token_expires_at = now + int(body.get('expires_in', 3600))
    sh.refresh_expires_at = now + int(body.get('refresh_token_expires_in', 7776000))
    sess.add(sh)
    sess.commit()
    return body['access_token']


async def gql(shop: str, token: str, query: str, variables: dict | None = None):
    async with httpx.AsyncClient(timeout=35.0) as client:
        resp = await client.post(f'https://{shop}/admin/api/{SHOPIFY_API_VERSION}/graphql.json',
                                 json={'query': query, 'variables': variables or {}},
                                 headers={'X-Shopify-Access-Token': token, 'Content-Type': 'application/json'})
    if resp.status_code == 401:
        raise HTTPException(403, 'Shopify access revoked. Reconnect this store.')
    if resp.status_code != 200:
        raise HTTPException(502, f'Shopify API failed (HTTP {resp.status_code}).')
    body = resp.json()
    if body.get('errors'):
        # Do not leak external details or protected fields into browser responses.
        raise HTTPException(502, 'Shopify rejected the data query. Check scopes and protected-data approval.')
    return body.get('data', {})


SHOP_QUERY = 'query { shop { name currencyCode } }'
PRODUCT_QUERY = '''query($cursor:String) { products(first:75, after:$cursor) {
 nodes { id title status totalInventory }
 pageInfo { hasNextPage endCursor }
}}'''
ORDERS_QUERY = '''query($cursor:String) { orders(first:75, after:$cursor, sortKey:CREATED_AT, reverse:true) {
 nodes { id processedAt cancelledAt displayFinancialStatus currentTotalPriceSet { shopMoney { amount currencyCode } } }
 pageInfo { hasNextPage endCursor }
}}'''


async def get_pages(domain, token, query, limit=10):
    nodes = []
    cursor = None
    has_more = False
    for _ in range(limit):
        data = await gql(domain, token, query, {'cursor': cursor})
        root = data.get('products') if 'products' in data else data.get('orders')
        if not root:
            raise HTTPException(502, 'Invalid Shopify response format')
        nodes.extend(root.get('nodes', []))
        page = root.get('pageInfo', {})
        has_more = bool(page.get('hasNextPage'))
        if not has_more:
            break
        cursor = page.get('endCursor')
        if not cursor:
            raise HTTPException(502, 'Incomplete Shopify pagination response')
    return nodes, has_more


@app.post('/shopify/sync')
async def shopify_sync(request: Request, csrf: str = Form(...), sess: Session = Depends(db)):
    user = must_user(request, sess)
    form_guard(request, csrf)
    sh = sess.scalar(select(Shop).where(Shop.user_id == user.id))
    if not sh:
        raise HTTPException(400, 'Connect a store first')
    token = await fresh_token(sh, sess)
    shopdata = await gql(sh.domain, token, SHOP_QUERY)
    shopinfo = shopdata.get('shop', {})
    currency = shopinfo.get('currencyCode')
    if not currency:
        raise HTTPException(502, 'Shopify did not provide store currency')
    products, products_more = await get_pages(sh.domain, token, PRODUCT_QUERY)
    orders, orders_more = await get_pages(sh.domain, token, ORDERS_QUERY)
    total = Decimal('0')
    count = 0
    per_day = defaultdict(lambda: Decimal('0'))
    earliest = time.time() - 60*24*60*60
    for o in orders:
        if o.get('cancelledAt') or o.get('displayFinancialStatus') not in ('PAID', 'PARTIALLY_REFUNDED'):
            continue
        try:
            ts = datetime.fromisoformat(o['processedAt'].replace('Z', '+00:00'))
            if ts.tzinfo is None:
                raise ValueError('Order time lacks timezone')
            if ts.timestamp() < earliest:
                continue
            shop_money = o['currentTotalPriceSet']['shopMoney']
            money = Decimal(str(shop_money['amount']))
            if (shop_money.get('currencyCode') != currency or
                    not money.is_finite() or money < 0):
                raise ValueError('Invalid order money')
            minor_units(money, currency)
            total += money
            count += 1
            per_day[ts.strftime('%Y-%m-%d')] += money
        except (KeyError, ValueError, TypeError, InvalidOperation):
            # Never replace a previous good snapshot with understated or mixed-
            # currency totals after silently dropping malformed paid orders.
            raise HTTPException(502, 'Shopify returned invalid order data. Previous synchronized data was preserved.')
    row = sess.scalar(select(Snapshot).where(Snapshot.user_id == user.id)) or Snapshot(user_id=user.id)
    row.domain = sh.domain
    row.currency = currency
    row.shop_name = shopinfo.get('name', sh.domain)
    row.product_count = len(products)
    row.paid_order_count = count
    try:
        row.paid_order_value_minor = minor_units(total, currency)
    except ValueError:
        raise HTTPException(502, 'Shopify returned invalid monetary precision or range. Previous synchronized data was preserved.')
    row.paid_order_days = json.dumps([{'date': k, 'value': str(v)} for k, v in sorted(per_day.items())])
    row.products_json = json.dumps([{'title': p.get('title', ''), 'inventory': p.get('totalInventory'), 'status': p.get('status')} for p in products[:25]])
    row.orders_limited = int(orders_more)
    row.products_limited = int(products_more)
    row.synced_at = time.time()
    sess.add(row)
    sess.commit()
    return RedirectResponse('/connections?synced=1', 303)


@app.post('/ask/commerce')
def ask_ayo(request: Request, question: str = Form(...), csrf: str = Form(...), sess: Session = Depends(db)):
    """Actual read-tool style business answers over real synchronized aggregates.

    This intentionally uses deterministic calculations, NOT a pretend LLM.
    """
    user = must_user(request, sess)
    form_guard(request, csrf)
    sh = sess.scalar(select(Shop).where(Shop.user_id == user.id))
    snapshot = sess.scalar(select(Snapshot).where(Snapshot.user_id == user.id))
    if not snapshot or not sh or snapshot.domain != sh.domain:
        private_insight(request, sess, 'Connect and synchronize Shopify first. Ayo never invents business answers.')
        return RedirectResponse('/connections#ask-ayo', 303)
    q = question.lower().strip()[:300]
    products = json.loads(snapshot.products_json)
    limited = bool(snapshot.orders_limited or snapshot.products_limited)
    caveat = ' Import is currently incomplete, so this answer covers only fetched records.' if limited else ''
    if any(word in q for word in ['sale', 'revenue', 'money', 'value', 'earn']):
        answer = f'The connected Shopify store returned {snapshot.paid_order_count} eligible paid orders over the available recent period, with current order totals of {snapshot.currency} {display_minor(snapshot.paid_order_value_minor, snapshot.currency)}. This is recorded paid order value, not net profit or audited revenue.'
    elif any(word in q for word in ['stock', 'inventory', 'low', 'restock']):
        low = [p for p in products if p.get('inventory') is not None and p['inventory'] <= 5]
        if low:
            answer = 'Low stock among the imported product preview: ' + '; '.join(f"{p['title']} ({p['inventory']} units)" for p in low[:8]) + '. Confirm sales velocity and reorder constraints before purchasing.'
        else:
            answer = 'No inventory quantity of 5 or fewer appears among the first 25 imported products. This is not a guarantee that the full store has no stock risk.'
    elif any(word in q for word in ['product', 'catalog', 'item', 'sku']):
        answer = f'Shopify returned {snapshot.product_count} products in the last sync. Inventory and status fields are included where authorized. Ayo currently shows the first 25, not the complete product catalog.'
    elif any(word in q for word in ['sync', 'update', 'fresh', 'connect']):
        when = datetime.fromtimestamp(snapshot.synced_at, timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        answer = f'The most recent successful Shopify synchronization for {snapshot.domain} finished at {when}. The next import must be triggered manually in this alpha.'
    elif any(word in q for word in ['profit', 'margin', 'roas', 'ad spend', 'marketing']):
        answer = 'Ayo cannot calculate that accurately from the connected data yet. Shopify order totals and product inventory do not provide costs, advertising spend or proper attribution. Those integrations and cost records must be added before Ayo can make a trustworthy recommendation.'
    else:
        answer = 'I can answer questions about the actual synchronized paid order value, order count, product list, low stock or sync freshness. More capabilities require additional real data sources. This alpha uses deterministic data tools, not a generative AI model.'
    private_insight(request, sess, answer + caveat)
    return RedirectResponse('/connections#ask-ayo', 303)


@app.post('/shopify/disconnect')
def disconnect(request: Request, csrf: str = Form(...), sess: Session = Depends(db)):
    user = must_user(request, sess)
    form_guard(request, csrf)
    sh = sess.scalar(select(Shop).where(Shop.user_id == user.id))
    snap = sess.scalar(select(Snapshot).where(Snapshot.user_id == user.id))
    if sh:
        sess.delete(sh)
    if snap:
        sess.delete(snap)
    sess.commit()
    return RedirectResponse('/connections?disconnected=1', 303)


@app.post('/shopify/webhooks/{topic:path}')
async def shopify_webhook(topic: str, request: Request, sess: Session = Depends(db)):
    body = await request.body()
    if not webhook_valid(body, request.headers.get('X-Shopify-Hmac-Sha256', '')):
        raise HTTPException(401, 'Invalid webhook signature')
    # Topics must be configured on the Shopify app. Verified messages ONLY.
    allowed = {'app/uninstalled', 'shop/redact', 'customers/data_request', 'customers/redact'}
    if topic not in allowed:
        raise HTTPException(404)
    domain = request.headers.get('X-Shopify-Shop-Domain', '').lower()
    if topic in ('app/uninstalled', 'shop/redact'):
        try:
            payload = json.loads(body)
            signed_domain = payload.get('myshopify_domain') if topic == 'app/uninstalled' else payload.get('shop_domain')
        except (ValueError, AttributeError):
            raise HTTPException(400, 'Invalid webhook payload')
        if not isinstance(signed_domain, str) or signed_domain.lower() != domain:
            raise HTTPException(400, 'Signed webhook identity does not match the delivery domain')
        try:
            domain = shop_domain(domain)
        except HTTPException:
            return {'ok': True}
        sh = sess.scalar(select(Shop).where(Shop.domain == domain))
        if sh:
            snap = sess.scalar(select(Snapshot).where(Snapshot.user_id == sh.user_id))
            if snap:
                sess.delete(snap)
            sess.delete(sh)
            sess.commit()
    # This MVP deliberately does not copy any customer personal records.
    # Compliance requests must be reviewed and logged for production operations.
    return {'ok': True}

# The platform owns account/workspace/research routes; existing Shopify handlers
# remain isolated under Connections and their own optional authorization.
from ayo.platform_routes import install_routes
import sys
install_routes(sys.modules[__name__])
