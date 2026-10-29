"""Offline adversarial HTTPS responses; no domains are contacted."""
import asyncio
import hashlib
import socket

import pytest

from ayo.public_http import PublicHTTPResponse
from ayo.research import ResearchError
from ayo.site_control_reader import PROOF_PATH, SiteFileReader


def test_exact_two_requests_and_hashes():
    calls = []
    async def request(url):
        calls.append(url)
        return PublicHTTPResponse(url, 200, {'content-type': 'text/plain; charset=utf-8'},
            b'User-agent: *\nAllow: /\n' if url.endswith('/robots.txt') else b'ayo-site-verification=fixture\r\n')
    proof = asyncio.run(SiteFileReader(request=request).read('fixture-studio.org'))
    assert proof.content_hash == hashlib.sha256(b'ayo-site-verification=fixture').hexdigest()
    assert proof.body_hash == hashlib.sha256(b'ayo-site-verification=fixture\r\n').hexdigest()
    assert calls == ['https://fixture-studio.org/robots.txt', 'https://fixture-studio.org' + PROOF_PATH]


@pytest.mark.parametrize('status,kind,body', [
    (301, 'text/plain', b''), (403, 'text/plain', b''), (429, 'text/plain', b''),
    (200, 'text/html', b'<html>Verification</html>'),
    (200, 'text/plain', b'User-agent: *\nDisallow: /'),
    (200, 'text/plain', b'User-agent: AyoResearch\nDisallow: /.well-known/'),
    (200, 'text/plain', b'User-agent: *\nCrawl-delay: 30'),
    (200, 'text/plain', b'\xff'),
    (200, 'text/plain', b'x' * 65537),
])
def test_robots_failure_never_fetches_file(status, kind, body):
    calls = []
    def request(url):
        calls.append(url)
        return PublicHTTPResponse(url, status, {'content-type': kind, 'location': 'https://other.org'}, body)
    with pytest.raises(ResearchError):
        asyncio.run(SiteFileReader(request=request).read('fixture-studio.org'))
    assert calls == ['https://fixture-studio.org/robots.txt']


@pytest.mark.parametrize('status,headers,body', [
    (301, {'content-type': 'text/plain', 'location': '/elsewhere'}, b'fixture'),
    (302, {'content-type': 'text/plain', 'location': 'https://www.fixture-studio.org'}, b'fixture'),
    (404, {'content-type': 'text/plain'}, b'fixture'),
    (200, {'content-type': 'text/html'}, b'<html>fixture</html>'),
    (200, {'content-type': 'application/json'}, b'"fixture"'),
    (200, {'content-type': 'text/plain', 'content-encoding': 'gzip'}, b'fixture'),
    (200, {'content-type': 'text/plain'}, b'x' * 4097),
])
def test_file_redirect_auth_type_and_size_are_rejected(status, headers, body):
    def request(url):
        return (PublicHTTPResponse(url, 404, {}, b'') if url.endswith('/robots.txt') else
            PublicHTTPResponse(url, status, headers, body))
    with pytest.raises(ResearchError):
        asyncio.run(SiteFileReader(request=request).read('fixture-studio.org'))


def test_redirect_or_host_replacement_from_transport_is_rejected():
    def request(url):
        return PublicHTTPResponse('https://other-fixture.org/robots.txt', 200, {'content-type': 'text/plain'}, b'')
    with pytest.raises(ResearchError):
        asyncio.run(SiteFileReader(request=request).read('fixture-studio.org'))


def test_whole_check_timeout_cancels_inflight_request():
    cancelled = []
    async def request(url):
        try:
            await asyncio.sleep(5)
        finally:
            cancelled.append(url)
    with pytest.raises(ResearchError) as exc:
        asyncio.run(SiteFileReader(request=request, deadline_seconds=.01).read('fixture-studio.org'))
    assert exc.value.code == 'verification_timeout' and len(cancelled) == 1


def test_private_dns_target_is_rejected_before_socket_connect():
    def resolver(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', port))]
    with pytest.raises(ResearchError):
        asyncio.run(SiteFileReader(resolver=resolver).read('fixture-studio.org'))
