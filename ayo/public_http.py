"""Pinned public-only HTTP transport for one-page website research.

Redirects and robots policy are handled by the caller so each hop is reviewed
before dispatch. This transport resolves every destination, rejects mixed or
special-use address sets, pins one public address, and keeps the original Host
header and TLS server name for certificate verification.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import http.client
import ipaddress
import os
import socket
import ssl
from urllib.parse import urlsplit

from ayo.research import ResearchError
from ayo.website_research import SiteInputError, normalize_public_url


USER_AGENT = 'AyoResearch/0.2 (+https://github.com/drippyxx12/Ayo; single-page public research)'
MAX_BODY_BYTES = 1_000_000


@dataclass(frozen=True)
class PublicHTTPResponse:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes


def _public_addresses(host: str, port: int, resolver=socket.getaddrinfo) -> tuple[str, ...]:
    try:
        rows = resolver(host, port, type=socket.SOCK_STREAM)
        addresses = tuple(dict.fromkeys(row[4][0] for row in rows))
    except (OSError, UnicodeError):
        raise ResearchError('source_unavailable', 'The public website address could not be resolved.', 502) from None
    if not addresses:
        raise ResearchError('source_unavailable', 'The public website address could not be resolved.', 502)
    for value in addresses:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            raise ResearchError('provider_unsafe_redirect', 'The website resolved to an invalid network address.', 403) from None
        if (not address.is_global or address.is_multicast or address.is_unspecified
                or address.is_loopback or address.is_link_local or address.is_private
                or getattr(address, 'ipv4_mapped', None)):
            raise ResearchError('provider_unsafe_redirect', 'The website resolved to a nonpublic network address.', 403)
    return addresses


class _PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host, port, *, address, tls, server_name, context, timeout, proxy=None):
        connect_host, connect_port = proxy or (host, port)
        super().__init__(connect_host, connect_port, timeout=timeout)
        self._address = address
        self._target_port = port
        self._tls = tls
        self._server_name = server_name
        self._context = context
        if proxy:
            tunnel_host = '[' + address + ']' if ':' in address else address
            self.set_tunnel(tunnel_host, port)

    def connect(self):
        if self._tunnel_host:
            super().connect()
        else:
            self.sock = socket.create_connection((self._address, self._target_port), self.timeout)
        if self._tls:
            self.sock = self._context.wrap_socket(self.sock, server_hostname=self._server_name)


class PublicHTTPClient:
    def __init__(self, *, resolver=socket.getaddrinfo, request=None,
                 max_body_bytes: int = MAX_BODY_BYTES, timeout_seconds: float = 15):
        if not 1 <= max_body_bytes <= MAX_BODY_BYTES or not 1 <= timeout_seconds <= 20:
            raise ValueError('Public HTTP bounds are invalid.')
        self.resolver = resolver
        self.request = request
        self.max_body_bytes = max_body_bytes
        self.timeout_seconds = timeout_seconds

    async def fetch_once(self, url: str) -> PublicHTTPResponse:
        try:
            url = normalize_public_url(url)
        except SiteInputError as exc:
            raise ResearchError('invalid_url', 'Enter a public website address.', 400) from exc
        try:
            async with asyncio.timeout(min(self.timeout_seconds + 5, 25)):
                if self.request:
                    result = self.request(url)
                    if asyncio.iscoroutine(result):
                        result = await result
                    return self._validate_fixture_response(url, result)
                return await asyncio.to_thread(self._fetch_sync, url)
        except ResearchError:
            raise
        except TimeoutError:
            raise ResearchError('research_timeout', 'The public website exceeded its request deadline.', 504) from None
        except (OSError, ssl.SSLError, http.client.HTTPException):
            raise ResearchError('source_unavailable', 'The public website could not be retrieved securely.', 502) from None

    def _validate_fixture_response(self, url, result):
        if not isinstance(result, PublicHTTPResponse) or result.url != url:
            raise ResearchError('provider_malformed', 'The website transport returned an invalid response.', 502)
        if len(result.body) > self.max_body_bytes:
            raise ResearchError('provider_response_too_large', 'The webpage exceeded the one-megabyte limit.', 502)
        return PublicHTTPResponse(result.url, result.status,
                                  {str(k).lower(): str(v) for k, v in result.headers.items()}, result.body)

    def _fetch_sync(self, url: str) -> PublicHTTPResponse:
        parsed = urlsplit(url)
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        addresses = _public_addresses(parsed.hostname or '', port, self.resolver)
        # Prefer IPv4 only for compatibility with inherited CONNECT proxies;
        # IPv6 remains supported when it is the only public destination.
        address = next((value for value in addresses if ':' not in value), addresses[0])
        proxy_url = urlsplit(os.getenv('HTTPS_PROXY') or os.getenv('https_proxy') or
                             os.getenv('HTTP_PROXY') or os.getenv('http_proxy') or '')
        proxy = None
        if proxy_url.scheme:
            if proxy_url.scheme != 'http' or not proxy_url.hostname or proxy_url.username or proxy_url.password:
                raise ResearchError('research_egress_not_verified', 'The configured HTTP proxy is unsupported.', 503)
            proxy = (proxy_url.hostname, proxy_url.port or 80)
        context = ssl.create_default_context()
        connection = _PinnedConnection(parsed.hostname, port, address=address,
            tls=parsed.scheme == 'https', server_name=parsed.hostname, context=context,
            timeout=self.timeout_seconds, proxy=proxy)
        target = parsed.path or '/'
        if parsed.query:
            target += '?' + parsed.query
        host_header = parsed.hostname or ''
        if parsed.port and not ((parsed.scheme == 'https' and parsed.port == 443)
                               or (parsed.scheme == 'http' and parsed.port == 80)):
            host_header += ':' + str(parsed.port)
        try:
            connection.request('GET', target, headers={
                'Host': host_header,
                'User-Agent': USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,text/plain;q=0.8',
                'Accept-Encoding': 'identity',
                'Connection': 'close',
            })
            response = connection.getresponse()
            headers: dict[str, str] = {}
            for name, value in response.getheaders():
                key = name.lower()
                if key not in headers:
                    headers[key] = value
            if headers.get('content-encoding', 'identity').lower() not in {'', 'identity'}:
                raise ResearchError('unsupported_content_type', 'Compressed webpage responses are not accepted.', 422)
            length = headers.get('content-length')
            if length and (not length.isdigit() or int(length) > self.max_body_bytes):
                raise ResearchError('provider_response_too_large', 'The webpage exceeded the one-megabyte limit.', 502)
            body = response.read(self.max_body_bytes + 1)
            if len(body) > self.max_body_bytes:
                raise ResearchError('provider_response_too_large', 'The webpage exceeded the one-megabyte limit.', 502)
            return PublicHTTPResponse(url=url, status=response.status, headers=headers, body=body)
        finally:
            connection.close()
