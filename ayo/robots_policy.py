"""Bounded robots path matching and pacing for Ayo's public-page reader.

Use the most specific matching agent groups and path rule, with Allow winning
equal-length ties. Wildcards are matched without backtracking regular
expressions, since robots text is untrusted input.
"""
from dataclasses import dataclass
import math
import re
from urllib.parse import quote, unquote_to_bytes, urlsplit


def _octets(value):
    value = quote(value, safe="/!$&'()*+,-._~:@?=%")
    def normalize(match):
        char = chr(int(match.group()[1:], 16))
        return char if char.isascii() and (char.isalnum() or char in '-._~') else match.group().upper()
    return re.sub(r'%[0-9a-fA-F]{2}', normalize, value)


def _matches(pattern, path):
    anchored = pattern.endswith('$')
    pattern = pattern[:-1] if anchored else pattern
    parts = pattern.split('*')
    if len(parts) == 1:
        return path == pattern if anchored else path.startswith(pattern)
    if not path.startswith(parts[0]):
        return False
    position = len(parts[0])
    for part in parts[1:-1]:
        index = path.find(part, position)
        if index < 0:
            return False
        position = index + len(part)
    tail = parts[-1]
    return (path.endswith(tail) and len(path) - len(tail) >= position) if anchored else path.find(tail, position) >= 0


@dataclass(frozen=True)
class _Group:
    agents: tuple[str, ...]
    rules: tuple[tuple[str, bool], ...]
    delay: float


class RobotsPolicy:
    def __init__(self, text):
        if len(text) > 200_000:
            raise ValueError('Robots policy exceeds its parsing bound.')
        self.groups = []
        agents, rules, delay, directives = [], [], 0, False
        for raw in (*text.splitlines(), 'User-agent: __end__'):
            key, separator, value = raw.split('#', 1)[0].partition(':')
            if not separator:
                continue
            key, value = key.strip().casefold(), value.strip()
            if key == 'user-agent':
                if agents and directives:
                    self.groups.append(_Group(tuple(agents), tuple(rules), delay))
                    agents, rules, delay, directives = [], [], 0, False
                agents.append(value.casefold())
            elif agents and key in {'allow', 'disallow', 'crawl-delay', 'request-rate'}:
                directives = True
                if key in {'allow', 'disallow'}:
                    if value:
                        rules.append((_octets(value), key == 'allow'))
                else:
                    try:
                        if key == 'request-rate':
                            count, seconds = value.split('/', 1)
                            pacing = float(seconds) / float(count)
                        else:
                            pacing = float(value)
                        if math.isfinite(pacing) and pacing >= 0:
                            delay = max(delay, pacing)
                    except (ValueError, ZeroDivisionError):
                        pass

    def _selected(self, agent):
        product = agent.split('/', 1)[0].casefold()
        matches = [(max((len(token) if token != '*' else 0 for token in group.agents
                         if token and (token == '*' or token in product)), default=-1), group)
                   for group in self.groups]
        specificity = max((score for score, _ in matches), default=-1)
        return [group for score, group in matches if score == specificity and score >= 0]

    def can_fetch(self, agent, url):
        parsed = urlsplit(url)
        path = _octets((parsed.path or '/') + ('?' + parsed.query if parsed.query else ''))
        matching = [(len(unquote_to_bytes(pattern.replace('*', '').removesuffix('$'))), allow)
                    for group in self._selected(agent) for pattern, allow in group.rules if _matches(pattern, path)]
        return max(matching, default=(-1, True))[1]

    def delay_seconds(self, agent):
        return max((group.delay for group in self._selected(agent)), default=0)
