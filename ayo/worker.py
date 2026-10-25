"""Operator-run bounded job worker; never enables provider spending itself."""
import argparse
import asyncio
import os
import time

from cryptography.fernet import Fernet

from ayo.database import make_engine, session_factory
from ayo.jobs import process_one
from ayo.mailer import deliver_one
from ayo.retention import cleanup_expired


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--mail', action='store_true', help='Deliver transactional account mail; requires separate authorization.')
    mode.add_argument('--cleanup', action='store_true', help='Delete expired anonymous and security artifacts.')
    args = parser.parse_args()
    key = os.getenv('TOKEN_ENCRYPTION_KEY')
    if not key or 'REPLACE_' in key:
        raise SystemExit('A durable TOKEN_ENCRYPTION_KEY is required for encrypted jobs and mail.')
    fernet = Fernet(key.encode())
    factory = session_factory(make_engine())
    while True:
        if args.cleanup:
            with factory() as session:
                worked = cleanup_expired(session)
                session.commit()
        elif args.mail:
            with factory() as session:
                worked = deliver_one(session, fernet)
                session.commit()
        else:
            worked = asyncio.run(process_one(factory, fernet))
        if args.once:
            break
        if not worked:
            time.sleep(2)


if __name__ == '__main__':
    main()
