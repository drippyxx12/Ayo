"""Migration parity, legacy preservation and DB-enforced tenant constraints."""
import os
import secrets
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from ayo.database import make_engine
from ayo.models import Base

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=['sqlite', 'postgresql'])
def migrated_database(request, tmp_path):
    if request.param == 'postgresql':
        url = os.getenv('AYO_TEST_POSTGRES_URL')
        if not url:
            pytest.skip('Set AYO_TEST_POSTGRES_URL to run real PostgreSQL migrations')
    else:
        url = 'sqlite:///' + str(tmp_path / 'migration.db')
    engine = make_engine(url)
    connection = engine.connect()
    schema = None
    if connection.dialect.name == 'postgresql':
        schema = 'ayo_migration_' + secrets.token_hex(8)
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        connection.exec_driver_sql(f'SET search_path TO "{schema}"')
        connection.commit()
    config = Config(str(ROOT / 'alembic.ini'))
    config.attributes['connection'] = connection
    try:
        yield connection, config
    finally:
        connection.rollback()
        if schema:
            connection.exec_driver_sql('SET search_path TO public')
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
            connection.commit()
        connection.close()
        engine.dispose()


def test_fresh_upgrade_matches_models_and_round_trips(migrated_database):
    connection, config = migrated_database
    command.upgrade(config, 'head')
    tables = set(inspect(connection).get_table_names())
    assert set(Base.metadata.tables) <= tables
    assert connection.execute(text('SELECT next_slot FROM cohort_counters WHERE id=1')).scalar_one() == 1
    connection.commit()
    context = MigrationContext.configure(connection, opts={'compare_type': True})
    assert compare_metadata(context, Base.metadata) == []
    connection.commit()
    command.downgrade(config, 'base')
    assert set(inspect(connection).get_table_names()) <= {'alembic_version'}
    connection.commit()
    command.upgrade(config, 'head')
    assert connection.execute(text('SELECT next_slot FROM cohort_counters')).scalar_one() == 1


def test_alpha_account_and_financial_snapshot_survive_upgrade(migrated_database):
    connection, config = migrated_database
    command.upgrade(config, '0001_alpha')
    connection.execute(text("INSERT INTO users(id,email,password_hash,joined) VALUES (1,'legacy@example.com','unchanged-scrypt-hash',100)"))
    connection.execute(text("INSERT INTO shops(id,user_id,domain,token_cipher,granted_scopes) VALUES(1,1,'legacy.myshopify.com','ciphertext','read_orders')"))
    connection.execute(text("INSERT INTO snapshots(id,user_id,domain,currency,shop_name,product_count,paid_order_count,paid_order_value_minor,paid_order_days,products_json,orders_limited,products_limited,synced_at) VALUES(1,1,'legacy.myshopify.com','NGN','Legacy',0,1,20000,'[]','[]',0,0,100)"))
    connection.commit()
    command.upgrade(config, 'head')
    row = connection.execute(text('SELECT email,password_hash,email_verified_at FROM users WHERE id=1')).one()
    assert row.email == 'legacy@example.com'
    assert row.password_hash == 'unchanged-scrypt-hash'
    assert row.email_verified_at is None
    assert connection.execute(text('SELECT paid_order_value_minor FROM snapshots')).scalar_one() == 20000
    assert connection.execute(text('SELECT slot FROM founding_grants WHERE user_id=1')).scalar_one() == 1
    assert connection.execute(text('SELECT next_slot FROM cohort_counters')).scalar_one() == 2
    assert connection.execute(text('SELECT COUNT(*) FROM businesses')).scalar_one() == 0
    connection.commit()
    command.downgrade(config, '0001_alpha')
    assert connection.execute(text('SELECT email FROM users')).scalar_one() == 'legacy@example.com'
    assert connection.execute(text('SELECT paid_order_value_minor FROM snapshots')).scalar_one() == 20000


def test_database_enforces_founding_slot_country_and_membership_constraints(migrated_database):
    connection, config = migrated_database
    command.upgrade(config, 'head')
    connection.execute(text("INSERT INTO users(id,email,password_hash,joined) VALUES(1,'one@example.com','hash',100),(2,'two@example.com','hash',101)"))
    connection.execute(text("INSERT INTO businesses(id,name,country,currency,timezone,created_at) VALUES('b1','Business','NG','NGN','Africa/Lagos',100)"))
    connection.execute(text("INSERT INTO memberships(business_id,user_id,role) VALUES('b1',1,'owner')"))
    connection.execute(text('INSERT INTO founding_grants(user_id,slot,awarded_at) VALUES(1,1,100)'))
    connection.commit()
    statements = [
        'INSERT INTO founding_grants(user_id,slot,awarded_at) VALUES(2,1,101)',
        'INSERT INTO founding_grants(user_id,slot,awarded_at) VALUES(2,501,101)',
        "INSERT INTO memberships(business_id,user_id,role) VALUES('b1',1,'owner')",
        "INSERT INTO memberships(business_id,user_id,role) VALUES('b1',2,'superuser')",
        "INSERT INTO businesses(id,name,country,currency,timezone,created_at) VALUES('bad','Business','GH','NGN','Africa/Accra',100)",
    ]
    for statement in statements:
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(text(statement))


def test_postgresql_supports_large_money_values(migrated_database):
    connection, config = migrated_database
    command.upgrade(config, 'head')
    connection.execute(text("INSERT INTO users(id,email,password_hash,joined) VALUES(1,'money@example.com','hash',100)"))
    connection.execute(text("INSERT INTO snapshots(id,user_id,domain,currency,shop_name,product_count,paid_order_count,paid_order_value_minor,paid_order_days,products_json,orders_limited,products_limited,synced_at) VALUES(1,1,'money.myshopify.com','NGN','Money',0,1,999999999999,'[]','[]',0,0,100)"))
    assert connection.execute(text('SELECT paid_order_value_minor FROM snapshots')).scalar_one() == 999999999999
