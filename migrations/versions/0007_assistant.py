"""Private conversations and bounded versioned read-tool receipts.

Revision ID: 0007_assistant
Revises: 0006_lead_crm
"""
from alembic import op
import sqlalchemy as sa

revision = '0007_assistant'
down_revision = '0006_lead_crm'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('assistant_conversations',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('business_id', sa.String(64), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('creation_key', sa.String(64), nullable=False),
        sa.Column('title', sa.String(160), nullable=False),
        sa.Column('active_request', sa.String(64)),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
        sa.UniqueConstraint('id', 'business_id', 'user_id', name='uq_assistant_conversation_scope'),
        sa.UniqueConstraint('business_id', 'user_id', 'creation_key', name='uq_assistant_conversation_creation'),
        sa.CheckConstraint('length(title) >= 1 AND length(title) <= 160', name='ck_assistant_title'))
    op.create_table('assistant_messages',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('conversation_id', sa.String(64), nullable=False),
        sa.Column('business_id', sa.String(64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('request_key', sa.String(64), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('plan_json', sa.Text(), nullable=False),
        sa.Column('result_json', sa.Text(), nullable=False),
        sa.Column('error_code', sa.String(80)),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('finished_at', sa.Float()),
        sa.ForeignKeyConstraint(['conversation_id', 'business_id', 'user_id'],
            ['assistant_conversations.id', 'assistant_conversations.business_id', 'assistant_conversations.user_id'],
            ondelete='CASCADE', name='fk_assistant_message_scope'),
        sa.UniqueConstraint('id', 'business_id', 'user_id', name='uq_assistant_message_scope'),
        sa.UniqueConstraint('conversation_id', 'request_key', 'role', name='uq_assistant_message_request'),
        sa.CheckConstraint("role IN ('user','assistant')", name='ck_assistant_message_role'),
        sa.CheckConstraint("status IN ('pending','completed','blocked','failed','uncertain')", name='ck_assistant_message_status'),
        sa.CheckConstraint('length(content) <= 1000', name='ck_assistant_message_content'))
    op.create_table('assistant_tool_runs',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('message_id', sa.String(64), nullable=False),
        sa.Column('business_id', sa.String(64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tool_name', sa.String(40), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('result_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['message_id', 'business_id', 'user_id'],
            ['assistant_messages.id', 'assistant_messages.business_id', 'assistant_messages.user_id'],
            ondelete='CASCADE', name='fk_assistant_tool_scope'),
        sa.UniqueConstraint('message_id', 'tool_name', name='uq_assistant_tool_message'),
        sa.CheckConstraint("tool_name IN ('business.profile','research.saved','opportunities.list','leads.saved','work.tasks')", name='ck_assistant_tool_name'),
        sa.CheckConstraint('version = 1', name='ck_assistant_tool_version'),
        sa.CheckConstraint("status IN ('completed','partial','empty')", name='ck_assistant_tool_status'))
    for table, columns in (
        ('assistant_conversations', ('business_id', 'user_id')),
        ('assistant_messages', ('conversation_id', 'business_id', 'user_id')),
        ('assistant_tool_runs', ('message_id', 'business_id', 'user_id')),
    ):
        for column in columns:
            op.create_index('ix_' + table + '_' + column, table, [column])


def downgrade():
    op.drop_table('assistant_tool_runs')
    op.drop_table('assistant_messages')
    op.drop_table('assistant_conversations')
