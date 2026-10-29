"""Pure configuration shape checks, never live credential/model validation."""
import re
import hashlib
import json

MODEL_INPUT_MAX_BYTES = 32768


def model_budget_fingerprint(provider, model, max_input_bytes, max_output_tokens, thinking_level=None):
    """Bind a price review to the exact bounded adapter configuration."""
    return hashlib.sha256(json.dumps({'provider': provider, 'model': model,
        'max_input_bytes': max_input_bytes, 'max_output_tokens': max_output_tokens,
        'thinking_level': thinking_level or 'provider_default', 'contract': 'ayo-text-json-v2'},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def valid_api_key(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[!-~]{8,512}', value)) and not any(
        marker in value.upper() for marker in ('REPLACE_', 'CHANGEME', 'YOUR_API_KEY', '${'))


def valid_model_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{1,99}', value))
