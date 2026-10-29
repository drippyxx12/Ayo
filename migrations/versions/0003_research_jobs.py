"""Durable bounded research jobs.

Revision ID: 0003_jobs
Revises: 0002_platform
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_jobs'
down_revision = '0002_platform'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('research_jobs',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('anonymous_session_hash', sa.String(64), nullable=False),
        sa.Column('payload_cipher', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('lease_until', sa.Float()),
        sa.Column('report_id', sa.String(64), sa.ForeignKey('research_reports.id', ondelete='SET NULL')),
        sa.Column('claim_cipher', sa.Text()), sa.Column('error_code', sa.String(80)),
        sa.Column('created_at', sa.Float(), nullable=False), sa.Column('finished_at', sa.Float()),
        sa.CheckConstraint("status IN ('queued','running','succeeded','failed')", name='ck_research_job_status'))
    op.create_index('ix_research_jobs_anonymous_session_hash', 'research_jobs', ['anonymous_session_hash'])
    op.create_index('ix_research_jobs_status', 'research_jobs', ['status'])


def downgrade():
    op.drop_table('research_jobs')
