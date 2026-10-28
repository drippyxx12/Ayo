"""Public-only network transport tests; no test opens a socket."""
import asyncio

import pytest

from ayo.public_http import PublicHTTPClient, PublicHTTPResponse, _public_addresses
from ayo.research import ResearchError


def rows(*addresses):
    return [(2, 1, 6, '', (address, 443)) for address in addresses]


def test_dns_set_must_be_entirely_public_and_never_ipv4_mapped():
    assert _public_addresses('public.test', 443, lambda *_args, **_kwargs: rows('93.184.216.34')) == ('93.184.216.34',)
    for addresses in [('93.184.216.34', '127.0.0.1'), ('10.0.0.1',), ('::ffff:127.0.0.1',), ('169.254.169.254',)]:
        with pytest.raises(ResearchError) as error:
            _public_addresses('unsafe.test', 443, lambda *_args, a=addresses, **_kwargs: rows(*a))
        assert error.value.code == 'provider_unsafe_redirect'


def test_fixture_transport_still_enforces_url_and_body_bounds():
    calls = []
    def request(url):
        calls.append(url)
        return PublicHTTPResponse(url, 200, {'Content-Type': 'text/html'}, b'<h1>Public fixture page</h1>')
    response = asyncio.run(PublicHTTPClient(request=request).fetch_once('https://merchant.org'))
    assert response.url == 'https://merchant.org/'
    assert response.headers == {'content-type': 'text/html'}
    assert calls == ['https://merchant.org/']
    with pytest.raises(Exception):
        asyncio.run(PublicHTTPClient(request=request).fetch_once('http://127.0.0.1/'))
    oversized = lambda url: PublicHTTPResponse(url, 200, {}, b'x' * 11)
    with pytest.raises(ResearchError) as error:
        asyncio.run(PublicHTTPClient(request=oversized, max_body_bytes=10).fetch_once('https://merchant.org'))
    assert error.value.code == 'provider_response_too_large'


def test_fixture_response_url_cannot_be_substituted():
    client = PublicHTTPClient(request=lambda _url: PublicHTTPResponse(
        'https://different.org/', 200, {}, b'Public content'))
    with pytest.raises(ResearchError) as error:
        asyncio.run(client.fetch_once('https://merchant.org/'))
    assert error.value.code == 'provider_malformed'
