"""Hosted preview allows real intake but cannot collect account credentials."""
import re

import pytest
from fastapi.testclient import TestClient

from ayo import app as mod


@pytest.fixture
def preview_client(monkeypatch):
    monkeypatch.setattr(mod, 'PREVIEW_MODE', True)
    monkeypatch.setitem(mod.TEMPLATE.globals, 'preview_mode', True)
    with TestClient(mod.app, base_url='http://testserver') as client:
        yield client


@pytest.mark.parametrize(('method', 'path'), [
    ('GET', '/signup'), ('POST', '/signup'), ('GET', '/login'),
    ('POST', '/login'), ('POST', '/shopify/connect'),
    ('POST', '/shopify/webhooks/app/uninstalled'), ('GET', '/dashboard'),
])
def test_preview_blocks_accounts_and_provider_routes(preview_client, method, path):
    response = preview_client.request(method, path)
    assert response.status_code == 503
    assert 'disabled in this preview' in response.text
    assert '<input' not in response.text
    assert response.headers['Cache-Control'] == 'private, no-store'


def test_preview_serves_syne_and_actual_intake_without_signup(preview_client):
    home = preview_client.get('/')
    assert home.status_code == 200
    assert 'Development preview' in home.text
    assert 'href="/signup"' not in home.text
    assert preview_client.get('/static/fonts/syne-variable.ttf').status_code == 200
    token = re.search(r'name="csrf" value="([^"]+)"', home.text).group(1)
    response = preview_client.post('/research', data={'query': 'Preview business', 'csrf': token})
    assert response.status_code == 503
    assert 'data-research-status="search_not_configured"' in response.text
    assert 'href="/signup"' not in response.text
    assert 'Your entered details are not saved' in response.text
