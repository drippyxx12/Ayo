"""Private-runtime wrapper regressions using synthetic temporary files only."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'with-private-runtime.py'
spec = importlib.util.spec_from_file_location('ayo_private_runtime', SCRIPT)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)

SYNTHETIC_VALUE = 'offline-fixture-private-runtime-value'


@pytest.fixture(autouse=True)
def synthetic_environment(monkeypatch):
    # Never inherit, inspect or pass the test runner's real runtime configuration.
    environment = {'PATH': os.defpath, 'BASELINE_FIXTURE': 'unchanged'}
    monkeypatch.setattr(os, 'environ', environment)
    return environment


@pytest.fixture
def private_file(tmp_path):
    directory = tmp_path / 'synthetic-private'
    directory.mkdir(mode=0o700)
    path = directory / 'runtime.env'
    path.write_text(f'GEMINI_API_KEY={SYNTHETIC_VALUE}\n'
                    'GEMINI_MODEL=offline-fixture-model\n'
                    'FIRECRAWL_API_KEY=offline-fixture-source-value\n'
                    'AYO_PROVIDER_SPEND_AUTHORIZED=0\n'
                    'AYO_MAIL_SEND_AUTHORIZED=0\n', encoding='utf-8')
    path.chmod(0o600)
    return path


def assert_redacted_failure(result, capfd, *raw_values):
    captured = capfd.readouterr()
    assert result == 2
    assert not captured.out
    assert captured.err
    assert 'Traceback' not in captured.err
    assert all(value not in captured.err for value in (SYNTHETIC_VALUE, *raw_values))


def test_loading_only_returns_configuration_and_never_mutates_environment(private_file, synthetic_environment):
    before = dict(synthetic_environment)
    values = runtime.load_private_configuration(private_file)
    assert values['GEMINI_API_KEY'] == SYNTHETIC_VALUE
    assert values['AYO_PROVIDER_SPEND_AUTHORIZED'] == '0'
    assert synthetic_environment == before


def test_default_private_location_is_outside_git_checkout_without_accessing_it():
    # Lexical checks only: the actual default directory/file is never inspected.
    assert runtime.DEFAULT_ENV_FILE.is_absolute()
    assert not runtime.DEFAULT_ENV_FILE.is_relative_to(runtime.ROOT)
    assert runtime.DEFAULT_ENV_FILE.name == 'runtime.env'


@pytest.mark.parametrize('mode', [0o640, 0o644, 0o660, 0o666])
def test_group_or_world_readable_file_is_rejected(private_file, capfd, mode):
    private_file.chmod(mode)
    assert_redacted_failure(runtime.main(['--env-file', str(private_file)]), capfd)


@pytest.mark.parametrize('mode', [0o710, 0o740, 0o750, 0o770, 0o755, 0o777])
def test_directory_must_be_owner_only(private_file, capfd, mode):
    private_file.parent.chmod(mode)
    assert_redacted_failure(runtime.main(['--env-file', str(private_file)]), capfd)


def test_directory_owner_must_match_effective_user(private_file, monkeypatch, capfd):
    owner = private_file.parent.stat().st_uid
    monkeypatch.setattr(runtime.os, 'geteuid', lambda: owner + 1)
    assert_redacted_failure(runtime.main(['--env-file', str(private_file)]), capfd)


def test_file_owner_must_match_effective_user(private_file, monkeypatch, capfd):
    original_fstat = runtime.os.fstat

    def foreign_owner(descriptor):
        metadata = original_fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            return metadata
        return SimpleNamespace(st_mode=metadata.st_mode, st_uid=metadata.st_uid + 1,
                               st_size=metadata.st_size)

    monkeypatch.setattr(runtime.os, 'fstat', foreign_owner)
    assert_redacted_failure(runtime.main(['--env-file', str(private_file)]), capfd)


def test_symlink_file_is_rejected(private_file, capfd):
    link = private_file.with_name('linked.env')
    link.symlink_to(private_file)
    assert_redacted_failure(runtime.main(['--env-file', str(link)]), capfd)


def test_symlink_parent_directory_is_rejected(private_file, tmp_path, capfd):
    link = tmp_path / 'linked-private'
    link.symlink_to(private_file.parent, target_is_directory=True)
    assert_redacted_failure(runtime.main(['--env-file', str(link / private_file.name)]), capfd)


def test_symlink_in_earlier_ancestor_is_rejected(private_file, tmp_path, capfd):
    link = tmp_path / 'linked-ancestor'
    link.symlink_to(tmp_path, target_is_directory=True)
    path = link / private_file.parent.name / private_file.name
    assert_redacted_failure(runtime.main(['--env-file', str(path)]), capfd)


@pytest.mark.parametrize('replacement_kind', ['directory', 'symlink'])
def test_renamed_parent_cannot_redirect_file_lookup(
        private_file, tmp_path, monkeypatch, replacement_kind):
    original_open = runtime.os.open
    original_parent = private_file.parent
    retired_parent = tmp_path / 'retired-private'
    alternate_parent = tmp_path / 'alternate-private'
    alternate_parent.mkdir(mode=0o700)
    alternate_file = alternate_parent / private_file.name
    alternate_file.write_text('GEMINI_API_KEY=alternate-offline-fixture\n', encoding='utf-8')
    alternate_file.chmod(0o600)
    replaced = False

    def replace_parent_at_file_open(path, flags, *args, **kwargs):
        nonlocal replaced
        if path == private_file.name and kwargs.get('dir_fd') is not None and not replaced:
            replaced = True
            original_parent.rename(retired_parent)
            if replacement_kind == 'symlink':
                original_parent.symlink_to(alternate_parent, target_is_directory=True)
            else:
                alternate_parent.rename(original_parent)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(runtime.os, 'open', replace_parent_at_file_open)
    values = runtime.load_private_configuration(private_file)
    assert replaced
    assert values['GEMINI_API_KEY'] == SYNTHETIC_VALUE
    assert (retired_parent / private_file.name).exists()
    assert private_file.read_text() == 'GEMINI_API_KEY=alternate-offline-fixture\n'


@pytest.mark.parametrize('kind', ['missing-file', 'missing-directory', 'directory', 'oversized', 'invalid-utf8'])
def test_unusable_configuration_fails_without_traceback_or_values(private_file, capfd, kind):
    if kind == 'missing-file':
        private_file.unlink()
    elif kind == 'missing-directory':
        private_file.unlink()
        private_file.parent.rmdir()
    elif kind == 'directory':
        private_file.unlink()
        private_file.mkdir(mode=0o700)
    elif kind == 'oversized':
        private_file.write_text('GEMINI_API_KEY=' + SYNTHETIC_VALUE + 'x' * 65536, encoding='utf-8')
    else:
        private_file.write_bytes(b'GEMINI_API_KEY=\xff\xfe')
    assert_redacted_failure(runtime.main(['--env-file', str(private_file)]), capfd)


@pytest.mark.parametrize('contents', ['', '# only a comment\n', 'lowercase=bad-value\n', 'GEMINI_API_KEY\n'])
def test_empty_or_invalid_configuration_is_rejected(private_file, capfd, contents):
    private_file.write_text(contents, encoding='utf-8')
    assert_redacted_failure(runtime.main(['--env-file', str(private_file)]), capfd, 'bad-value')


@pytest.mark.parametrize('contents', [
    'GEMINI_API_KEY=first-offline-fixture\nGEMINI_API_KEY=second-offline-fixture\n',
    'GEMINI_API_KEY=valid-offline-fixture\nnot a valid binding\n',
    'GEMINI_API_KEY=valid-offline-fixture\nFIRECRAWL_API_KEY="unterminated\n',
])
def test_duplicate_or_partially_malformed_configuration_is_rejected(private_file, capfd, contents):
    private_file.write_text(contents, encoding='utf-8')
    assert_redacted_failure(runtime.main(['--env-file', str(private_file)]), capfd,
                           'first-offline-fixture', 'second-offline-fixture', 'valid-offline-fixture')


@pytest.mark.parametrize('name', ['PATH', 'HOME', 'PYTHONPATH', 'PYTHONHOME', 'LD_PRELOAD',
                                 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'UNKNOWN_TOKEN'])
def test_configuration_cannot_override_system_or_unrecognized_environment(private_file, capfd, name):
    private_file.write_text(f'{name}={SYNTHETIC_VALUE}\n', encoding='utf-8')
    assert_redacted_failure(runtime.main(['--env-file', str(private_file)]), capfd)


@pytest.mark.parametrize('name', ['AYO_TEST_SETTING', 'GEMINI_API_KEY', 'FIRECRAWL_API_KEY',
                                 'ANTHROPIC_API_KEY', 'SHOPIFY_API_KEY', 'DATABASE_URL',
                                 'SESSION_SECRET', 'TOKEN_ENCRYPTION_KEY', 'APP_ORIGIN',
                                 'ENVIRONMENT', 'RESEND_API_KEY', 'MAIL_FROM'])
def test_supported_application_configuration_is_loaded_as_literal_values(private_file, name):
    private_file.write_text(f'{name}={SYNTHETIC_VALUE}\n', encoding='utf-8')
    assert runtime.load_private_configuration(private_file) == {name: SYNTHETIC_VALUE}


def test_fifo_configuration_is_rejected_promptly_without_child_launch(
        private_file, synthetic_environment):
    private_file.unlink()
    os.mkfifo(private_file, mode=0o600)
    completed = subprocess.run([sys.executable, str(SCRIPT), '--env-file', str(private_file)],
                               env=synthetic_environment, capture_output=True, text=True, timeout=5)
    assert completed.returncode == 2
    assert not completed.stdout and completed.stderr
    assert 'Traceback' not in completed.stderr
    assert SYNTHETIC_VALUE not in completed.stderr


def test_null_bytes_fail_closed_without_launch_traceback(private_file, capfd):
    private_file.write_text(f'GEMINI_API_KEY={SYNTHETIC_VALUE}\x00invalid\n', encoding='utf-8')
    assert_redacted_failure(runtime.main(['--env-file', str(private_file)]), capfd)


def test_configuration_is_literal_without_environment_or_shell_expansion(private_file, tmp_path):
    marker = tmp_path / 'must-not-exist'
    literal = '${BASELINE_FIXTURE} $(touch ' + str(marker) + ') `touch ' + str(marker) + '`'
    private_file.write_text('GEMINI_API_KEY=' + literal + '\n', encoding='utf-8')
    assert runtime.load_private_configuration(private_file)['GEMINI_API_KEY'] == literal
    assert not marker.exists()


def test_explicit_child_inherits_loaded_values_and_exit_code_only_on_invocation(
        private_file, tmp_path, synthetic_environment, capfd):
    marker = tmp_path / 'child-was-invoked'
    command = ('import os,pathlib,sys; '
               f'assert os.environ["GEMINI_API_KEY"] == {SYNTHETIC_VALUE!r}; '
               'assert os.environ["BASELINE_FIXTURE"] == "unchanged"; '
               f'pathlib.Path({str(marker)!r}).write_text("invoked"); sys.exit(7)')
    runtime.load_private_configuration(private_file)
    assert not marker.exists()
    result = runtime.main(['--env-file', str(private_file), '--', sys.executable, '-c', command])
    assert result == 7
    assert marker.read_text() == 'invoked'
    assert 'GEMINI_API_KEY' not in synthetic_environment
    captured = capfd.readouterr()
    assert not captured.out and not captured.err


def test_missing_child_command_fails_without_raw_command_or_configuration(private_file, tmp_path, capfd):
    missing_command = tmp_path / (SYNTHETIC_VALUE + '-missing-command')
    result = runtime.main(['--env-file', str(private_file), '--', str(missing_command)])
    assert_redacted_failure(result, capfd, str(missing_command))


def test_default_preparation_is_offline_redacted_and_never_arms_configuration(
        private_file, tmp_path, synthetic_environment, capfd):
    hooks = tmp_path / 'network-guard'
    hooks.mkdir()
    loaded_marker = hooks / 'loaded'
    network_marker = hooks / 'network-attempted'
    (hooks / 'sitecustomize.py').write_text(
        'import pathlib,socket\n'
        f'pathlib.Path({str(loaded_marker)!r}).touch()\n'
        'def blocked(*args, **kwargs):\n'
        f'    pathlib.Path({str(network_marker)!r}).touch()\n'
        '    raise AssertionError("Offline fixture forbids networking")\n'
        'socket.socket.connect = blocked\n'
        'socket.socket.connect_ex = blocked\n'
        'socket.getaddrinfo = blocked\n'
        'socket.create_connection = blocked\n', encoding='utf-8')
    synthetic_environment['PYTHONPATH'] = str(hooks)
    before = private_file.read_bytes()
    assert runtime.main(['--env-file', str(private_file)]) == 2
    captured = capfd.readouterr()
    result = json.loads(captured.out)
    assert not captured.err
    assert result['mode'] == 'offline_configuration_only'
    assert result['readiness_mode'] == 'prepare'
    assert result['network_requests_made'] == 0
    assert result['live_verified'] is False
    checks = {item['id']: item['status'] for item in result['provider_checks']}
    assert checks['gemini_credential'] == 'configured'
    assert checks['provider_spending_disabled'] == checks['mail_delivery_disabled'] == 'configured'
    assert loaded_marker.exists() and not network_marker.exists()
    assert SYNTHETIC_VALUE not in captured.out
    assert 'offline-fixture-model' not in captured.out
    assert 'offline-fixture-source-value' not in captured.out
    assert 'GEMINI_API_KEY' not in synthetic_environment
    assert private_file.read_bytes() == before


@pytest.mark.parametrize('switch,check', [
    ('AYO_PROVIDER_SPEND_AUTHORIZED', 'provider_spending_disabled'),
    ('AYO_MAIL_SEND_AUTHORIZED', 'mail_delivery_disabled'),
])
def test_default_preparation_rejects_enabled_switches_without_changing_them(private_file, capfd, switch, check):
    contents = private_file.read_text().replace(switch + '=0', switch + '=1')
    private_file.write_text(contents, encoding='utf-8')
    assert runtime.main(['--env-file', str(private_file)]) == 2
    captured = capfd.readouterr()
    assert not captured.err
    result = json.loads(captured.out)
    assert {item['id']: item['status'] for item in result['provider_checks']}[check] == 'blocked'
    assert result['live_verified'] is False and result['network_requests_made'] == 0
    assert private_file.read_text() == contents


def test_successful_child_keeps_owner_only_configuration_permissions(private_file, capfd):
    assert runtime.main(['--env-file', str(private_file), '--', sys.executable, '-c', 'pass']) == 0
    assert stat.S_IMODE(private_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(private_file.parent.stat().st_mode) == 0o700
    captured = capfd.readouterr()
    assert not captured.out and not captured.err
