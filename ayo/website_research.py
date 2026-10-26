"""Pure, non-network public website research primitives for Ayo.

WARNING: normalize_public_url does NOT make a URL safe to FETCH. The eventual
crawler MUST use a hardened network egress with DNS/IP pinning, robots policy,
per-hop redirect validation, rate limiting and bounded size. This module never
issues HTTP requests, and does not claim to have inspected a live website.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from ipaddress import ip_address
import json
import re
from urllib.parse import parse_qsl, unquote, urlencode, quote, urljoin, urlsplit, urlunsplit


class SiteInputError(ValueError):
    """Input cannot be admitted into the public website research workflow."""


@dataclass(frozen=True)
class WebsiteIntent:
    kind: str  # 'search' or 'url'
    value: str
    ownership_verified: bool = False


@dataclass(frozen=True)
class PageObservation:
    url: str
    title: str | None = None
    meta_description: str | None = None
    headings: tuple[str, ...] = ()
    links: tuple[str, ...] = ()
    product_structured_data: tuple[dict, ...] = ()
    warnings: tuple[str, ...] = ()
    source_classification: str = 'PUBLIC_UNVERIFIED'

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_public_url(text: str) -> str:
    """Normalize a plausible public website URL without making network requests.

    Validation here is syntactic only. IP addresses and special-use hostnames
    are deliberately refused. A later secure fetcher must ALSO validate DNS,
    actual destination IP, TLS, response redirect chains and robots.txt.
    """
    if not isinstance(text, str):
        raise SiteInputError('Enter a valid public website address.')
    text = text.strip()
    if not text or len(text) > 2048 or any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise SiteInputError('Enter a valid public website address.')
    if not re.match(r'^https?://', text, re.I):
        if '://' in text or text.startswith('//'):
            raise SiteInputError('Only public http and https websites are supported.')
        text = 'https://' + text
    try:
        parsed = urlsplit(text)
        host = parsed.hostname
        if not host or parsed.username or parsed.password:
            raise SiteInputError('Credentials or missing host in website URL.')
        if parsed.scheme not in {'https', 'http'}:
            raise SiteInputError('Only public http and https websites are supported.')
        port = parsed.port
        if port and port not in {80, 443}:
            raise SiteInputError('Nonstandard website ports are not supported.')
        host = host.rstrip('.').encode('idna').decode('ascii').lower()
        if len(host) > 253 or any(len(part) > 63 or not part for part in host.split('.')):
            raise SiteInputError('Invalid website hostname.')
        if re.search(r'[^a-z0-9.\-]', host) or any(part.startswith('-') or part.endswith('-') for part in host.split('.')):
            raise SiteInputError('Invalid website hostname.')
        if len(host.split('.')) < 2 or host.endswith(('.localhost', '.local', '.internal', '.test', '.invalid', '.example')):
            raise SiteInputError('This is not a public website hostname.')
        try:
            ip_address(host)
        except ValueError:
            # Reject numeric-only hostnames, e.g. octal/decimal IP aliases.
            if re.fullmatch(r'[0-9.]+', host):
                raise SiteInputError('Public IP literals and aliases are not supported.')
        else:
            raise SiteInputError('Public IP literals are not supported. Enter a domain.')
        path = parsed.path or '/'
        # Check the path the origin may actually interpret, including nested
        # encodings. Never forward encoded controls, separators or dot-segment
        # aliases that could evade the public-page policy downstream.
        for _ in range(5):
            if re.search(r'%(?![0-9a-fA-F]{2})', path):
                raise SiteInputError('Invalid website path encoding.')
            decoded = unquote(path, errors='strict')
            if decoded == path:
                break
            path = decoded
        else:
            raise SiteInputError('Excessively encoded website path.')
        if ('\\' in path or ';' in path or any(ord(c) < 32 or ord(c) == 127 for c in path)
                or any(segment in {'.', '..'} for segment in path.split('/'))):
            raise SiteInputError('Unsupported website path.')
        path = quote(path, safe="/!$&'()*+,-._~:@")
        query = ''
        # This public profile endpoint identifies businesses by a query value.
        # Dropping every query conflates unrelated profiles. Retain only its
        # validated identity, never tracking/authentication query parameters.
        if host in {'facebook.com', 'www.facebook.com', 'm.facebook.com'} and path == '/profile.php' and parsed.query:
            identities = [value for key, value in parse_qsl(parsed.query) if key == 'id']
            if len(identities) != 1 or not re.fullmatch(r'[0-9]{1,30}', identities[0]):
                raise SiteInputError('Enter a public Facebook profile with its numeric identity.')
            query = urlencode({'id': identities[0]})
        netloc = host if port is None or (parsed.scheme == 'https' and port == 443) or (parsed.scheme == 'http' and port == 80) else f'{host}:{port}'
        return urlunsplit((parsed.scheme.lower(), netloc, path, query, ''))
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, SiteInputError):
            raise
        raise SiteInputError('Invalid website URL.') from exc


def classify_website_input(text: str) -> WebsiteIntent:
    """Distinguish candidate name search from a URL; never asserts ownership."""
    raw = text.strip()
    if not raw or len(raw) > 250:
        raise SiteInputError('Enter a company name or a website address.')
    is_url = raw.lower().startswith(('http://', 'https://', 'www.')) or (' ' not in raw and '.' in raw)
    if is_url:
        return WebsiteIntent('url', normalize_public_url(raw), False)
    cleaned = re.sub(r'\s+', ' ', raw)
    return WebsiteIntent('search', cleaned, False)


def _clean(s: str | None, limit: int = 350) -> str | None:
    if not s:
        return None
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:limit] if s else None


class _PageParser(HTMLParser):
    def __init__(self, source_url: str, max_links: int, max_schema_chars: int):
        super().__init__(convert_charrefs=True)
        self.source_url = source_url
        self.max_links = max_links
        self.max_schema_chars = max_schema_chars
        self.title_chunks: list[str] = []
        self.headings: list[str] = []
        self.links: list[str] = []
        self.description: str | None = None
        self.jsonld_text: list[str] = []
        self.products: list[dict] = []
        self.warnings: list[str] = []
        self._skip_depth = 0
        self._title_depth = 0
        self._heading_tag: str | None = None
        self._heading_chunks: list[str] = []
        self._jsonld_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        at = dict(attrs)
        if tag in {'style', 'noscript'}:
            self._skip_depth += 1
        if tag == 'script':
            self._skip_depth += 1
            if (at.get('type') or '').lower() == 'application/ld+json':
                self._jsonld_depth += 1
                self.jsonld_text = []
        if self._skip_depth:
            return
        if tag == 'title':
            self._title_depth += 1
        if tag in {'h1', 'h2'}:
            self._heading_tag = tag
            self._heading_chunks = []
        if tag == 'meta' and (at.get('name') or '').lower() == 'description':
            self.description = _clean(at.get('content'))
        if tag == 'a' and len(self.links) < self.max_links:
            href = at.get('href') or ''
            if href.startswith(('/', 'http://', 'https://')) and not href.startswith('//'):
                url = urljoin(self.source_url, href)
                if urlsplit(url).scheme in {'http', 'https'}:
                    self.links.append(url)

    def handle_data(self, data: str):
        if self._jsonld_depth:
            current = sum(map(len, self.jsonld_text))
            if current + len(data) <= self.max_schema_chars:
                self.jsonld_text.append(data)
            elif 'jsonld_truncated' not in self.warnings:
                self.warnings.append('jsonld_truncated')
            return
        if self._skip_depth:
            return
        if self._title_depth:
            self.title_chunks.append(data)
        if self._heading_tag:
            self._heading_chunks.append(data)

    def handle_endtag(self, tag: str):
        if tag == 'script' and self._jsonld_depth:
            try:
                if 'jsonld_truncated' not in self.warnings:
                    content = json.loads(''.join(self.jsonld_text))
                    for obj in self._flatten_jsonld(content):
                        if len(self.products) >= 20:
                            break
                        typ = obj.get('@type', '')
                        types = [typ] if isinstance(typ, str) else typ if isinstance(typ, list) else []
                        if 'Product' in types:
                            product = {'name': _clean(obj.get('name') if isinstance(obj.get('name'), str) else None)}
                            offers = obj.get('offers')
                            if isinstance(offers, dict):
                                product['price'] = offers.get('price') if isinstance(offers.get('price'), (int, float, str)) else None
                                product['priceCurrency'] = offers.get('priceCurrency') if isinstance(offers.get('priceCurrency'), str) else None
                            self.products.append(product)
            except (ValueError, TypeError, RecursionError):
                self.warnings.append('invalid_jsonld')
            self._jsonld_depth -= 1
            self.jsonld_text = []
        if tag in {'style', 'noscript', 'script'} and self._skip_depth:
            self._skip_depth -= 1
        if tag == 'title' and self._title_depth:
            self._title_depth -= 1
        if tag == self._heading_tag:
            h = _clean(''.join(self._heading_chunks), limit=240)
            if h and len(self.headings) < 30:
                self.headings.append(h)
            self._heading_tag = None
            self._heading_chunks = []

    @staticmethod
    def _flatten_jsonld(root):
        if isinstance(root, dict):
            if isinstance(root.get('@graph'), list):
                return [obj for obj in root['@graph'] if isinstance(obj, dict)]
            return [root]
        if isinstance(root, list):
            return [obj for obj in root if isinstance(obj, dict)]
        return []


def extract_public_page(source_url: str, html: str, max_chars: int = 300_000) -> PageObservation:
    """Extract *observations* from supplied HTML; never retrieves a page.

    Caller must supply actual retrieved data + URL. Its provenance is NOT
    considered validated here; website claims are public/unverified. This
    extractor alone cannot infer real sales, conversion, profit or inventory.
    """
    if len(html) > max_chars:
        raise ValueError('HTML exceeds the configured extraction size limit.')
    parser = _PageParser(source_url, max_links=100, max_schema_chars=25_000)
    parser.feed(html)
    return PageObservation(
        url=source_url,
        title=_clean(''.join(parser.title_chunks)),
        meta_description=parser.description,
        headings=tuple(parser.headings),
        links=tuple(dict.fromkeys(parser.links)),
        product_structured_data=tuple(parser.products),
        warnings=tuple(dict.fromkeys(parser.warnings)),
    )
