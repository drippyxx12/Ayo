"""Persistent conservative provider budget reservations.

Revision ID: 0004_budgets
Revises: 0003_jobs
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_budgets'
down_revision = '0003_jobs'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('provider_budget_lock',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.CheckConstraint('id = 1', name='ck_provider_budget_lock'))
    op.bulk_insert(sa.table('provider_budget_lock', sa.column('id', sa.Integer())), [{'id': 1}])
    op.create_table('provider_budget_accounts',
        sa.Column('key_hash', sa.String(64), primary_key=True),
        sa.Column('kind', sa.String(30), nullable=False),
        sa.Column('window_day', sa.Integer(), nullable=False),
        sa.Column('limit_microusd', sa.BigInteger(), nullable=False),
        sa.Column('call_limit', sa.Integer(), nullable=False),
        sa.Column('reserved_microusd', sa.BigInteger(), nullable=False),
        sa.Column('calls', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
        sa.CheckConstraint('reserved_microusd >= 0 AND calls >= 0', name='ck_budget_account_nonnegative'),
        sa.CheckConstraint('limit_microusd > 0 AND call_limit > 0', name='ck_budget_account_limits'),
        sa.CheckConstraint('reserved_microusd <= limit_microusd AND calls <= call_limit', name='ck_budget_account_capacity'))
    op.create_table('provider_usage_reservations',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('dispatch_hash', sa.String(64), nullable=False),
        sa.Column('scope_hash', sa.String(64), nullable=False),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('provider', sa.String(30), nullable=False),
        sa.Column('operation', sa.String(30), nullable=False),
        sa.Column('policy_version', sa.String(100), nullable=False),
        sa.Column('policy_hash', sa.String(64), nullable=False),
        sa.Column('reserved_microusd', sa.BigInteger(), nullable=False),
        sa.Column('outcome', sa.String(20), nullable=False),
        sa.Column('usage_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('settled_at', sa.Float()),
        sa.UniqueConstraint('dispatch_hash', name='uq_provider_usage_dispatch'),
        sa.CheckConstraint('reserved_microusd > 0', name='ck_provider_usage_reservation'),
        sa.CheckConstraint("outcome IN ('reserved','succeeded','failed','uncertain')", name='ck_provider_usage_outcome'))
    for column in ('scope_hash', 'request_hash', 'created_at'):
        op.create_index('ix_provider_usage_reservations_' + column, 'provider_usage_reservations', [column])


def downgrade():
    op.drop_table('provider_usage_reservations')
    op.drop_table('provider_budget_accounts')
    op.drop_table('provider_budget_lock')
