"""At most two public, pinned HTTPS GETs; no redirects, model or provider fees."""
import asyncio
from dataclasses import dataclass
import hashlib

from ayo.public_http import PublicHTTPClient, USER_AGENT
from ayo.research import ResearchError, _access_wall
from ayo.robots_policy import RobotsPolicy

PROOF_PATH = '/.well-known/ayo-site-verification.txt'


@dataclass(frozen=True)
class FileProof:
    content_hash: str
    body_hash: str


class SiteFileReader:
    def __init__(self, *, request=None, resolver=None, deadline_seconds=15):
        if not 0 < deadline_seconds <= 15:
            raise ValueError('Verification must finish within its lease.')
        options = {'request': request, 'timeout_seconds': 6}
        if resolver is not None:
            options['resolver'] = resolver
        self.robots = PublicHTTPClient(max_body_bytes=65536, **options)
        self.file = PublicHTTPClient(max_body_bytes=4096, **options)
        self.deadline = deadline_seconds

    async def read(self, host):
        # Validate again at this boundary; callers cannot select an arbitrary path.
        from ayo.site_control import site_host
        host = site_host(host)
        try:
            async with asyncio.timeout(self.deadline):
                return await self._read(host)
        except TimeoutError:
            raise ResearchError('verification_timeout', 'The website check exceeded its deadline.', 504) from None

    async def _read(self, host):
        origin = 'https://' + host
        target = origin + PROOF_PATH
        robots = await self.robots.fetch_once(origin + '/robots.txt')
        if robots.status not in {404, 410}:
            if robots.status != 200 or robots.headers.get('content-type', '').split(';')[0].strip().lower() not in {'text/plain', 'text/x-robots'}:
                raise ResearchError('robots_unavailable', 'The website robots policy could not be checked.', 422)
            try:
                text = robots.body.decode('utf-8-sig')
            except UnicodeDecodeError:
                raise ResearchError('robots_unavailable', 'The website robots policy could not be checked.', 422) from None
            rules = RobotsPolicy(text)
            if _access_wall(text) or not rules.can_fetch(USER_AGENT, target):
                raise ResearchError('robots_denied', 'The website robots policy prevents this check.', 422)
            delay = rules.delay_seconds(USER_AGENT)
            if delay > 5:
                raise ResearchError('robots_pacing', 'The website requires a slower verification method.', 422)
            if delay:
                await asyncio.sleep(delay)
        result = await self.file.fetch_once(target)
        if result.status != 200:
            raise ResearchError('verification_file_unavailable', 'The HTTPS verification file was not accessible without redirects.', 422)
        content_type = result.headers.get('content-type', '').split(';')[0].strip().lower()
        if content_type != 'text/plain' or result.headers.get('content-encoding', 'identity').lower() != 'identity':
            raise ResearchError('verification_file_type', 'Serve the verification file as uncompressed plain text.', 422)
        content = result.body.removesuffix(b'\n').removesuffix(b'\r')
        return FileProof(hashlib.sha256(content).hexdigest(), hashlib.sha256(result.body).hexdigest())
