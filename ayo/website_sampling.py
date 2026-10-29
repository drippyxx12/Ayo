"""Bounded, deterministic selection of public links from a retrieved page."""
from dataclasses import dataclass
import re
from urllib.parse import parse_qsl, urlsplit

from ayo.research import SHARED_PUBLIC_HOSTS, ResearchError, SourceDocument, _candidate_identity, _public_url


@dataclass(frozen=True)
class WebsiteEvidence:
    sources: tuple[SourceDocument, ...]
    limitations: tuple[str, ...] = ()


def selected_page_links(source_url: str, links: tuple[str, ...], limit: int = 2) -> tuple[str, ...]:
    """One product/category and one policy/about page, without guessed URLs.

    Only actual same-site links qualify. Shared profiles cannot expand into
    unrelated merchants; identity-bearing queries and files are never stripped
    into a different guessed page. Selection does not authorize a fetch: every
    chosen page still passes the transport, public-path and robots checks.
    """
    host = (urlsplit(source_url).hostname or '').removeprefix('www.')
    if host in SHARED_PUBLIC_HOSTS:
        return ()
    groups = {'product': [], 'policy': []}
    seen = {_candidate_identity(source_url)}
    for link in links[:100]:
        try:
            raw = urlsplit(link)
        except ValueError:
            continue
        if any(not (key.startswith('utm_') or key in {'gclid', 'fbclid'})
               for key, _ in parse_qsl(raw.query, keep_blank_values=True)):
            continue
        try:
            url = _public_url(link)
        except (ResearchError, ValueError, TypeError):
            continue
        parsed = urlsplit(url)
        if ((parsed.hostname or '').removeprefix('www.') != host or
                (urlsplit(source_url).scheme == 'https' and parsed.scheme != 'https')):
            continue
        identity = _candidate_identity(url)
        if identity in seen or re.search(r'\.(?:pdf|zip|png|jpe?g|gif|svg|webp|mp4|docx?|xlsx?)$', parsed.path, re.I):
            continue
        seen.add(identity)
        path = parsed.path.casefold()
        if re.search(r'/(?:products?|collections?|shop|catalog(?:ue)?|categor(?:y|ies)|product-categor(?:y|ies))(?:/|[-.]|$)', path):
            groups['product'].append(url)
        elif re.search(r'/(?:[^/]*[-_])?(?:shipping|delivery|returns?|refunds?|about)(?:[-_./]|$)', path):
            groups['policy'].append(url)
    # Preserve original link order within each group. Prefer distinct coverage
    # over fetching two similar product pages when a policy page is available.
    selected = [items[0] for items in groups.values() if items]
    remaining = [url for items in groups.values() for url in items[1:]]
    return tuple((selected + remaining)[:max(0, min(limit, 2))])
