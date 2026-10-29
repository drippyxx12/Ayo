"""Preview startup rejects unsafe/mismatched configuration before any process."""
import importlib.util
from pathlib import Path
import secrets

from cryptography.fernet import Fernet
import pytest

spec = importlib.util.spec_from_file_location('workspace_preview',
    Path(__file__).resolve().parents[1] / 'scripts/run-workspace-preview.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def config():
    return dict(ENVIRONMENT='development', AYO_PREVIEW_MODE='0', APP_ORIGIN='http://127.0.0.1:8000',
        SESSION_SECRET=secrets.token_urlsafe(48), TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(),
        DATABASE_URL='postgresql+psycopg://preview@127.0.0.1:55432/preview',
        AYO_PROVIDER_SPEND_AUTHORIZED='0', AYO_MAIL_SEND_AUTHORIZED='0')


@pytest.mark.parametrize('changes', [
    {'ENVIRONMENT': 'production'}, {'AYO_PREVIEW_MODE': '1'},
    {'APP_ORIGIN': 'https://public.example.org:8000'}, {'APP_ORIGIN': 'http://127.0.0.1:8001'},
    {'APP_ORIGIN': 'http://127.0.0.1:8000/?secret=private'}, {'AYO_MAIL_SEND_AUTHORIZED': '1'},
    {'AYO_PROVIDER_SPEND_AUTHORIZED': '1'}, {'AYO_PROVIDER_SPEND_AUTHORIZED': ''},
    {'SESSION_SECRET': ''}, {'TOKEN_ENCRYPTION_KEY': 'private-invalid-secret'},
    {'DATABASE_URL': 'sqlite:///:memory:'},
    {'DATABASE_URL': 'postgresql://preview:private-db-password@remote.example.org/preview'},
    {'DATABASE_URL': 'private-invalid-database-url'}, {'AYO_RESEARCH_SOURCE': 'firecrawl'},
])
def test_runner_rejects_unsafe_configuration_without_secret_echo(changes):
    with pytest.raises(ValueError) as error:
        runner.preflight({**config(), **changes}, 8000, check_database=False)
    assert 'private-db-password' not in str(error.value)
    assert 'private-invalid-secret' not in str(error.value)
    assert 'private-invalid-database-url' not in str(error.value)


def test_matching_local_preview_config_is_accepted_without_disabling_model_guards():
    values = config()
    assert runner.preflight(values, 8000, check_database=False) is None
    assert values['AYO_PROVIDER_SPEND_AUTHORIZED'] == values['AYO_MAIL_SEND_AUTHORIZED'] == '0'
