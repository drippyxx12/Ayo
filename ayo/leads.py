"""Organization prospect discovery and evidence-gated pipeline transitions.

Discovery is research, not outreach consent or a sale. This module has no send
adapter. Tenant membership and persistence are enforced by the caller's scoped
repository; transition validation additionally requires a matching business.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Literal, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ayo.website_research import SiteInputError, normalize_public_url


class LeadError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


LeadStatus = Literal['discovered', 'qualified', 'contacted', 'replied', 'converted']


class LeadCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    id: str
    name: str = Field(min_length=1, max_length=240)
    url: str = Field(min_length=1, max_length=2048)
    country: Literal['NG', 'GH']
    city: str = Field(default='', max_length=100)
    status: LeadStatus = 'discovered'
    source_id: str = Field(min_length=1, max_length=160)
    source_url: str
    source_excerpt: str = Field(min_length=1, max_length=2000)
    discovered_at: datetime
    fit_reasons: tuple[str, ...] = ()
    fit_evidence_ids: tuple[str, ...] = ()
    contact_status: Literal['unknown'] = 'unknown'
    outreach_allowed: Literal[False] = False

    @model_validator(mode='after')
    def safe_source(self):
        normalize_public_url(self.url)
        normalize_public_url(self.source_url)
        if self.discovered_at.tzinfo is None:
            raise ValueError('Lead discovery time needs a timezone')
        if any(e != self.source_id for e in self.fit_evidence_ids):
            raise ValueError('Lead fit can cite only the actual discovery source')
        return self

    def to_dict(self) -> dict:
        return self.model_dump(mode='json')


class SearchProvider(Protocol):
    async def search(self, query: str, country: str = '', city: str = '', limit: int = 5): ...


_ORG_SIGNALS = re.compile(
    r'\b(?:business|company|boutique|store|shop|wholesal\w*|retail\w*|distributor\w*|supplier\w*|manufacturer\w*|brand|enterprise\w*|commerce|stockist\w*|marketplace)\b', re.I)
_PROFILE_HOSTS = {'instagram.com', 'facebook.com', 'linkedin.com', 'tiktok.com', 'x.com', 'jiji.ng', 'jiji.com.gh', 'tonaton.com', 'jumia.com.ng', 'jumia.com.gh'}
_QUERY_STOP = {'the', 'and', 'for', 'with', 'from', 'find', 'ghana', 'nigeria', 'business', 'businesses', 'shop', 'shops', 'store', 'stores'}


def identity_key(url: str) -> str:
    """Domain/profile dedupe without conflating hosted organization identities.

    The shared public URL parser removes tracking queries and preserves only a
    validated Facebook numeric identity. This remains a discovery heuristic,
    not proof that two aliases belong to the same organization or merchant.
    """
    normalized = normalize_public_url(url)
    parsed = urlsplit(normalized)
    host = parsed.hostname.removeprefix('www.')
    if host == 'm.facebook.com':
        host = 'facebook.com'
    if host in _PROFILE_HOSTS:
        path = parsed.path.rstrip('/').casefold()
        if host == 'facebook.com' and path == '/profile.php' and not parsed.query:
            raise SiteInputError('A Facebook profile needs its public numeric identity.')
        if host == 'linkedin.com':
            parts = path.strip('/').split('/')
            if len(parts) >= 2 and parts[0] == 'company':
                # The about/jobs/posts tabs of one company are not new leads.
                path = '/company/' + parts[1]
        return host + path + ('?' + parsed.query if parsed.query else '')
    return host


def _value(candidate, name: str, default=None):
    return candidate.get(name, default) if isinstance(candidate, dict) else getattr(candidate, name, default)


async def discover_leads(
    provider: SearchProvider,
    query: str,
    country: str,
    city: str = '',
    *,
    existing_urls: tuple[str, ...] = (),
    limit: int = 5,
) -> tuple[LeadCandidate, ...]:
    """Return only sourced organization candidates; never synthesize contacts.

    Country is the explicitly selected discovery market, not independently
    verified business domicile. Search-index snippets are clearly retained as
    discovery evidence; they do not establish product demand or site ownership.
    """
    if country not in {'NG', 'GH'}:
        raise LeadError('invalid_market', 'Choose Nigeria or Ghana for lead research.')
    query, city = query.strip(), city.strip()
    if not query or len(query) > 250 or len(city) > 100 or not 1 <= limit <= 20:
        raise LeadError('invalid_input', 'Lead research needs a bounded offer/query and result limit.')
    if any(ord(c) < 32 or ord(c) == 127 for c in query + city):
        raise LeadError('invalid_input', 'Enter a valid lead research query.')
    seen = set()
    for url in existing_urls:
        try:
            seen.add(identity_key(url))
        except SiteInputError:
            continue
    candidates = await provider.search(query, country=country, city=city, limit=limit)
    output = []
    query_terms = {t for t in re.findall(r'[a-z]{3,}', query.lower()) if t not in _QUERY_STOP}
    for candidate in tuple(candidates)[:20]:
        name = _value(candidate, 'name', _value(candidate, 'title', ''))
        url = _value(candidate, 'url', '')
        snippet = _value(candidate, 'snippet', _value(candidate, 'description', ''))
        source_id = _value(candidate, 'source_id', '')
        discovered_at = _value(candidate, 'discovered_at', None)
        if not all(isinstance(s, str) and s.strip() for s in (name, url, snippet, source_id)):
            continue
        if len(name) > 240 or len(snippet) > 2000 or len(source_id) > 160:
            continue
        if not isinstance(discovered_at, datetime) or discovered_at.tzinfo is None:
            continue
        text = name + ' ' + snippet
        if not _ORG_SIGNALS.search(text):
            continue
        try:
            url = normalize_public_url(url)
            key = identity_key(url)
        except SiteInputError:
            continue
        # Individual professional profiles are not organization lead records.
        if urlsplit(url).hostname.removeprefix('www.') == 'linkedin.com' and urlsplit(url).path.casefold().startswith('/in/'):
            continue
        if key in seen:
            continue
        seen.add(key)
        matches = sorted(t for t in query_terms if re.search(r'\b' + re.escape(t) + r'\b', snippet, re.I))
        reasons = [f'Search source describes an organization: "{_ORG_SIGNALS.search(text).group(0)}".']
        if matches:
            reasons.append('Source mentions offer/query terms: ' + ', '.join(matches[:6]) + '.')
        if city and city.casefold() in snippet.casefold():
            reasons.append('Source mentions the selected location: ' + city + '.')
        reasons.append('Research candidate only; location, demand and contact permission need review.')
        output.append(LeadCandidate(
            id=hashlib.sha256(key.encode()).hexdigest()[:32], name=name.strip(), url=url,
            country=country, city=city, source_id=source_id, source_url=url,
            source_excerpt=snippet.strip(), discovered_at=discovered_at,
            fit_reasons=tuple(reasons), fit_evidence_ids=(source_id,),
        ))
        if len(output) == limit:
            break
    return tuple(output)


class PipelineEvidence(BaseModel):
    """Server-resolved proof, not a browser-supplied authorization object.

    Later provider adapters must resolve the receipt from their verified event
    ledger. Passing an arbitrary reference from a form is never sufficient.
    """
    model_config = ConfigDict(frozen=True, extra='forbid')
    business_id: str = Field(min_length=1, max_length=64)
    kind: Literal['qualification', 'provider_send', 'provider_reply', 'provider_conversion', 'merchant_reported']
    reference: str = Field(min_length=1, max_length=200)
    verified: bool = False
    approved_by_user_id: int | None = None
    permission_checked: bool = False
    suppressed: bool = False
    note: str = Field(default='', max_length=1000)


class PipelineTransition(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    previous_status: LeadStatus
    status: LeadStatus
    provenance: Literal['evidence_reviewed', 'provider_verified', 'merchant_reported']
    evidence_reference: str
    occurred_at: datetime


def transition_lead(
    *, business_id: str, actor_business_id: str, current_status: LeadStatus,
    next_status: LeadStatus, evidence: PipelineEvidence,
) -> PipelineTransition:
    if not business_id or business_id != actor_business_id or evidence.business_id != business_id:
        raise LeadError('forbidden_tenant', 'Lead status cannot be changed outside the authorized business.')
    steps = ['discovered', 'qualified', 'contacted', 'replied', 'converted']
    if current_status not in steps or next_status not in steps or steps.index(next_status) != steps.index(current_status) + 1:
        raise LeadError('invalid_transition', 'Advance the lead only after the next evidenced event.')
    if next_status == 'qualified':
        if evidence.kind != 'qualification' or not evidence.note.strip():
            raise LeadError('qualification_evidence_required', 'Qualification needs a source-backed merchant assessment.')
        provenance = 'evidence_reviewed'
    elif evidence.kind == 'merchant_reported':
        if not evidence.note.strip():
            raise LeadError('outcome_note_required', 'Manually reported outcomes need an explicit note.')
        provenance = 'merchant_reported'
    else:
        required = {'contacted': 'provider_send', 'replied': 'provider_reply', 'converted': 'provider_conversion'}[next_status]
        if evidence.kind != required or not evidence.verified:
            raise LeadError('verified_event_required', 'A verified provider event is required for this outcome.')
        if next_status == 'contacted' and (not evidence.approved_by_user_id or not evidence.permission_checked or evidence.suppressed):
            raise LeadError('outreach_not_authorized', 'Sending requires merchant approval, permission and suppression checks.')
        provenance = 'provider_verified'
    return PipelineTransition(previous_status=current_status, status=next_status,
        provenance=provenance, evidence_reference=evidence.reference, occurred_at=datetime.now(timezone.utc))
