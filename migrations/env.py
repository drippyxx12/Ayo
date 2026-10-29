"""Explicit Alembic migration entrypoint, supporting SQLite and PostgreSQL."""
import os

from alembic import context

from ayo.database import configured_url, make_engine, normalize_url
from ayo.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_offline():
    url = configured_url() if os.getenv('DATABASE_URL') else normalize_url(config.get_main_option('sqlalchemy.url'))
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    supplied = config.attributes.get('connection')
    if supplied is not None:
        context.configure(connection=supplied, target_metadata=target_metadata, compare_type=True, render_as_batch=supplied.dialect.name == 'sqlite')
        with context.begin_transaction():
            context.run_migrations()
        return
    url = configured_url() if os.getenv('DATABASE_URL') else config.get_main_option('sqlalchemy.url')
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True, render_as_batch=connection.dialect.name == 'sqlite')
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
