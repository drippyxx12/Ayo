"""Exact-host, expiring HTTPS-file control proofs. No report/schema rewrite."""
from alembic import op
import sqlalchemy as sa

revision = '0009_site_control'
down_revision = '0008_merchant_analysis'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('site_control_claims',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('business_id', sa.String(64), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('host', sa.String(253), nullable=False),
        sa.Column('method', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('token_cipher', sa.Text()),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('expires_at', sa.Float(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('checked_at', sa.Float()),
        sa.Column('lease_hash', sa.String(64)),
        sa.Column('lease_until', sa.Float()),
        sa.Column('verified_at', sa.Float()),
        sa.Column('verified_until', sa.Float()),
        sa.Column('proof_body_sha256', sa.String(64)),
        sa.Column('error_code', sa.String(60)),
        sa.CheckConstraint("status IN ('pending','checking','failed','verified','expired','revoked')", name='ck_site_control_status'),
        sa.CheckConstraint('attempts >= 0 AND attempts <= 5', name='ck_site_control_attempts'),
        sa.CheckConstraint("method = 'https_file'", name='ck_site_control_method'),
        sa.CheckConstraint('expires_at > created_at', name='ck_site_control_expiry'),
        sa.CheckConstraint("status != 'verified' OR (verified_at IS NOT NULL AND verified_until > verified_at AND proof_body_sha256 IS NOT NULL AND token_cipher IS NULL)", name='ck_site_control_proof'))
    op.create_index('ix_site_control_business_host', 'site_control_claims', ['business_id', 'host', 'created_at'])
    op.create_index('ix_site_control_actor_created', 'site_control_claims', ['created_by', 'created_at'])


def downgrade():
    # Proof history belongs to the merchant. Never silently drop populated data.
    if op.get_bind().execute(sa.text('SELECT COUNT(*) FROM site_control_claims')).scalar_one():
        raise RuntimeError('Site-control history exists; export and explicitly remove it before downgrade.')
    op.drop_table('site_control_claims')
