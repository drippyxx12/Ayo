"""Database configuration without import-time schema creation."""
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def normalize_url(url):
    if url.startswith('postgres://'):
        url = 'postgresql+psycopg://' + url[len('postgres://'):]
    elif url.startswith('postgresql://'):
        url = 'postgresql+psycopg://' + url[len('postgresql://'):]
    if os.getenv('ENVIRONMENT') == 'production' and not url.startswith('postgresql+'):
        raise RuntimeError('Production requires PostgreSQL and explicit migrations.')
    return url


def configured_url():
    return normalize_url(os.getenv('DATABASE_URL', 'sqlite:///./ayo.db'))


def make_engine(url=None):
    url = normalize_url(url) if url else configured_url()
    options = {'pool_pre_ping': True}
    if url.startswith('postgresql+'):
        options.update(connect_args={'connect_timeout': 5}, pool_timeout=5)
    if url.startswith('sqlite:'):
        options['connect_args'] = {'check_same_thread': False, 'timeout': 30}
        if url in {'sqlite://', 'sqlite:///:memory:'}:
            options['poolclass'] = StaticPool
    result = create_engine(url, **options)
    if url.startswith('sqlite:'):
        @event.listens_for(result, 'connect')
        def configure_sqlite(connection, _record):
            cursor = connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()
    return result


def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
