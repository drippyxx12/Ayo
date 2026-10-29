"""Pure child-environment composition with injected configuration precedence.

This module never reads files, the process environment, or a provider. Callers
choose whether a local fallback is allowed before passing it here. Each call
builds a new snapshot; running processes still need restarting after rotation.
"""
from collections.abc import Mapping
import re

from ayo.provider_config import valid_api_key


AUTHORIZATION_SWITCHES = (
    'AYO_PROVIDER_SPEND_AUTHORIZED',
    'AYO_MAIL_SEND_AUTHORIZED',
)
PROVIDER_CREDENTIALS = ('GEMINI_API_KEY', 'FIRECRAWL_API_KEY')


class RuntimeConfigurationError(ValueError):
    """Configuration errors contain fixed text, never configuration values."""


def application_origin(configuration):
    """Use trusted platform configuration, never a request Host/forwarded header.

    Each protected Vercel preview has its own hostname. A stale fixed staging
    origin would reject valid browser POSTs after every branch rebuild.
    """
    if configuration.get('VERCEL_ENV') == 'preview':
        host = configuration.get('VERCEL_URL', '')
        if not isinstance(host, str) or not re.fullmatch(
                r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.vercel\.app', host):
            raise RuntimeConfigurationError('The protected preview deployment hostname is unavailable or invalid.')
        return 'https://' + host
    return configuration.get('APP_ORIGIN', 'http://localhost:8000').rstrip('/')


def build_child_environment(
    injected: Mapping[str, str], fallback: Mapping[str, str] | None = None,
    *, credential_mode: str = 'injected',
) -> dict[str, str]:
    """Prepare an explicitly disarmed child with one complete credential source.

    Injected mode never accesses fallback and requires both credentials and
    explicitly disabled switches. Their presence does not certify persistence,
    a managed binding, provider validity, or permission to make paid calls.

    Local mode requires the caller to select and read a fallback explicitly.
    Injected settings, including blanks, always win. If either provider key is
    injected, the entire provider pair must be injected; local provider values
    cannot complete a partial rotation or revive a removed credential. Missing
    local-mode authorization switches default to disabled. Enabled or ambiguous
    switches fail closed; the helper never silently changes an enabled switch.
    """
    if credential_mode not in {'injected', 'local'}:
        raise RuntimeConfigurationError('Select injected or local runtime configuration.')
    environment = dict(injected)
    if credential_mode == 'local':
        fallback = {} if fallback is None else fallback
        if any(name in fallback and fallback[name] != '0' for name in AUTHORIZATION_SWITCHES):
            raise RuntimeConfigurationError('Local fallback must keep provider spending and mail delivery disabled.')
        injected_pair = any(name in injected for name in PROVIDER_CREDENTIALS)
        for name, value in fallback.items():
            if injected_pair and name.startswith(('GEMINI_', 'FIRECRAWL_')):
                continue
            environment.setdefault(name, value)
        for name in AUTHORIZATION_SWITCHES:
            environment.setdefault(name, '0')
    if not all(valid_api_key(environment.get(name, '')) for name in PROVIDER_CREDENTIALS):
        raise RuntimeConfigurationError('Both provider credentials must be configured together in the selected runtime source.')
    if any(environment.get(name) != '0' for name in AUTHORIZATION_SWITCHES):
        raise RuntimeConfigurationError('Runtime preparation requires provider spending and mail delivery explicitly disabled.')
    return environment
