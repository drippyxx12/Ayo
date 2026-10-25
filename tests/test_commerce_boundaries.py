import base64
import hashlib
import hmac
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ayo import app as mod
from ayo.markets import verified_payment_amount
from ayo.models import Base, Shop, User
from ayo.money import display_minor, minor_units


@pytest.mark.parametrize(('currency', 'amount', 'minor', 'display'), [
    ('NGN', '8030.50', 803050, '8,030.50'), ('GHS', '123.45', 12345, '123.45'),
    ('JPY', '500', 500, '500'), ('KWD', '1.234', 1234, '1.234'),
])
def test_currency_precision(currency, amount, minor, display):
    assert minor_units(amount, currency) == minor
    assert display_minor(minor, currency) == display


@pytest.mark.parametrize(('amount', 'currency'), [('0.001', 'NGN'), ('1.5', 'JPY'), ('NaN', 'GHS'), ('1e100', 'NGN')])
def test_invalid_money_is_rejected(amount, currency):
    with pytest.raises(ValueError):
        minor_units(amount, currency)


@pytest.mark.parametrize('country,currency,method', [('GH', 'GHS', 'mobile_money'), ('NG', 'NGN', 'bank_transfer')])
def test_pending_local_payments_are_not_collected_cash(country, currency, method):
    event = {'country': country, 'currency': currency, 'method': method, 'state': 'pending', 'verified': True, 'amount': '100', 'receipt_id': 'fixture'}
    assert verified_payment_amount(event) is None
    event['state'] = 'settled'
    assert str(verified_payment_amount(event)) == '100'
    event['verified'] = False
    assert verified_payment_amount(event) is None


def test_unsigned_webhook_header_cannot_redirect_signed_deletion(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, 'SHOPIFY_SECRET', 'offline-webhook-fixture-secret')
    engine = create_engine('sqlite:///' + str(tmp_path / 'webhook.db'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(mod, 'DbSession', factory)
    with factory() as sess:
        user = User(email='fixture@example.org', password_hash='not-used', email_verified_at=time.time())
        sess.add(user)
        sess.flush()
        sess.add(Shop(user_id=user.id, domain='victim-store.myshopify.com', token_cipher='fixture'))
        sess.commit()
    body = b'{"myshopify_domain":"other-store.myshopify.com"}'
    signature = base64.b64encode(hmac.new(mod.SHOPIFY_SECRET.encode(), body, hashlib.sha256).digest()).decode()
    with TestClient(mod.app) as client:
        response = client.post('/shopify/webhooks/app/uninstalled', content=body,
            headers={'X-Shopify-Hmac-Sha256': signature, 'X-Shopify-Shop-Domain': 'victim-store.myshopify.com'})
        assert response.status_code == 400
    with factory() as sess:
        assert sess.scalar(select(Shop)).domain == 'victim-store.myshopify.com'
    engine.dispose()
