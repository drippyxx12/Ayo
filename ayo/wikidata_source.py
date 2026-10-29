"""Bounded CC0 company records from Wikidata's fixed-host public JSON APIs.

No arbitrary-site crawl, browser, Firecrawl call or paid source endpoint exists
here. The proxy CONNECT destination is a vetted public IP; TLS SNI/Host retain
the original fixed hostname. Redirects are rejected rather than followed.
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
from urllib.parse import urlencode, urlsplit

from ayo.budgets import BudgetError
from ayo.provider_usage import metered_operation
from ayo.research import BusinessCandidate, ResearchError, SourceDocument, _public_content

HOST = 'www.wikidata.org'
BASE = 'https://' + HOST
ENTITY = re.compile(r'^Q[1-9][0-9]{0,11}$')
BUSINESS_DESCRIPTION = re.compile(r'\b(company|business|corporation|marketplace|retailer|organization)\b', re.I)
AGENT = 'AyoResearch/0.1 (https://github.com/drippyxx12/Ayo/issues; bounded operator-led CC0 research)'


def _json_get(path):
    if not (re.fullmatch(r'/wiki/Special:EntityData/Q[1-9][0-9]{0,11}\.json', path) or
            path.startswith('/w/api.php?action=wbsearchentities&')):
        raise ResearchError('source_policy_not_approved', 'Unsupported source API path.', 403)
    addresses = {row[4][0] for row in socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)}
    def public(value):
        ip = ipaddress.ip_address(value)
        return ip.is_global and not ip.is_multicast and not getattr(ip, 'ipv4_mapped', None)
    if not addresses or not all(public(value) for value in addresses):
        raise ResearchError('provider_unsafe_redirect', 'Source DNS is not entirely public.', 403)
    address = next((value for value in sorted(addresses) if ':' not in value), sorted(addresses)[0])
    proxy = urlsplit(os.getenv('HTTPS_PROXY') or os.getenv('https_proxy') or '')
    if proxy.scheme != 'http' or not proxy.hostname or proxy.username or proxy.password:
        raise ResearchError('research_egress_not_verified', 'The configured HTTP CONNECT proxy is required.', 503)
    context = ssl.create_default_context()
    class PinnedTLS(http.client.HTTPConnection):
        def connect(self):
            super().connect()  # CONNECT to the pinned IP through the inherited proxy.
            self.sock = context.wrap_socket(self.sock, server_hostname=HOST)
    connection = PinnedTLS(proxy.hostname, proxy.port or 80, timeout=15)
    connection.set_tunnel(address, 443)
    try:
        connection.request('GET', path, headers={'Host': HOST, 'User-Agent': AGENT,
            'Accept': 'application/json', 'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        if response.status != 200 or response.getheader('Content-Encoding', 'identity') != 'identity':
            raise ResearchError('source_unavailable', 'The licensed source returned an unsuccessful or unsupported response.', 502)
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ResearchError('provider_response_too_large', 'Source response exceeds the one-megabyte bound.', 502)
        result = json.loads(raw)
        if not isinstance(result, dict) or 'error' in result:
            raise ValueError()
        return result
    except ResearchError:
        raise
    except (OSError, ValueError, http.client.HTTPException):
        raise ResearchError('source_unavailable', 'The licensed source is unavailable; no retry or bypass occurred.', 502) from None
    finally:
        connection.close()


class WikidataProvider:
    def __init__(self, *, get_json=None, dispatch_budget=metered_operation):
        self.get_json = get_json
        self.dispatch_budget = dispatch_budget

    async def _request(self, operation, path):
        if os.getenv('AYO_WIKIDATA_READ_AUTHORIZED') != '1' or os.getenv('AYO_WIKIDATA_API_REVIEW') != 'cc0_reviewed':
            raise ResearchError('source_policy_not_approved', 'Wikidata CC0 API use is not enabled for this run.', 403)
        try:
            async with self.dispatch_budget('wikidata', operation), asyncio.timeout(35):
                return await self.get_json(path) if self.get_json else await asyncio.to_thread(_json_get, path)
        except BudgetError as error:
            raise ResearchError(error.code, str(error), 503) from error

    async def search(self, query, country='', city='', limit=5):
        path = '/w/api.php?' + urlencode({'action': 'wbsearchentities', 'search': query,
            'language': 'en', 'type': 'item', 'format': 'json', 'limit': min(limit, 5)})
        result = await self._request('search', path)
        candidates = []
        for item in result.get('search', [])[:limit]:
            identity = item.get('id', '')
            description = str(item.get('description', ''))
            if not ENTITY.fullmatch(identity) or not BUSINESS_DESCRIPTION.search(description):
                continue
            # Search matches remain candidates; no country/company identity is inferred.
            candidates.append(BusinessCandidate(id=identity, name=_public_content(str(item.get('label', '')))[:240],
                url=BASE + '/wiki/Special:EntityData/' + identity + '.json',
                snippet=_public_content(str(item.get('description', '')))[:600], country=country,
                source_id='wikidata-search-' + identity, discovered_at=datetime.now(timezone.utc), provider='wikidata_cc0'))
        return tuple(candidates)

    async def fetch(self, url, country=''):
        parsed = urlsplit(url)
        match = re.fullmatch(r'/wiki/Special:EntityData/(Q[1-9][0-9]{0,11})\.json', parsed.path)
        if parsed.scheme != 'https' or parsed.netloc != HOST or parsed.query or parsed.fragment or not match:
            raise ResearchError('source_policy_not_approved', 'Select a Wikidata company-record candidate.', 403)
        identity = match.group(1)
        data = await self._request('fetch', parsed.path)
        entity = data.get('entities', {}).get(identity)
        if not isinstance(entity, dict) or entity.get('id') != identity or entity.get('type') != 'item':
            raise ResearchError('provider_malformed', 'The source returned a different entity.', 502)
        label = entity.get('labels', {}).get('en', {}).get('value', '')
        description = entity.get('descriptions', {}).get('en', {}).get('value', '')
        if not isinstance(label, str) or not label or not isinstance(description, str):
            raise ResearchError('insufficient_evidence', 'No usable English company record was returned.', 422)
        human = any(statement.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id') == 'Q5'
                    for statement in entity.get('claims', {}).get('P31', [])
                    if isinstance(statement.get('mainsnak', {}).get('datavalue', {}).get('value'), dict))
        if human or not BUSINESS_DESCRIPTION.search(description):
            raise ResearchError('source_not_business', 'The selected record is not an eligible company or organization record.', 422)
        lines = ['Wikidata item: ' + identity, 'Label: ' + label, 'Description: ' + description]
        for statement in entity.get('claims', {}).get('P17', [])[:5]:
            value = statement.get('mainsnak', {}).get('datavalue', {}).get('value', {})
            if isinstance(value, dict) and value.get('id') in {'Q1033', 'Q117'}:
                lines.append('Country stated by Wikidata: ' + {'Q1033': 'Nigeria', 'Q117': 'Ghana'}[value['id']])
        content = _public_content('\n'.join(lines))
        digest = hashlib.sha256(content.encode()).hexdigest()
        return SourceDocument(id='wikidata-' + identity + '-' + digest[:16], url=url,
            retrieved_at=datetime.now(timezone.utc), source_hash=digest, title=label,
            excerpt=content[:600], content=content, provider='wikidata_cc0',
            provider_receipt_id=str(entity.get('lastrevid') or identity), robots_policy='API_POLICY_REVIEWED')
