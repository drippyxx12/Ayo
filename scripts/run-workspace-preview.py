#!/usr/bin/env python3
"""Run a loopback PostgreSQL workspace preview with its supervised research worker.

Never provisions hosting, migrates a database, seeds records, enables providers,
prints secrets or replaces the separate restricted Vercel preview.
"""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit

from alembic.config import Config
from alembic.script import ScriptDirectory
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def preflight(environ, port, *, check_database=True):
    """Fail before either child starts; all errors are fixed non-secret text."""
    if not 1024 <= port <= 65535:
        raise ValueError('Choose a loopback port between 1024 and 65535.')
    if environ.get('ENVIRONMENT') != 'development' or environ.get('AYO_PREVIEW_MODE', '0') != '0':
        raise ValueError('Use ENVIRONMENT=development and AYO_PREVIEW_MODE=0 for this separate workspace preview.')
    if any(environ.get(name) != '0' for name in ('AYO_PROVIDER_SPEND_AUTHORIZED', 'AYO_MAIL_SEND_AUTHORIZED')):
        raise ValueError('Paid provider calls and mail delivery must both be explicitly disabled.')
    if environ.get('AYO_RESEARCH_SOURCE', 'direct_public_web') != 'direct_public_web':
        raise ValueError('This local preview requires the direct_public_web source; other provider modes are separate.')
    try:
        origin = urlsplit(environ.get('APP_ORIGIN', ''))
        if (origin.scheme != 'http' or origin.hostname not in {'127.0.0.1', 'localhost'}
                or origin.port != port or origin.username or origin.password
                or origin.path not in {'', '/'} or origin.query or origin.fragment):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('APP_ORIGIN must match this preview\'s HTTP loopback hostname and port.') from None
    if len(environ.get('SESSION_SECRET', '')) < 32:
        raise ValueError('Configure a durable session signing secret outside Git before starting.')
    try:
        Fernet(environ.get('TOKEN_ENCRYPTION_KEY', '').encode())
    except (ValueError, TypeError):
        raise ValueError('Configure a durable Fernet encryption key outside Git before starting.') from None
    try:
        url = make_url(environ.get('DATABASE_URL', ''))
        if url.get_backend_name() != 'postgresql' or url.host not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError()
    except (ValueError, TypeError, ArgumentError):
        raise ValueError('Use a dedicated loopback PostgreSQL database, with its URL configured outside Git.') from None
    if check_database:
        from ayo.database import make_engine
        engine = None
        try:
            engine = make_engine(url.render_as_string(hide_password=False))
            with engine.connect() as connection:
                actual = set(connection.execute(text('SELECT version_num FROM alembic_version')).scalars())
            expected = set(ScriptDirectory.from_config(Config(str(ROOT / 'alembic.ini'))).get_heads())
            if actual != expected:
                raise ValueError()
        except Exception:
            raise ValueError('PostgreSQL is unreachable or its schema is not at the repository migration head. No migration was attempted.') from None
        finally:
            if engine is not None:
                engine.dispose()


def run(port):
    children = []
    stop = False

    def request_stop(_signum, _frame):
        nonlocal stop
        stop = True

    prior = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        # Both processes inherit the exact same DB/signing/encryption/policy settings.
        for command in ([sys.executable, '-m', 'uvicorn', 'ayo.app:app', '--host', '127.0.0.1',
                         '--port', str(port), '--no-access-log'],
                        [sys.executable, '-m', 'ayo.worker']):
            children.append(subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                              start_new_session=True))
        print(f'Workspace web and research worker started at http://127.0.0.1:{port}/. '
              'External AI remains subject to the existing data policy and budget. No account data was seeded.', flush=True)
        while not stop:
            if any(child.poll() is not None for child in children):
                print('A preview process stopped; stopping its companion to avoid a silently disconnected worker.', flush=True)
                return 1
            time.sleep(.25)
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        deadline = time.monotonic() + 8
        for child in children:
            try:
                child.wait(timeout=max(.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        for sig, handler in prior.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--check', action='store_true', help='Check configuration and DB migration head; start nothing.')
    args = parser.parse_args()
    try:
        preflight(os.environ, args.port)
    except ValueError as exc:
        parser.exit(2, 'Workspace preview unavailable: ' + str(exc) + '\n')
    if args.check:
        print('Workspace configuration and PostgreSQL migration head verified. No worker, source, model or mail request started.')
        return 0
    return run(args.port)


if __name__ == '__main__':
    raise SystemExit(main())
