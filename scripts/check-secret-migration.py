#!/usr/bin/env python3
"""Offline inherited-configuration check; never provisions or validates a key.

No private file is read unless --compare-local is explicitly requested and both
inherited credentials/switches pass preparation checks. Output is fixed metadata
only. Process presence/equality never certifies a managed binding or recreation.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ayo.provider_config import valid_api_key
from ayo.runtime_configuration import AUTHORIZATION_SWITCHES, PROVIDER_CREDENTIALS


def check_migration(*, compare_local=False, local_file=None, environ=None, loader=None):
    environment = os.environ if environ is None else environ
    source = environment.get('AYO_RUNTIME_INPUT_SOURCE', 'inherited_environment')
    if not isinstance(source, str) or source not in ('local_file', 'inherited_environment'):
        source = 'unknown'
    credentials = {name: valid_api_key(environment.get(name, '')) for name in PROVIDER_CREDENTIALS}
    disabled = all(environment.get(name) == '0' for name in AUTHORIZATION_SWITCHES)
    ready = all(credentials.values()) and disabled and source == 'inherited_environment'
    comparison = 'not_requested'
    if compare_local:
        comparison = 'not_attempted'
        if ready:
            try:
                if loader is None:
                    path = ROOT / 'scripts' / 'with-private-runtime.py'
                    spec = importlib.util.spec_from_file_location('ayo_migration_local_loader', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    loader = module.load_private_configuration
                    local_file = local_file or module.DEFAULT_ENV_FILE
                local = loader(local_file)
                # Compare internally; never emit a value, hash or partial match.
                # Evaluate both comparisons before combining their results, so
                # a mismatch never skips the other credential. Invalid local
                # shapes use an empty ASCII value and cannot match a ready key.
                matches = []
                for name in PROVIDER_CREDENTIALS:
                    value = local.get(name)
                    matches.append(secrets.compare_digest(environment[name], value if valid_api_key(value) else ''))
                comparison = 'matched' if all(matches) else 'mismatch'
            except Exception:
                comparison = 'unavailable'
    return {
        'schema_version': 1,
        'mode': 'offline_inherited_configuration_only',
        'process_source': source,
        'credential_shape_checks': credentials,
        'provider_and_mail_explicitly_disabled': disabled,
        'runtime_configuration_ready': ready,
        'local_comparison': comparison,
        'cloud_binding_provisioning_verified': False,
        'environment_recreation_verified': False,
        'provider_key_rotation_verified': False,
        'provider_live_api_validated': False,
        'network_requests_made': 0,
        'remaining_proof': [
            'Current control-plane observations must show both persistent bindings ready.',
            'A real lifecycle event and fresh-instance observations are required to prove recreation survival.',
            'New processes must load the selected version without a local fallback; old processes require restart.',
            'Configuration equality is not provider validity, old-key revocation, billing proof or call approval.',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare-local', action='store_true')
    parser.add_argument('--local-file', type=Path)
    args = parser.parse_args(argv)
    report = check_migration(compare_local=args.compare_local, local_file=args.local_file)
    print(json.dumps(report, indent=2))
    passed = report['runtime_configuration_ready'] and (not args.compare_local or report['local_comparison'] == 'matched')
    return 0 if passed else 2


if __name__ == '__main__':
    raise SystemExit(main())
