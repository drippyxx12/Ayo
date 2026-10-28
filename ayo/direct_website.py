"""Single-page public website evidence for the existing research worker.

This adapter handles ordinary public HTTP(S) pages without a paid crawler. It
checks robots.txt, follows only bounded same-site redirects, retains immutable
source provenance and refuses authentication walls, executable documents and
weak client-only shells. The network transport independently validates every
resolved address and pins the connection before bytes are read.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from ayo.public_http import PublicHTTPClient, PublicHTTPResponse, USER_AGENT
from ayo.research import (
    MAX_SOURCE_CHARS,
    BusinessCandidate,
    PublicProduct,
    ResearchError,
    SourceDocument,
    _access_wall,
    _public_content,
    _public_url,
)
from ayo.website_research import extract_public_page


_REDIRECTS = frozenset({301, 302, 303, 307, 308})
_HTML_TYPES = frozenset({'text/html', 'application/xhtml+xml'})
_TEXT_TYPES = frozenset({'text/plain'})
_CHARSETS = {'utf-8': 'utf-8', 'utf8': 'utf-8', 'us-ascii': 'ascii',
             'iso-8859-1': 'iso-8859-1', 'latin1': 'iso-8859-1',
             'windows-1252': 'cp1252'}
_CHANNEL_HOSTS = {
    'WhatsApp': {'wa.me', 'api.whatsapp.com', 'whatsapp.com'},
    'Instagram': {'instagram.com', 'www.instagram.com'},
    'Facebook': {'facebook.com', 'www.facebook.com'},
    'TikTok': {'tiktok.com', 'www.tiktok.com'},
    'Jiji': {'jiji.ng', 'jiji.com.gh'},
}


def _site_host(url: str) -> str:
    return (urlsplit(url).hostname or '').removeprefix('www.')


def _same_site(initial: str, target: str) -> bool:
    """Allow only the common bare-host/www alias, never sibling subdomains."""
    return bool(_site_host(initial) and _site_host(initial) == _site_host(target))


def _redirect(initial: str, current: str, response: PublicHTTPResponse) -> str:
    location = response.headers.get('location', '')
    if not location or len(location) > 2048:
        raise ResearchError('provider_unsafe_redirect', 'The website returned an invalid redirect.', 502)
    target = _public_url(urljoin(current, location))
    if not _same_site(initial, target):
        raise ResearchError('provider_unsafe_redirect', 'The website redirected outside its public host.', 502)
    if urlsplit(current).scheme == 'https' and urlsplit(target).scheme != 'https':
        raise ResearchError('provider_unsafe_redirect', 'The website attempted an insecure redirect.', 502)
    return target


def _decode(response: PublicHTTPResponse, *, robots: bool = False) -> str:
    content_type = response.headers.get('content-type', '').split(';', 1)[0].strip().lower()
    if not robots and content_type and content_type not in _HTML_TYPES | _TEXT_TYPES:
        raise ResearchError('unsupported_content_type',
                            'This public address is not a readable HTML or text webpage.', 422)
    match = re.search(r'charset\s*=\s*["\']?([A-Za-z0-9._-]+)',
                      response.headers.get('content-type', ''), re.I)
    charset = (match.group(1).lower() if match else 'utf-8')
    codec = _CHARSETS.get(charset)
    if codec is None:
        raise ResearchError('unsupported_content_type', 'The webpage uses an unsupported text encoding.', 422)
    try:
        return response.body.decode(codec)
    except UnicodeDecodeError:
        raise ResearchError('source_unavailable', 'The webpage text could not be decoded safely.', 422) from None


def _response_error(response: PublicHTTPResponse, *, robots: bool = False):
    if response.status in {401, 403}:
        code = 'robots_denied' if robots else 'source_access_restricted'
        message = ('The website does not permit this automated page request.' if robots else
                   'The website requires authentication or refused public access.')
        raise ResearchError(code, message, 403 if robots else 422)
    if response.status == 429:
        raise ResearchError('provider_rate_limited', 'The website is temporarily rate limited.', 429)
    if response.status in {502, 503, 504}:
        raise ResearchError('provider_service_unavailable', 'The public website is temporarily unavailable.', 503)
    if response.status >= 400:
        raise ResearchError('source_unavailable', 'The public webpage could not be retrieved.', 422)


class DirectWebsiteProvider:
    """Retrieve one readable public page; never render scripts or bypass gates."""

    def __init__(self, client: PublicHTTPClient | None = None, *, deadline_seconds: float = 45):
        if not 0 < deadline_seconds <= 45:
            raise ValueError('Website retrieval deadline must fit within the worker lease.')
        self.client = client or PublicHTTPClient()
        self.deadline_seconds = deadline_seconds
        self._robots: dict[tuple[str, str, int | None], RobotFileParser | None] = {}

    async def search(self, query: str, country: str = '', city: str = '', limit: int = 5) -> tuple[BusinessCandidate, ...]:
        raise ResearchError('website_url_required',
                            'Paste the public website address. Name search needs a separately configured discovery source.', 400)

    async def _robots_allowed(self, target: str) -> None:
        parsed = urlsplit(target)
        origin = (parsed.scheme, parsed.hostname or '', parsed.port)
        rules = self._robots.get(origin, ...)
        if rules is ...:
            robots_url = urlunsplit((parsed.scheme, parsed.netloc, '/robots.txt', '', ''))
            current = robots_url
            response = None
            for _ in range(4):
                response = await self.client.fetch_once(current)
                if response.status not in _REDIRECTS:
                    break
                current = _redirect(robots_url, current, response)
            else:
                raise ResearchError('provider_unsafe_redirect', 'The website robots policy redirected too many times.', 502)
            assert response is not None
            if response.status in {404, 410}:
                rules = None
            else:
                _response_error(response, robots=True)
                if response.status != 200:
                    raise ResearchError('source_unavailable', 'The website robots policy could not be checked.', 503)
                robots_type = response.headers.get('content-type', '').split(';', 1)[0].strip().lower()
                if robots_type not in {'', 'text/plain', 'text/x-robots'}:
                    raise ResearchError('source_unavailable', 'The website robots policy was not returned as text.', 503)
                text = _decode(response, robots=True)
                if len(text) > 200_000:
                    raise ResearchError('source_unavailable', 'The website robots policy is too large to evaluate.', 503)
                rules = RobotFileParser()
                rules.set_url(current)
                rules.parse(text.splitlines())
            self._robots[origin] = rules
        if rules is not None and not rules.can_fetch(USER_AGENT, target):
            raise ResearchError('robots_denied', 'The website robots policy does not permit this page request.', 403)

    async def fetch(self, url: str, country: str = '') -> SourceDocument:
        # One deadline covers robots AND every page redirect. Per-hop socket
        # deadlines alone can multiply past the worker's publication lease.
        try:
            async with asyncio.timeout(self.deadline_seconds):
                return await self._fetch(url, country)
        except TimeoutError:
            raise ResearchError('research_timeout', 'The public website exceeded its total retrieval deadline.', 504) from None

    async def _fetch(self, url: str, country: str = '') -> SourceDocument:
        initial = current = _public_url(url)
        response = None
        for _ in range(4):
            await self._robots_allowed(current)
            response = await self.client.fetch_once(current)
            if response.status not in _REDIRECTS:
                break
            current = _redirect(initial, current, response)
        else:
            raise ResearchError('provider_unsafe_redirect', 'The website redirected too many times.', 502)
        assert response is not None
        _response_error(response)
        if response.status != 200:
            raise ResearchError('source_unavailable', 'The public webpage did not return a readable response.', 422)

        raw = _decode(response)
        content_type = response.headers.get('content-type', '').split(';', 1)[0].strip().lower()
        html_like = content_type in _HTML_TYPES or (not content_type and
            re.search(r'<!doctype\s+html|<html\b|<body\b', raw[:2000], re.I))
        if not content_type and not html_like:
            raise ResearchError('unsupported_content_type',
                                'The website did not identify readable HTML or text content.', 422)

        # The transport has already capped bytes at 1 MB. Match the parser's
        # character ceiling to that bound instead of its smaller legacy default.
        observation = extract_public_page(current, raw, max_chars=1_000_000) if html_like else None
        content = _public_content(raw)
        title = _public_content(observation.title or '')[:240] if observation else ''
        if _access_wall(content, title):
            raise ResearchError('source_access_restricted',
                                'The website returned a login, access or bot-verification page.', 422)
        words = re.findall(r'\w+', content)
        if len(content) < 30 or len(words) < 5:
            script_shell = html_like and bool(re.search(
                r'<(?:div|main)[^>]+id=["\'](?:root|app|__next)["\']|javascript\s+is\s+required|enable\s+javascript',
                raw, re.I))
            raise ResearchError('source_requires_javascript' if script_shell else 'insufficient_evidence',
                                'The website requires browser rendering.' if script_shell else
                                'The public page did not contain enough readable business evidence.', 422)

        products, channels = [], ()
        if observation:
            for item in observation.product_structured_data:
                name = _public_content(item.get('name') or '')[:200]
                if not name:
                    continue
                price = str(item['price']) if item.get('price') is not None else None
                if price is not None and len(price) > 40:
                    price = None
                currency = item.get('priceCurrency')
                currency = currency.upper() if isinstance(currency, str) and re.fullmatch(r'[A-Za-z]{3}', currency) else None
                try:
                    product = PublicProduct(name=name, listed_price=price, currency=currency)
                except ValueError:
                    product = PublicProduct(name=name, currency=currency)
                if product not in products:
                    products.append(product)
            hosts = {urlsplit(link).hostname for link in observation.links}
            channels = tuple(name for name, domains in _CHANNEL_HOSTS.items() if hosts & domains)
            if products or channels:
                appendix = '\n\nPUBLIC MARKUP OBSERVATIONS (UNVERIFIED):\n' + json.dumps(
                    {'listed_products': [p.model_dump() for p in products[:20]],
                     'linked_channels': channels}, ensure_ascii=False)
                content = content[:MAX_SOURCE_CHARS - len(appendix)] + appendix
        content = content[:MAX_SOURCE_CHARS]
        digest = hashlib.sha256(content.encode()).hexdigest()
        raw_hash = hashlib.sha256(response.body).hexdigest() if html_like else None
        return SourceDocument(
            id='source-' + digest[:32], url=current, retrieved_at=datetime.now(timezone.utc),
            source_hash=digest, title=title, excerpt=content[:600], content=content,
            provider='direct_public_web', provider_receipt_id='direct-' + hashlib.sha256(
                (current + raw_hash if raw_hash else current + digest).encode()).hexdigest()[:32],
            robots_policy='ROBOTS_CHECKED', html_source_hash=raw_hash,
            product_observations=tuple(products[:20]), channel_observations=channels,
        )
