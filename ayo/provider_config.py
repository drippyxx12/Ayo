"""Pure configuration shape checks, never live credential/model validation."""
import re


def valid_api_key(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[!-~]{8,512}', value)) and not any(
        marker in value.upper() for marker in ('REPLACE_', 'CHANGEME', 'YOUR_API_KEY', '${'))


def valid_model_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{1,99}', value))
