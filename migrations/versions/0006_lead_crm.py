"""Private prospect lists, notes and source-bound review drafts.

Revision ID: 0006_lead_crm
Revises: 0005_merchant
"""
from alembic import op
import sqlalchemy as sa

revision = '0006_lead_crm'
down_revision = '0005_merchant'
branch_labels = None
depends_on = None


def upgrade():
    # A unique index avoids rebuilding SQLite's populated parent table, which
    # could otherwise cascade-delete events and detach existing task sources.
    op.create_index('uq_lead_business_id', 'leads', ['business_id', 'id'], unique=True)
    op.create_table('lead_lists',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('business_id', sa.String(64), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('provenance', sa.String(40), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
        sa.UniqueConstraint('business_id', 'id', name='uq_lead_list_business_id'))
    op.create_index('ix_lead_lists_business_id', 'lead_lists', ['business_id'])
    op.create_table('lead_list_items',
        sa.Column('business_id', sa.String(64), sa.ForeignKey('businesses.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('list_id', sa.String(64), primary_key=True),
        sa.Column('lead_id', sa.String(64), primary_key=True),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('provenance', sa.String(40), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['business_id', 'list_id'], ['lead_lists.business_id', 'lead_lists.id'],
                                ondelete='CASCADE', name='fk_lead_list_item_list'),
        sa.ForeignKeyConstraint(['business_id', 'lead_id'], ['leads.business_id', 'leads.id'],
                                ondelete='CASCADE', name='fk_lead_list_item_lead'))
    op.create_table('lead_notes',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('business_id', sa.String(64), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.String(64), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('provenance', sa.String(40), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['business_id', 'lead_id'], ['leads.business_id', 'leads.id'],
                                ondelete='CASCADE', name='fk_lead_note_lead'))
    for column in ('business_id', 'lead_id'):
        op.create_index('ix_lead_notes_' + column, 'lead_notes', [column])
    op.create_table('outreach_drafts',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('business_id', sa.String(64), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.String(64), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('offer', sa.Text(), nullable=False),
        sa.Column('source_id', sa.String(160), nullable=False),
        sa.Column('source_url', sa.String(2048), nullable=False),
        sa.Column('source_excerpt', sa.Text(), nullable=False),
        sa.Column('subject', sa.String(200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('provenance', sa.String(40), nullable=False),
        sa.Column('template_version', sa.String(40), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
        sa.UniqueConstraint('business_id', 'lead_id', name='uq_outreach_draft_business_lead'),
        sa.CheckConstraint('version >= 1', name='ck_outreach_draft_version'),
        sa.CheckConstraint("status = 'draft'", name='ck_outreach_draft_status'),
        sa.ForeignKeyConstraint(['business_id', 'lead_id'], ['leads.business_id', 'leads.id'],
                                ondelete='CASCADE', name='fk_outreach_draft_lead'))
    for column in ('business_id', 'lead_id'):
        op.create_index('ix_outreach_drafts_' + column, 'outreach_drafts', [column])


def downgrade():
    op.drop_table('outreach_drafts')
    op.drop_table('lead_notes')
    op.drop_table('lead_list_items')
    op.drop_table('lead_lists')
    op.drop_index('uq_lead_business_id', table_name='leads')
