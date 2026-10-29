"""Migration evidence stays offline and redacted using synthetic inputs only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'check-secret-migration.py'
spec = importlib.util.spec_from_file_location('ayo_secret_migration', SCRIPT)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)

SYNTHETIC_KEYS = {
    'GEMINI_API_KEY': 'synthetic-inherited-model-key',
    'FIRECRAWL_API_KEY': 'synthetic-inherited-source-key',
}
PROOF_FIELDS = (
    'cloud_binding_provisioning_verified', 'environment_recreation_verified',
    'provider_key_rotation_verified', 'provider_live_api_validated',
)


@pytest.fixture(autouse=True)
def synthetic_environment(monkeypatch):
    # Replace the entire mapping, never inspect or inherit runner credentials.
    environment = {
        'PATH': os.defpath, **SYNTHETIC_KEYS,
        'AYO_PROVIDER_SPEND_AUTHORIZED': '0', 'AYO_MAIL_SEND_AUTHORIZED': '0',
    }
    monkeypatch.setattr(os, 'environ', environment)

    def blocked(*args, **kwargs):
        pytest.fail('Offline migration check attempted networking')

    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket.socket, 'connect_ex', blocked)
    monkeypatch.setattr(socket, 'getaddrinfo', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)
    return environment


def forbidden_loader(*args, **kwargs):
    pytest.fail('Migration check accessed an unrequested local configuration')


def assert_metadata_only(report, *additional_values):
    assert report['schema_version'] == 1
    assert report['mode'] == 'offline_inherited_configuration_only'
    assert report['process_source'] in ('inherited_environment', 'local_file', 'unknown')
    assert set(report['credential_shape_checks']) == set(SYNTHETIC_KEYS)
    assert all(type(value) is bool for value in report['credential_shape_checks'].values())
    assert type(report['provider_and_mail_explicitly_disabled']) is bool
    assert type(report['runtime_configuration_ready']) is bool
    assert report['local_comparison'] in ('not_requested', 'not_attempted', 'matched', 'mismatch', 'unavailable')
    assert all(report[name] is False for name in PROOF_FIELDS)
    assert report['network_requests_made'] == 0
    assert len(report['remaining_proof']) == 4
    assert all(type(item) is str for item in report['remaining_proof'])
    serialized = json.dumps(report)
    for value in (*SYNTHETIC_KEYS.values(), *additional_values):
        assert value not in serialized
        assert hashlib.sha256(value.encode()).hexdigest() not in serialized
    return serialized


def test_inherited_shape_and_disabled_switches_are_only_configuration_evidence(synthetic_environment, monkeypatch):
    monkeypatch.setattr(migration.importlib.util, 'spec_from_file_location', forbidden_loader)
    before = dict(synthetic_environment)
    report = migration.check_migration(loader=forbidden_loader)
    assert report['runtime_configuration_ready'] is True
    assert all(report['credential_shape_checks'].values())
    assert report['provider_and_mail_explicitly_disabled'] is True
    assert report['local_comparison'] == 'not_requested'
    assert_metadata_only(report)
    assert synthetic_environment == before


@pytest.mark.parametrize('source,expected,ready', [
    ('inherited_environment', 'inherited_environment', True),
    ('local_file', 'local_file', False),
    ('synthetic-sensitive-source-name', 'unknown', False),
    (None, 'unknown', False), (True, 'unknown', False), (17, 'unknown', False),
    ([], 'unknown', False), ({}, 'unknown', False), (set(), 'unknown', False),
])
def test_only_inherited_source_can_be_ready_without_echoing_untrusted_source(
        synthetic_environment, source, expected, ready):
    synthetic_environment['AYO_RUNTIME_INPUT_SOURCE'] = source
    report = migration.check_migration(compare_local=True, loader=forbidden_loader if not ready else lambda _: SYNTHETIC_KEYS)
    assert report['process_source'] == expected
    assert report['runtime_configuration_ready'] is ready
    assert report['local_comparison'] == ('matched' if ready else 'not_attempted')
    assert_metadata_only(report, 'synthetic-sensitive-source-name')


@pytest.mark.parametrize('name', SYNTHETIC_KEYS)
@pytest.mark.parametrize('value', [None, '', 'short', 'REPLACE_EXAMPLE_KEY', 'synthetic whitespace',
                                  'synthetic-unicode-\u00e9', 'x' * 513, [], {}, True])
def test_invalid_pair_cannot_trigger_comparison_or_claim_readiness(synthetic_environment, name, value):
    synthetic_environment[name] = value
    report = migration.check_migration(compare_local=True, loader=forbidden_loader)
    assert report['credential_shape_checks'][name] is False
    assert report['runtime_configuration_ready'] is False
    assert report['local_comparison'] == 'not_attempted'
    assert_metadata_only(report)


@pytest.mark.parametrize('name', SYNTHETIC_KEYS)
def test_removed_credential_cannot_be_supplied_by_comparison(synthetic_environment, name):
    del synthetic_environment[name]
    report = migration.check_migration(compare_local=True, loader=forbidden_loader)
    assert report['credential_shape_checks'][name] is False
    assert report['runtime_configuration_ready'] is False
    assert report['local_comparison'] == 'not_attempted'
    assert_metadata_only(report)


@pytest.mark.parametrize('switch', migration.AUTHORIZATION_SWITCHES)
@pytest.mark.parametrize('value', [None, '', '1', 'true', '00', 0, False])
def test_both_switches_must_be_exact_disabled_strings_without_rewriting(synthetic_environment, switch, value):
    synthetic_environment[switch] = value
    before = dict(synthetic_environment)
    report = migration.check_migration(compare_local=True, loader=forbidden_loader)
    assert report['provider_and_mail_explicitly_disabled'] is False
    assert report['runtime_configuration_ready'] is False
    assert report['local_comparison'] == 'not_attempted'
    assert synthetic_environment == before
    assert_metadata_only(report)


@pytest.mark.parametrize('switch', migration.AUTHORIZATION_SWITCHES)
def test_missing_authorization_switch_is_not_silently_defaulted(synthetic_environment, switch):
    del synthetic_environment[switch]
    report = migration.check_migration(compare_local=True, loader=forbidden_loader)
    assert report['provider_and_mail_explicitly_disabled'] is False
    assert report['runtime_configuration_ready'] is False
    assert_metadata_only(report)


@pytest.mark.parametrize('length', [8, 512])
def test_accepted_key_shape_never_means_provider_validation(synthetic_environment, length):
    synthetic_environment.update({name: 'k' * length for name in SYNTHETIC_KEYS})
    report = migration.check_migration()
    assert report['runtime_configuration_ready'] is True
    assert all(report[name] is False for name in PROOF_FIELDS)
    assert_metadata_only(report, 'k' * length)


@pytest.mark.parametrize('matching', [(True, True), (False, True), (True, False), (False, False)])
def test_complete_pair_uses_both_constant_time_comparisons_and_emits_only_pair_result(
        synthetic_environment, tmp_path, monkeypatch, matching):
    local = {name: value if matches else f'synthetic-different-{name}'
             for (name, value), matches in zip(SYNTHETIC_KEYS.items(), matching, strict=True)}
    local['AYO_SYNTHETIC_EXTRA'] = 'synthetic-local-extra-never-in-report'
    original_local = dict(local)
    original_environment = dict(synthetic_environment)
    path = tmp_path / 'explicit-synthetic-runtime.env'
    calls, paths = [], []
    compare_digest = migration.secrets.compare_digest

    def compare(left, right):
        calls.append((left, right))
        return compare_digest(left, right)

    def loader(selected_path):
        paths.append(selected_path)
        return local

    monkeypatch.setattr(migration.secrets, 'compare_digest', compare)
    report = migration.check_migration(compare_local=True, local_file=path, loader=loader)
    assert paths == [path]
    assert calls == [(SYNTHETIC_KEYS[name], local[name]) for name in SYNTHETIC_KEYS]
    assert report['local_comparison'] == ('matched' if all(matching) else 'mismatch')
    assert report['runtime_configuration_ready'] is True
    assert_metadata_only(report, *local.values())
    assert local == original_local and synthetic_environment == original_environment


@pytest.mark.parametrize('value', [None, [], {}, True, 'synthetic-unicode-\u00e9', 'short'])
def test_invalid_local_shape_cannot_match_or_abort_the_other_comparison(synthetic_environment, monkeypatch, value):
    local = dict(SYNTHETIC_KEYS, GEMINI_API_KEY=value)
    compared = []
    compare_digest = migration.secrets.compare_digest

    def compare(left, right):
        compared.append((left, right))
        return compare_digest(left, right)

    monkeypatch.setattr(migration.secrets, 'compare_digest', compare)
    report = migration.check_migration(compare_local=True, loader=lambda _: local)
    assert report['local_comparison'] == 'mismatch'
    assert len(compared) == 2
    assert compared[0][1] == ''
    assert compared[1][1] == SYNTHETIC_KEYS['FIRECRAWL_API_KEY']
    assert_metadata_only(report)


@pytest.mark.parametrize('local', [None, [], 'synthetic-sensitive-nonmapping-result'])
def test_unusable_loader_result_stays_unavailable_without_raw_errors(local):
    report = migration.check_migration(compare_local=True, loader=lambda _: local)
    assert report['local_comparison'] == 'unavailable'
    assert_metadata_only(report, 'synthetic-sensitive-nonmapping-result')


def test_loader_exception_is_redacted_and_does_not_claim_comparison():
    def loader(_):
        raise ValueError('synthetic-sensitive-error-value')

    report = migration.check_migration(compare_local=True, loader=loader)
    assert report['local_comparison'] == 'unavailable'
    assert_metadata_only(report, 'synthetic-sensitive-error-value')


@pytest.fixture
def network_guard(tmp_path):
    hooks = tmp_path / 'synthetic-network-guard'
    hooks.mkdir()
    loaded, attempted = hooks / 'loaded', hooks / 'network-attempted'
    (hooks / 'sitecustomize.py').write_text(
        'import pathlib,socket\n'
        f'pathlib.Path({str(loaded)!r}).touch()\n'
        'def blocked(*args, **kwargs):\n'
        f'    pathlib.Path({str(attempted)!r}).touch()\n'
        '    raise AssertionError("Offline synthetic CLI forbids networking")\n'
        'socket.socket.connect = blocked\n'
        'socket.socket.connect_ex = blocked\n'
        'socket.getaddrinfo = blocked\n'
        'socket.create_connection = blocked\n', encoding='utf-8')
    return hooks, loaded, attempted


@pytest.mark.parametrize('case,expected_code,comparison', [
    ('inherited', 0, 'not_requested'), ('missing-pair', 2, 'not_requested'),
    ('armed', 2, 'not_requested'), ('local-source', 2, 'not_attempted'),
    ('matched', 0, 'matched'), ('mismatch', 2, 'mismatch'),
    ('unavailable', 2, 'unavailable'), ('ignored-file', 0, 'not_requested'),
])
def test_cli_uses_only_isolated_synthetic_inputs_with_network_blocked(
        synthetic_environment, network_guard, tmp_path, case, expected_code, comparison):
    hooks, loaded, attempted = network_guard
    environment = dict(synthetic_environment, PYTHONPATH=str(hooks))
    directory = tmp_path / 'synthetic-private'
    directory.mkdir(mode=0o700)
    path = directory / 'runtime.env'
    values = dict(SYNTHETIC_KEYS)
    if case == 'mismatch':
        values['GEMINI_API_KEY'] = 'synthetic-different-local-key'
    path.write_text(''.join(f'{name}={value}\n' for name, value in values.items()), encoding='utf-8')
    path.chmod(0o600)
    args = []
    if case == 'missing-pair':
        del environment['FIRECRAWL_API_KEY']
    elif case == 'armed':
        environment['AYO_PROVIDER_SPEND_AUTHORIZED'] = '1'
    elif case == 'local-source':
        environment['AYO_RUNTIME_INPUT_SOURCE'] = 'local_file'
        path.unlink()
        args = ['--compare-local', '--local-file', str(path)]
    elif case in ('matched', 'mismatch', 'unavailable'):
        args = ['--compare-local', '--local-file', str(path)]
        if case == 'unavailable':
            path.unlink()
    elif case == 'ignored-file':
        path.write_text('synthetic-invalid-contents-never-read', encoding='utf-8')
        args = ['--local-file', str(path)]
    completed = subprocess.run([sys.executable, str(SCRIPT), *args], env=environment,
                               capture_output=True, text=True, check=False, timeout=10)
    assert completed.returncode == expected_code
    assert completed.stderr == ''
    report = json.loads(completed.stdout)
    assert report['local_comparison'] == comparison
    assert_metadata_only(report, 'synthetic-different-local-key', 'synthetic-invalid-contents-never-read')
    assert loaded.exists() and not attempted.exists()
