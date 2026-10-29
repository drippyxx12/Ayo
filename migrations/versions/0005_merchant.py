"""Merchant-supplied profile and tenant-scoped internal tasks.

Revision ID: 0005_merchant
Revises: 0004_budgets
"""
from alembic import op
import sqlalchemy as sa

revision = '0005_merchant'
down_revision = '0004_budgets'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('business_profiles',
        sa.Column('business_id', sa.String(64), sa.ForeignKey('businesses.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('offer', sa.Text(), nullable=False),
        sa.Column('products', sa.Text(), nullable=False),
        sa.Column('audience', sa.Text(), nullable=False),
        sa.Column('location', sa.String(250), nullable=False),
        sa.Column('goals', sa.Text(), nullable=False),
        sa.Column('source_classification', sa.String(40), nullable=False),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.CheckConstraint("source_classification = 'OWNER_PROVIDED_UNVERIFIED'", name='ck_profile_source'),
        sa.CheckConstraint('version >= 1', name='ck_profile_version'))
    op.create_table('tasks',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('business_id', sa.String(64), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('due_date', sa.Date()),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('source_report_id', sa.String(64), sa.ForeignKey('research_reports.id', ondelete='SET NULL')),
        sa.Column('source_lead_id', sa.String(64), sa.ForeignKey('leads.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('open','in_progress','done','cancelled')", name='ck_task_status'),
        sa.CheckConstraint('version >= 1', name='ck_task_version'),
        sa.CheckConstraint('length(title) >= 1 AND length(title) <= 200', name='ck_task_title'))
    for column in ('business_id', 'source_report_id', 'source_lead_id'):
        op.create_index('ix_tasks_' + column, 'tasks', [column])


def downgrade():
    op.drop_table('tasks')
    op.drop_table('business_profiles')
