"""Populated upgrade preservation and safe pre-migration application behavior."""
from alembic import command
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from ayo.site_control import schema_ready, SiteControlService
from ayo.identity import IdentityError
from ayo import app as mod
from test_migrations import migrated_database  # noqa: F401


def test_prior_reports_budget_and_account_survive_additive_migration(migrated_database):
    connection, config = migrated_database
    command.upgrade(config, '0008_merchant_analysis')
    connection.execute(text("INSERT INTO users(id,email,password_hash,joined) VALUES(1,'fixture@example.invalid','fixture',1)"))
    connection.execute(text("INSERT INTO businesses(id,name,country,currency,timezone,created_at) VALUES('business','Fixture','NG','NGN','Africa/Lagos',1)"))
    connection.execute(text("INSERT INTO memberships(business_id,user_id,role) VALUES('business',1,'owner')"))
    connection.execute(text("INSERT INTO research_reports(id,business_id,title,status,country,report_json,created_at) VALUES('report','business','Immutable','PARTIAL','NG',:report,1)"), {'report': '{"website_ownership_verified":false}'})
    connection.execute(text("INSERT INTO provider_budget_accounts(key_hash,kind,window_day,limit_microusd,call_limit,reserved_microusd,calls,updated_at) VALUES('free-account','request',0,0,1,0,1,1)"))
    connection.commit()
    with Session(bind=connection) as sess:
        assert schema_ready(sess) is False
        with pytest.raises(IdentityError) as exc:
            SiteControlService(sess, mod.fernet).list(1, 'business')
        assert exc.value.code == 'site_control_not_ready'
    command.upgrade(config, 'head')
    assert 'site_control_claims' in inspect(connection).get_table_names()
    assert connection.scalar(text("SELECT report_json FROM research_reports WHERE id='report'")) == '{"website_ownership_verified":false}'
    assert connection.scalar(text("SELECT calls FROM provider_budget_accounts WHERE key_hash='free-account'")) == 1
    assert connection.scalar(text('SELECT count(*) FROM memberships')) == 1
    connection.execute(text("INSERT INTO site_control_claims(id,business_id,created_by,host,method,status,token_hash,created_at,expires_at,attempts) VALUES('claim','business',1,'example.org','https_file','revoked','fixturehash',1,2,0)"))
    connection.commit()
    with pytest.raises(RuntimeError, match='history exists'):
        command.downgrade(config, '0008_merchant_analysis')
    assert connection.scalar(text('SELECT count(*) FROM site_control_claims')) == 1
    assert connection.scalar(text("SELECT report_json FROM research_reports WHERE id='report'")) == '{"website_ownership_verified":false}'
