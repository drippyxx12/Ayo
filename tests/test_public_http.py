"""Public-only network transport tests; no test opens a socket."""
import asyncio
import threading

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


def test_real_transport_boundary_pins_dns_but_keeps_hostname_identity(monkeypatch):
    from ayo import public_http
    seen = {}

    class Response:
        status = 200

        def getheaders(self):
            return [('Content-Type', 'text/html')]

        def read(self, bound):
            seen['body_bound'] = bound
            return b'<html><p>Public fixture page.</p></html>'

    class Connection:
        sock = None

        def __init__(self, host, port, **kwargs):
            seen.update(host=host, port=port, **kwargs)

        def request(self, method, target, *, headers):
            seen.update(method=method, target=target, headers=headers)

        def getresponse(self):
            return Response()

        def close(self):
            seen['closed'] = True

    monkeypatch.setattr(public_http, '_PinnedConnection', Connection)
    monkeypatch.setenv('HTTPS_PROXY', 'http://operator-proxy:8080')
    client = PublicHTTPClient(resolver=lambda *_args, **_kwargs: rows('93.184.216.34'))
    result = asyncio.run(client.fetch_once('https://merchant.org/catalog'))
    assert result.status == 200 and seen['closed']
    assert seen['address'] == '93.184.216.34' and seen['server_name'] == 'merchant.org'
    assert seen['tls'] is True and seen['proxy'] == ('operator-proxy', 8080)
    assert seen['headers']['Host'] == 'merchant.org'
    assert seen['headers']['Accept-Encoding'] == 'identity'
    assert 'Cookie' not in seen['headers'] and 'Authorization' not in seen['headers']
    assert seen['target'] == '/catalog' and seen['body_bound'] == 1_000_001


def test_cancelling_fetch_closes_blocking_io_instead_of_only_cancelling_future(monkeypatch):
    started, stopped = threading.Event(), threading.Event()

    class Socket:
        def shutdown(self, _how):
            stopped.set()

    def blocking_fetch(_url, control):
        control.sock = Socket()
        started.set()
        assert stopped.wait(2), 'Cancelling must terminate the active blocking read.'
        control.check()

    client = PublicHTTPClient()
    monkeypatch.setattr(client, '_fetch_sync', blocking_fetch)

    async def run():
        task = asyncio.create_task(client.fetch_once('https://merchant.org/'))
        async with asyncio.timeout(1):
            while not started.is_set():
                await asyncio.sleep(0.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stopped.is_set()

    asyncio.run(run())
