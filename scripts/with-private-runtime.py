#!/usr/bin/env python3
"""Run Ayo with a private local configuration; never print loaded values.

This is workspace configuration, not a managed secret-vault binding. The default
file lives outside the Git checkout. No setting is inferred as spend approval.
With no command this runs only the existing offline provider preparation check.
"""
from __future__ import annotations

import argparse
import io
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

from dotenv.parser import parse_stream

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT.parent / '.ayo-private' / 'runtime.env'


def allowed_variable(key):
    return (key in {'DATABASE_URL', 'SESSION_SECRET', 'TOKEN_ENCRYPTION_KEY', 'APP_ORIGIN',
                    'ENVIRONMENT', 'RESEND_API_KEY', 'MAIL_FROM'} or
            key.startswith(('AYO_', 'GEMINI_', 'FIRECRAWL_', 'ANTHROPIC_', 'SHOPIFY_')))


class PrivateRuntimeError(ValueError):
    pass


def load_private_configuration(path):
    path = Path(os.path.abspath(path))
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory = os.open(path.anchor, directory_flags)
    try:
        # Descriptor-relative traversal refuses symlinks in every ancestor and
        # anchors the final file lookup if a directory is renamed concurrently.
        for part in path.parts[1:-1]:
            next_directory = os.open(part, directory_flags, dir_fd=directory)
            os.close(directory)
            directory = next_directory
        parent = os.fstat(directory)
        if parent.st_uid != os.geteuid() or parent.st_mode & 0o077:
            raise PrivateRuntimeError('Private configuration requires an owner-only directory.')
        if not stat.S_ISREG(os.stat(path.name, dir_fd=directory, follow_symlinks=False).st_mode):
            raise PrivateRuntimeError('Private configuration requires a regular file.')
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(descriptor, 'r', encoding='utf-8') as stream:
        metadata = os.fstat(stream.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid()
                or metadata.st_mode & 0o077 or metadata.st_size > 65536):
            raise PrivateRuntimeError('Private configuration requires a bounded owner-only regular file.')
        data = stream.read(65537)
    values = {}
    for binding in parse_stream(io.StringIO(data)):
        if binding.error:
            raise PrivateRuntimeError('The private configuration format is invalid.')
        if binding.key is None:
            continue
        if (not re.fullmatch(r'[A-Z][A-Z0-9_]*', binding.key) or not allowed_variable(binding.key)
                or binding.value is None or '\x00' in binding.value or binding.key in values):
            raise PrivateRuntimeError('The private configuration format is invalid.')
        values[binding.key] = binding.value
    if not values:
        raise PrivateRuntimeError('The private configuration format is invalid.')
    return values


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        values = load_private_configuration(args.env_file)
    except (OSError, ValueError, UnicodeError):
        print('Private runtime configuration is missing, invalid or not owner-only. No values were displayed.', file=sys.stderr)
        return 2
    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        command = [sys.executable, str(ROOT / 'scripts' / 'check-provider-readiness.py'),
                   '--mode', 'prepare', '--scope', 'provider']
    environment = os.environ.copy()
    environment.update(values)
    try:
        return subprocess.run(command, env=environment, cwd=ROOT, check=False).returncode
    except (OSError, ValueError):
        print('The requested private runtime command could not start. No values were displayed.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
