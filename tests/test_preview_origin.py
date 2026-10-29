"""Rotating preview hostnames must work without trusting request headers."""
import pytest

from ayo import app as mod
from ayo.runtime_configuration import RuntimeConfigurationError, application_origin
from test_platform_flow import platform, csrf  # noqa: F401


def test_preview_origin_uses_exact_platform_hostname_and_preserves_production():
    configuration = {'VERCEL_ENV': 'preview', 'VERCEL_URL': 'ayo-staging-new-build.vercel.app',
                     'APP_ORIGIN': 'https://old-staging.vercel.app'}
    assert application_origin(configuration) == 'https://ayo-staging-new-build.vercel.app'
    assert application_origin({**configuration, 'VERCEL_ENV': 'production'}) == configuration['APP_ORIGIN']
    assert application_origin({'APP_ORIGIN': 'http://localhost:8000/'}) == 'http://localhost:8000'


@pytest.mark.parametrize('host', ['', 'evil.example.org', 'ayo.vercel.app.evil.org',
    'https://ayo.vercel.app', 'ayo.vercel.app/path', 'ayo.vercel.app:443',
    'user@ayo.vercel.app', 'ayo.vercel.app\n', '-invalid.vercel.app'])
def test_invalid_preview_hostname_fails_closed_without_configuration_echo(host):
    with pytest.raises(RuntimeConfigurationError):
        application_origin({'VERCEL_ENV': 'preview', 'VERCEL_URL': host})


def test_preview_browser_post_accepts_its_rotating_origin_but_denies_spoofed_origin(platform, monkeypatch):
    origin = application_origin({'VERCEL_ENV': 'preview', 'VERCEL_URL': 'ayo-current-preview.vercel.app'})
    monkeypatch.setattr(mod, 'ORIGIN', origin)
    token = csrf(platform.client)
    data = {'csrf': token, 'query': 'https://fixture-clothing.org/', 'country': 'GH'}
    assert platform.client.post('/research', data=data, headers={'Origin': origin}).status_code == 303
    assert platform.client.post('/research', data=data, headers={'Origin': 'https://spoofed.example.org'}).status_code == 403
