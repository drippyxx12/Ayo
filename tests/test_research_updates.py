"""Read-only polling privacy and URL intake compatibility, with fake sources."""
import asyncio
import secrets

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from ayo import app as mod
from ayo.jobs import process_one
from ayo.models import ResearchJob
from ayo.public_research import prepare_public_research
from ayo.research import ResearchService
from ayo.research_refresh import RefreshService
from ayo.website_research import SiteInputError, classify_website_input
from test_platform_flow import platform, csrf, FixtureProvider  # noqa: F401
from test_research_workspace import account, saved, report


def test_public_poll_is_capability_scoped_read_only_and_opens_report(platform):
    client = platform.client
    response = client.post('/research', data={'csrf': csrf(client),
        'query': 'https://fixture-clothing.org/', 'country': 'GH'})
    path = response.headers['location']
    updates = path + '/updates'
    first = client.get(updates)
    assert first.status_code == 200 and first.headers['Cache-Control'] == 'private, no-store'
    payload = first.json()
    assert set(payload) == {'revision', 'terminal'} and not payload['terminal']
    assert 'data-research-watch="' + updates in client.get(path).text
    for _ in range(3):
        assert client.get(updates).json() == payload
    with platform.factory() as session:
        assert session.scalar(select(ResearchJob)).attempts == 0
    with TestClient(mod.app, base_url='http://testserver') as foreign:
        assert foreign.get(updates).status_code == 404
    asyncio.run(process_one(platform.factory, mod.fernet, lambda: ResearchService(FixtureProvider())))
    result = client.get(updates).json()
    assert result['terminal'] and result['revision'] != payload['revision']
    final = client.get(path)
    assert final.status_code == 303 and '/research/' in final.headers['location']
    assert client.get(final.headers['location']).status_code == 200


def test_private_refresh_poll_never_exposes_anonymous_capability(platform):
    user, business = account(platform)
    record = saved(platform.factory, user, business, report())
    with platform.factory() as session:
        job = RefreshService(session, mod.fernet).request(user, business, record,
            request_id=secrets.token_urlsafe(24), reviewed=True)
        session.commit()
        job_id = job.id
    path = '/research/library/' + record + '/refresh/' + job_id
    response = platform.client.get(path + '/updates')
    assert response.status_code == 200 and set(response.json()) == {'revision', 'terminal'}
    assert platform.client.get('/research/jobs/' + job_id + '/updates').status_code == 404
    assert platform.client.get(path + '/updates?business_id=foreign').status_code == 400
    other = saved(platform.factory, user, business, report())
    assert platform.client.get(path.replace(record, other) + '/updates').status_code == 404


def test_long_product_url_is_accepted_without_widening_name_or_url_limits():
    url = 'https://shop.example.org/products/' + 'a' * 300
    assert classify_website_input(url).value == url
    assert prepare_public_research(url).query == url
    for query in ('Name ' * 60, 'https://shop.example.org/' + 'a' * 2048):
        with pytest.raises(SiteInputError):
            prepare_public_research(query)
