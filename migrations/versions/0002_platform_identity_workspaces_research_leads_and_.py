"""Identity workspaces research leads and founding users

Revision ID: 0002_platform
Revises: 0001_alpha
"""
from alembic import op
import sqlalchemy as sa


revision = '0002_platform'
down_revision = '0001_alpha'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auth_attempts',
    sa.Column('key_hash', sa.String(length=64), nullable=False),
    sa.Column('window_started', sa.Float(), nullable=False),
    sa.Column('count', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('key_hash')
    )
    op.create_table('businesses',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=250), nullable=False),
    sa.Column('country', sa.String(length=2), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('timezone', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.CheckConstraint("(country = 'NG' AND currency = 'NGN') OR (country = 'GH' AND currency = 'GHS')", name='ck_business_currency'),
    sa.CheckConstraint("country IN ('NG', 'GH')", name='ck_business_country'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('cohort_counters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('next_slot', sa.Integer(), nullable=False),
    sa.CheckConstraint('id = 1 AND next_slot >= 1 AND next_slot <= 501', name='ck_cohort_counter'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('business_id', sa.String(length=64), nullable=True),
    sa.Column('actor_user_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('resource_type', sa.String(length=50), nullable=False),
    sa.Column('resource_id', sa.String(length=128), nullable=True),
    sa.Column('details_json', sa.Text(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_events_actor_user_id'), ['actor_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_business_id'), ['business_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_created_at'), ['created_at'], unique=False)

    op.create_table('auth_sessions',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.Float(), nullable=False),
    sa.Column('revoked_at', sa.Float(), nullable=True),
    sa.Column('csrf', sa.String(length=128), nullable=False),
    sa.Column('flash_json', sa.Text(), nullable=True),
    sa.Column('oauth_state_hash', sa.String(length=64), nullable=True),
    sa.Column('oauth_shop', sa.String(length=255), nullable=True),
    sa.Column('oauth_started_at', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('token_hash')
    )
    with op.batch_alter_table('auth_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_auth_sessions_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_auth_sessions_user_id'), ['user_id'], unique=False)

    op.create_table('founding_grants',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('slot', sa.Integer(), nullable=False),
    sa.Column('awarded_at', sa.Float(), nullable=False),
    sa.CheckConstraint('slot >= 1 AND slot <= 500', name='ck_founding_slot'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id'),
    sa.UniqueConstraint('slot')
    )
    op.create_table('identity_tokens',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('purpose', sa.String(length=30), nullable=False),
    sa.Column('expires_at', sa.Float(), nullable=False),
    sa.Column('consumed_at', sa.Float(), nullable=True),
    sa.CheckConstraint("purpose IN ('verify_email', 'reset_password')", name='ck_identity_token_purpose'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('token_hash')
    )
    with op.batch_alter_table('identity_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_identity_tokens_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_identity_tokens_user_id'), ['user_id'], unique=False)

    op.create_table('leads',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('business_id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=250), nullable=False),
    sa.Column('url', sa.String(length=2048), nullable=False),
    sa.Column('country', sa.String(length=2), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('fit_reason', sa.Text(), nullable=False),
    sa.Column('evidence_json', sa.Text(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.Float(), nullable=False),
    sa.CheckConstraint("status IN ('discovered', 'qualified', 'contacted', 'replied', 'converted')", name='ck_lead_status'),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('business_id', 'url', name='uq_lead_business_url')
    )
    with op.batch_alter_table('leads', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_leads_business_id'), ['business_id'], unique=False)

    op.create_table('mail_outbox',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('recipient', sa.String(length=320), nullable=False),
    sa.Column('payload_cipher', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('mail_outbox', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_mail_outbox_user_id'), ['user_id'], unique=False)

    op.create_table('memberships',
    sa.Column('business_id', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.CheckConstraint("role IN ('owner', 'admin', 'editor', 'analyst')", name='ck_membership_role'),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('business_id', 'user_id')
    )
    with op.batch_alter_table('memberships', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_memberships_user_id'), ['user_id'], unique=False)

    op.create_table('research_reports',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('owner_user_id', sa.Integer(), nullable=True),
    sa.Column('business_id', sa.String(length=64), nullable=True),
    sa.Column('title', sa.String(length=250), nullable=False),
    sa.Column('status', sa.String(length=40), nullable=False),
    sa.Column('target_url', sa.String(length=2048), nullable=True),
    sa.Column('country', sa.String(length=2), nullable=False),
    sa.Column('report_json', sa.Text(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('expires_at', sa.Float(), nullable=True),
    sa.Column('anonymous_session_hash', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('research_reports', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_research_reports_business_id'), ['business_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_research_reports_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_research_reports_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_research_reports_owner_user_id'), ['owner_user_id'], unique=False)

    op.create_table('intelligence_runs',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('business_id', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('source_report_id', sa.String(length=64), nullable=True),
    sa.Column('provider', sa.String(length=40), nullable=False),
    sa.Column('model', sa.String(length=100), nullable=False),
    sa.Column('status', sa.String(length=40), nullable=False),
    sa.Column('result_json', sa.Text(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_report_id'], ['research_reports.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_intelligence_runs_business_id', 'intelligence_runs', ['business_id'], unique=False)
    op.create_index('ix_intelligence_runs_user_id', 'intelligence_runs', ['user_id'], unique=False)
    op.create_index('ix_intelligence_runs_created_at', 'intelligence_runs', ['created_at'], unique=False)

    op.create_table('lead_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lead_id', sa.String(length=64), nullable=False),
    sa.Column('business_id', sa.String(length=64), nullable=False),
    sa.Column('actor_user_id', sa.Integer(), nullable=True),
    sa.Column('from_status', sa.String(length=20), nullable=True),
    sa.Column('to_status', sa.String(length=20), nullable=False),
    sa.Column('evidence_json', sa.Text(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lead_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lead_events_business_id'), ['business_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lead_events_lead_id'), ['lead_id'], unique=False)

    op.create_table('report_claims',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('report_id', sa.String(length=64), nullable=False),
    sa.Column('anonymous_session_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.Float(), nullable=False),
    sa.Column('consumed_at', sa.Float(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['report_id'], ['research_reports.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('token_hash'),
    sa.UniqueConstraint('report_id')
    )
    with op.batch_alter_table('snapshots', schema=None) as batch_op:
        batch_op.alter_column('paid_order_value_minor',
               existing_type=sa.INTEGER(),
               type_=sa.BigInteger(),
               existing_nullable=False)

    op.add_column('users', sa.Column('email_verified_at', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('disabled_at', sa.Float(), nullable=True))

    # Preserve existing distinct account ordering; workspace country must still
    # be chosen by each merchant, never guessed from an email or shop name.
    connection = op.get_bind()
    existing = connection.execute(sa.text('SELECT id, joined FROM users ORDER BY joined, id LIMIT 500')).all()
    for slot, row in enumerate(existing, start=1):
        connection.execute(sa.text('INSERT INTO founding_grants (user_id, slot, awarded_at) VALUES (:uid, :slot, :joined)'), {'uid': row.id, 'slot': slot, 'joined': row.joined})
    connection.execute(sa.text('INSERT INTO cohort_counters (id, next_slot) VALUES (1, :next_slot)'), {'next_slot': len(existing) + 1})



def downgrade():
    # PostgreSQL and supported SQLite >=3.35 use native column removal;
    # rebuilding users would break legacy shop foreign keys during downgrade.
    op.drop_column('users', 'disabled_at')
    op.drop_column('users', 'email_verified_at')

    with op.batch_alter_table('snapshots', schema=None) as batch_op:
        batch_op.alter_column('paid_order_value_minor',
               existing_type=sa.BigInteger(),
               type_=sa.INTEGER(),
               existing_nullable=False)

    op.drop_table('report_claims')
    with op.batch_alter_table('lead_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lead_events_lead_id'))
        batch_op.drop_index(batch_op.f('ix_lead_events_business_id'))

    op.drop_table('lead_events')
    op.drop_table('intelligence_runs')
    with op.batch_alter_table('research_reports', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_research_reports_owner_user_id'))
        batch_op.drop_index(batch_op.f('ix_research_reports_expires_at'))
        batch_op.drop_index(batch_op.f('ix_research_reports_created_at'))
        batch_op.drop_index(batch_op.f('ix_research_reports_business_id'))

    op.drop_table('research_reports')
    with op.batch_alter_table('memberships', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_memberships_user_id'))

    op.drop_table('memberships')
    with op.batch_alter_table('mail_outbox', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_mail_outbox_user_id'))

    op.drop_table('mail_outbox')
    with op.batch_alter_table('leads', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_leads_business_id'))

    op.drop_table('leads')
    with op.batch_alter_table('identity_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_identity_tokens_user_id'))
        batch_op.drop_index(batch_op.f('ix_identity_tokens_expires_at'))

    op.drop_table('identity_tokens')
    op.drop_table('founding_grants')
    with op.batch_alter_table('auth_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_auth_sessions_user_id'))
        batch_op.drop_index(batch_op.f('ix_auth_sessions_expires_at'))

    op.drop_table('auth_sessions')
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_events_created_at'))
        batch_op.drop_index(batch_op.f('ix_audit_events_business_id'))
        batch_op.drop_index(batch_op.f('ix_audit_events_actor_user_id'))

    op.drop_table('audit_events')
    op.drop_table('cohort_counters')
    op.drop_table('businesses')
    op.drop_table('auth_attempts')
