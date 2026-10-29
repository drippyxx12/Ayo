"""Start test collection with synthetic isolated configuration, never a workspace DB."""
import os
import secrets
import tempfile

from cryptography.fernet import Fernet

_bootstrap = tempfile.TemporaryDirectory(prefix='ayo-offline-bootstrap-')
os.environ.update(
    ENVIRONMENT='test', DATABASE_URL='sqlite:///' + _bootstrap.name + '/bootstrap.db',
    SESSION_SECRET=secrets.token_urlsafe(48), TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(),
    SHOPIFY_CLIENT_ID='offline-test-id', SHOPIFY_CLIENT_SECRET='test-secret',
    APP_ORIGIN='http://testserver', AYO_PROVIDER_SPEND_AUTHORIZED='0', AYO_MAIL_SEND_AUTHORIZED='0',
    AYO_ON_DEMAND_RESEARCH='0', AYO_ON_DEMAND_GEMINI_AUTHORIZED='0',
)
