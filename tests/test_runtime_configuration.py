"""Runtime precedence/rotation checks use only in-memory synthetic settings."""
import os
import subprocess
import sys
from collections.abc import Mapping

import pytest

from ayo.runtime_configuration import (
    AUTHORIZATION_SWITCHES, PROVIDER_CREDENTIALS,
    RuntimeConfigurationError, build_child_environment,
)


@pytest.fixture
def injected():
    return {
        'GEMINI_API_KEY': 'synthetic-injected-model-key',
        'FIRECRAWL_API_KEY': 'synthetic-injected-source-key',
        'GEMINI_MODEL': 'synthetic-reviewed-model',
        'AYO_PROVIDER_SPEND_AUTHORIZED': '0',
        'AYO_MAIL_SEND_AUTHORIZED': '0',
        'BASELINE_FIXTURE': 'preserved',
        'HTTPS_PROXY': 'http://synthetic-proxy.example:8080',
    }


def test_injected_configuration_always_wins_without_mutating_either_input(injected):
    fallback = {
        'GEMINI_API_KEY': 'synthetic-stale-local-key',
        'FIRECRAWL_API_KEY': 'synthetic-stale-source-key',
        'GEMINI_MODEL': 'synthetic-stale-model',
        'SESSION_SECRET': 'synthetic-local-session-setting',
    }
    original_injected, original_fallback = dict(injected), dict(fallback)
    result = build_child_environment(injected, fallback, credential_mode='local')
    assert all(result[name] == value for name, value in injected.items())
    assert result['SESSION_SECRET'] == fallback['SESSION_SECRET']
    assert injected == original_injected and fallback == original_fallback
    assert result is not injected and result is not fallback


def test_injected_mode_never_even_inspects_fallback(injected):
    class InaccessibleFallback(Mapping):
        def __getitem__(self, key):
            raise AssertionError('Fallback was accessed')

        def __iter__(self):
            raise AssertionError('Fallback was accessed')

        def __len__(self):
            raise AssertionError('Fallback was accessed')

    assert build_child_environment(injected, InaccessibleFallback()) == injected


@pytest.mark.parametrize('name', PROVIDER_CREDENTIALS)
@pytest.mark.parametrize('mode', ['injected', 'local'])
@pytest.mark.parametrize('invalid', [None, '', 'short', 'REPLACE_EXAMPLE_KEY', 'synthetic invalid whitespace'])
def test_missing_or_invalid_injected_key_cannot_be_revived_by_local_fallback(injected, name, mode, invalid):
    fallback = dict(injected)
    if invalid is None:
        del injected[name]
    else:
        injected[name] = invalid
    with pytest.raises(RuntimeConfigurationError) as error:
        build_child_environment(injected, fallback, credential_mode=mode)
    assert str(error.value) == 'Both provider credentials must be configured together in the selected runtime source.'
    assert 'synthetic' not in str(error.value)


def test_local_pair_fills_only_when_neither_key_is_injected(injected):
    fallback = {name: injected.pop(name) for name in PROVIDER_CREDENTIALS}
    result = build_child_environment(injected, fallback, credential_mode='local')
    assert all(result[name] == fallback[name] for name in PROVIDER_CREDENTIALS)


def test_injected_mode_does_not_use_even_a_complete_local_pair(injected):
    fallback = {name: injected.pop(name) for name in PROVIDER_CREDENTIALS}
    with pytest.raises(RuntimeConfigurationError):
        build_child_environment(injected, fallback)


@pytest.mark.parametrize('name', ['GEMINI_MODEL', 'GEMINI_MAX_OUTPUT_TOKENS', 'FIRECRAWL_ADAPTER_SETTING'])
def test_injected_pair_cannot_pick_up_local_provider_configuration(injected, name):
    injected.pop(name, None)
    result = build_child_environment(injected, {name: 'synthetic-stale-provider-setting'}, credential_mode='local')
    assert name not in result


@pytest.mark.parametrize('name', ['GEMINI_MODEL', *AUTHORIZATION_SWITCHES])
def test_explicitly_empty_injected_setting_never_uses_local_fallback(injected, name):
    injected[name] = ''
    local_value = '0' if name in AUTHORIZATION_SWITCHES else 'synthetic-local-fallback'
    if name in AUTHORIZATION_SWITCHES:
        with pytest.raises(RuntimeConfigurationError):
            build_child_environment(injected, {name: local_value}, credential_mode='local')
    else:
        assert build_child_environment(injected, {name: local_value}, credential_mode='local')[name] == ''


@pytest.mark.parametrize('switch', AUTHORIZATION_SWITCHES)
@pytest.mark.parametrize('local_value', ['1', 'true', '', 'synthetic-sensitive-invalid-value'])
def test_fallback_cannot_arm_or_ambiguously_configure_authorization(injected, switch, local_value):
    # Reject invalid fallback even if injection currently overrides it. It could
    # otherwise arm the next process when an injected switch is removed.
    with pytest.raises(RuntimeConfigurationError) as error:
        build_child_environment(injected, {switch: local_value}, credential_mode='local')
    assert str(error.value) == 'Local fallback must keep provider spending and mail delivery disabled.'
    assert 'synthetic-sensitive-invalid-value' not in str(error.value)


def test_missing_authorization_defaults_to_disabled_only_in_local_mode(injected):
    for switch in AUTHORIZATION_SWITCHES:
        del injected[switch]
    with pytest.raises(RuntimeConfigurationError):
        build_child_environment(injected)
    result = build_child_environment(injected, credential_mode='local')
    assert all(result[switch] == '0' for switch in AUTHORIZATION_SWITCHES)


@pytest.mark.parametrize('mode', ['injected', 'local'])
@pytest.mark.parametrize('switch', AUTHORIZATION_SWITCHES)
@pytest.mark.parametrize('injected_value', ['1', '', 'true'])
def test_enabled_or_ambiguous_injected_authorization_is_rejected_not_hidden(injected, mode, switch, injected_value):
    injected[switch] = injected_value
    original = dict(injected)
    with pytest.raises(RuntimeConfigurationError) as error:
        build_child_environment(injected, {switch: '0'}, credential_mode=mode)
    assert str(error.value) == 'Runtime preparation requires provider spending and mail delivery explicitly disabled.'
    assert injected == original


def test_managed_only_composition_does_not_remember_previous_local_pair(injected):
    fallback = {name: injected.pop(name) for name in PROVIDER_CREDENTIALS}
    assert build_child_environment(injected, fallback, credential_mode='local')
    with pytest.raises(RuntimeConfigurationError):
        build_child_environment(injected)


def test_unknown_source_mode_fails_without_echoing_input(injected):
    with pytest.raises(RuntimeConfigurationError) as error:
        build_child_environment(injected, credential_mode='synthetic-sensitive-mode')
    assert str(error.value) == 'Select injected or local runtime configuration.'


def test_synthetic_rotation_propagates_only_new_injected_keys_to_fresh_children(injected):
    # Child code asserts internally, never prints credentials or fingerprints.
    # No process environment or private file is read by this test.
    fallback = {
        'GEMINI_API_KEY': 'synthetic-stale-model-key',
        'FIRECRAWL_API_KEY': 'synthetic-stale-source-key',
    }
    for version in ('old', 'rotated'):
        model_key = f'synthetic-{version}-model-key'
        source_key = f'synthetic-{version}-source-key'
        fresh = dict(injected, PATH=os.defpath, GEMINI_API_KEY=model_key, FIRECRAWL_API_KEY=source_key)
        child = build_child_environment(fresh, fallback)
        command = (
            'import os; '
            f'assert os.environ["GEMINI_API_KEY"] == {model_key!r}; '
            f'assert os.environ["FIRECRAWL_API_KEY"] == {source_key!r}; '
            'assert os.environ["AYO_PROVIDER_SPEND_AUTHORIZED"] == "0"; '
            'assert os.environ["AYO_MAIL_SEND_AUTHORIZED"] == "0"'
        )
        completed = subprocess.run(
            [sys.executable, '-I', '-c', command], env=child,
            capture_output=True, text=True, check=False, timeout=10,
        )
        assert completed.returncode == 0
        assert completed.stdout == completed.stderr == ''


def test_provider_factories_read_current_injected_keys_without_network(monkeypatch):
    import httpx

    from ayo.intelligence import IntelligenceError, provider_from_env
    from ayo.research import FirecrawlProvider, ResearchError

    def blocked_request(*args, **kwargs):
        raise AssertionError('Provider factory attempted network access')

    async def blocked_async_request(*args, **kwargs):
        raise AssertionError('Provider factory attempted network access')

    monkeypatch.setattr(httpx.Client, 'send', blocked_request)
    monkeypatch.setattr(httpx.AsyncClient, 'send', blocked_async_request)
    # Replacing the whole environment avoids inspecting/inheriting real keys.
    # The synthetic authorization permits constructors only; no dispatch runs.
    environment = {
        'GEMINI_API_KEY': 'synthetic-initial-model-key',
        'GEMINI_MODEL': 'synthetic-test-model',
        'FIRECRAWL_API_KEY': 'synthetic-initial-source-key',
        'AYO_PROVIDER_SPEND_AUTHORIZED': '1',
        'AYO_AI_DATA_POLICY': 'public_only_reviewed',
        'AYO_RESEARCH_EGRESS_POLICY': 'provider_managed_verified',
        'AYO_RESEARCH_APPROVED_HOSTS': 'example.com',
    }
    monkeypatch.setattr(os, 'environ', environment)
    old_model, old_source = provider_from_env('gemini'), FirecrawlProvider.from_env()
    environment['GEMINI_API_KEY'] = 'synthetic-rotated-model-key'
    environment['FIRECRAWL_API_KEY'] = 'synthetic-rotated-source-key'
    new_model, new_source = provider_from_env('gemini'), FirecrawlProvider.from_env()
    assert new_model._api_key == environment['GEMINI_API_KEY']
    assert new_source._api_key == environment['FIRECRAWL_API_KEY']
    assert old_model._api_key != new_model._api_key and old_source._api_key != new_source._api_key

    del environment['GEMINI_API_KEY']
    del environment['FIRECRAWL_API_KEY']
    with pytest.raises(IntelligenceError, match='requires a configured API key'):
        provider_from_env('gemini')
    with pytest.raises(ResearchError, match='credentials are not configured'):
        FirecrawlProvider.from_env()
