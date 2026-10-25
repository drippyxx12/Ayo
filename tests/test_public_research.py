"""Anonymous acquisition behavior: honest unavailable states, no fetch or save."""
import base64
import json
import re
import socket

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ayo.public_research import prepare_public_research
from ayo.website_research import SiteInputError


@pytest.fixture
def public_client(monkeypatch):
    from ayo import app as mod

    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    mod.Base.metadata.create_all(test_engine)
    monkeypatch.setattr(mod, "DbSession", sessionmaker(bind=test_engine, expire_on_commit=False))

    def unexpected_network(*args, **kwargs):
        raise AssertionError("Public intake must not make outbound network requests")

    monkeypatch.setattr(socket, "create_connection", unexpected_network)
    monkeypatch.setattr(socket, "getaddrinfo", unexpected_network)
    monkeypatch.setattr(mod.httpx, "AsyncClient", unexpected_network)
    with TestClient(mod.app, base_url="http://testserver", follow_redirects=False) as client:
        yield client, mod
    test_engine.dispose()


def _csrf(client):
    response = client.get("/")
    assert response.status_code == 200
    return re.search(r'name="csrf" value="([^"]+)"', response.text).group(1)


def test_public_home_starts_with_business_search_without_account(public_client):
    client, _ = public_client
    response = client.get("/")
    assert response.status_code == 200
    assert 'action="/research"' in response.text
    assert "Search for your business." in response.text
    assert "I don't have a website" in response.text
    assert "No account required" in response.text
    assert '<option value="NG">Nigeria</option>' in response.text
    assert '<option value="GH">Ghana</option>' in response.text
    assert 'action="/shopify/connect"' not in response.text


@pytest.mark.parametrize(("query", "status"), [
    ("A local clothing business", "search_not_configured"),
    ("https://merchant.org/catalog", "secure_fetch_not_configured"),
    ("https://www.instagram.com/publicbusiness/", "secure_fetch_not_configured"),
])
def test_public_research_reports_unavailable_and_never_fetches(public_client, query, status):
    client, _ = public_client
    response = client.post("/research", data={"csrf": _csrf(client), "query": query, "country": "NG"})
    assert response.status_code == 503
    assert f'data-research-status="{status}"' in response.text
    assert "No public sources have been retrieved" in response.text
    assert "There is no sourced mini-report or verified lead preview yet" in response.text
    assert "Create your free Ayo account" in response.text
    assert "Shopify is optional" in response.text


def test_owner_supplied_profile_is_unverified_ephemeral_and_escaped(public_client):
    client, mod = public_client
    details = 'Handmade dresses <script>alert("untrusted")</script>'
    response = client.post("/research", data={
        "csrf": _csrf(client), "query": "My clothing business", "country": "GH",
        "city": "Accra", "no_website": "true", "owner_facts": details,
    })
    assert response.status_code == 200
    assert 'data-research-status="owner_provided_unverified"' in response.text
    assert "OWNER_PROVIDED_UNVERIFIED" in response.text
    assert "&lt;script&gt;" in response.text
    assert '<script>alert("untrusted")</script>' not in response.text
    assert "Ghana" in response.text and "Accra" in response.text
    assert "not an independent website assessment" in response.text
    assert "has not been saved to an account" in response.text
    cookie_data = client.cookies.get("ayo_session").split(".", 1)[0]
    session = json.loads(base64.b64decode(cookie_data))
    assert set(session) == {"csrf"}
    with mod.DbSession() as sess:
        assert sess.scalar(select(func.count()).select_from(mod.User)) == 0
        assert sess.scalar(select(func.count()).select_from(mod.Shop)) == 0
        assert sess.scalar(select(func.count()).select_from(mod.Snapshot)) == 0
    assert details not in client.get("/").text
    assert client.get("/dashboard").status_code == 303


def test_research_form_rejects_invalid_csrf_and_foreign_origin(public_client):
    client, _ = public_client
    assert client.post("/research", data={"csrf": "wrong", "query": "My shop"}).status_code == 403
    token = _csrf(client)
    response = client.post("/research", data={"csrf": token, "query": "My shop"}, headers={"Origin": "https://unrelated.example"})
    assert response.status_code == 403


@pytest.mark.parametrize("query", [
    "http://127.0.0.1", "http://169.254.169.254/latest/meta-data/",
    "https://user:password@merchant.org", "file:///etc/passwd", "x" * 251,
])
def test_hostile_or_oversized_research_input_is_rejected(public_client, query):
    client, _ = public_client
    response = client.post("/research", data={"csrf": _csrf(client), "query": query})
    assert response.status_code == 400
    assert 'role="alert"' in response.text
    assert "data-research-status" not in response.text


def test_country_is_selected_never_inferred():
    assert prepare_public_research("Ghana-themed clothing in Lagos").country == ""
    assert prepare_public_research("My shop", "NG").country_name == "Nigeria"
    with pytest.raises(SiteInputError, match="Choose Nigeria or Ghana"):
        prepare_public_research("My shop", "US")


@pytest.mark.parametrize("fields", [
    {"query": ""}, {"query": "My shop", "city": "x" * 101},
    {"query": "My shop", "owner_facts": "x" * 2001},
    {"query": "My shop", "no_website": True},
    {"query": "https://merchant.org", "no_website": True, "owner_facts": "Selling clothes"},
    {"query": "My shop", "owner_facts": "Selling clothes"},
    {"query": "My\x00shop"}, {"query": "My shop", "city": "Accra\r\nInjected"},
])
def test_intake_fields_are_bounded_and_unambiguous(fields):
    with pytest.raises(SiteInputError):
        prepare_public_research(**fields)


def test_owner_description_is_labeled_and_normalized_without_fact_inference():
    preview = prepare_public_research("My shop", "GH", "Accra", True, "  Selling clothes\nfor local buyers.  ")
    assert preview.owner_facts == "Selling clothes for local buyers."
    assert preview.source_kind == "OWNER_PROVIDED_UNVERIFIED"
    assert preview.input_kind == "owner_provided"
    assert preview.status == "owner_provided_unverified"
