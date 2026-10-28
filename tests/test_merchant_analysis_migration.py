"""Preserve populated parent/child evidence; never discard a zero-cost ledger to downgrade."""
from alembic import command
import pytest
from sqlalchemy import text
from test_migrations import migrated_database  # noqa: F401


def test_populated_conversations_and_budget_receipts_survive_upgrade(migrated_database):
    connection, config = migrated_database
    command.upgrade(config, '0007_assistant')
    statements = [
        "INSERT INTO users(id,email,password_hash,joined) VALUES(1,'migration@example.invalid','fixture',1)",
        "INSERT INTO businesses(id,name,country,currency,timezone,created_at) VALUES('business','Fixture','NG','NGN','Africa/Lagos',1)",
        "INSERT INTO assistant_conversations(id,business_id,user_id,creation_key,title,created_at,updated_at) VALUES('conversation','business',1,'creation','Fixture',1,1)",
        "INSERT INTO assistant_messages(id,conversation_id,business_id,user_id,request_key,role,content,status,plan_json,result_json,created_at) VALUES('message','conversation','business',1,'request','assistant','Fixture','completed','{}','{}',1)",
        "INSERT INTO assistant_tool_runs(id,message_id,business_id,user_id,tool_name,version,status,result_json,created_at) VALUES('tool','message','business',1,'research.saved',1,'empty','{}',1)",
        "INSERT INTO provider_budget_accounts(key_hash,kind,window_day,limit_microusd,call_limit,reserved_microusd,calls,updated_at) VALUES('account','request',0,1,1,1,1,1)",
        "INSERT INTO provider_usage_reservations(id,dispatch_hash,scope_hash,request_hash,provider,operation,policy_version,policy_hash,reserved_microusd,outcome,usage_json,created_at) VALUES('receipt','dispatch','scope','request','gemini','analyze','fixture','policy',1,'uncertain','{}',1)",
    ]
    for statement in statements:connection.execute(text(statement))
    connection.commit()
    command.upgrade(config, 'head')
    for table in ('assistant_conversations','assistant_messages','assistant_tool_runs','provider_budget_accounts','provider_usage_reservations'):
        assert connection.scalar(text('SELECT count(*) FROM '+table)) == 1
    assert connection.scalar(text("SELECT outcome FROM provider_usage_reservations WHERE id='receipt'")) == 'uncertain'
    connection.commit()
    command.downgrade(config, '0007_assistant')
    assert connection.scalar(text('SELECT count(*) FROM assistant_messages')) == 1
    assert connection.scalar(text('SELECT count(*) FROM assistant_tool_runs')) == 1


def test_zero_cost_evidence_prevents_destructive_downgrade(migrated_database):
    connection, config = migrated_database
    command.upgrade(config, 'head')
    connection.execute(text("INSERT INTO provider_budget_accounts(key_hash,kind,window_day,limit_microusd,call_limit,reserved_microusd,calls,updated_at) VALUES('free-account','request',0,0,1,0,1,1)"))
    connection.commit()
    with pytest.raises(RuntimeError, match='zero-cost budget evidence'):
        command.downgrade(config, '0007_assistant')
    assert connection.scalar(text("SELECT calls FROM provider_budget_accounts WHERE key_hash='free-account'")) == 1
