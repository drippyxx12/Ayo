"""Zero-dollar bounded Gemini budgets and report-scoped conversations.

Revision ID: 0008_merchant_analysis
Revises: 0007_assistant
"""
from alembic import op
import sqlalchemy as sa

revision = '0008_merchant_analysis'
down_revision = '0007_assistant'
branch_labels = None
depends_on = None


def _limits(free):
    with op.batch_alter_table('provider_budget_accounts') as batch:
        batch.drop_constraint('ck_budget_account_limits', type_='check')
        batch.create_check_constraint('ck_budget_account_limits',
            'limit_microusd >= 0 AND call_limit > 0' if free else 'limit_microusd > 0 AND call_limit > 0')
    with op.batch_alter_table('provider_usage_reservations') as batch:
        batch.drop_constraint('ck_provider_usage_reservation', type_='check')
        batch.create_check_constraint('ck_provider_usage_reservation',
            'reserved_microusd >= 0' if free else 'reserved_microusd > 0')


def upgrade():
    _limits(True)
    # Never rebuild the populated conversation parent on SQLite: child-message
    # CASCADEs would otherwise erase existing conversations' evidence.
    if op.get_bind().dialect.name == 'sqlite':
        op.execute('ALTER TABLE assistant_conversations ADD COLUMN source_report_id VARCHAR(64) REFERENCES research_reports(id)')
    else:
        op.add_column('assistant_conversations', sa.Column('source_report_id', sa.String(64), nullable=True))
        op.create_foreign_key('fk_assistant_source_report', 'assistant_conversations', 'research_reports',
                             ['source_report_id'], ['id'])


def downgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text('SELECT count(*) FROM provider_budget_accounts WHERE limit_microusd = 0')) or connection.scalar(
            sa.text('SELECT count(*) FROM provider_usage_reservations WHERE reserved_microusd = 0')):
        raise RuntimeError('Cannot downgrade while zero-cost budget evidence exists; preserve the ledger and review a backup.')
    if connection.dialect.name == 'sqlite':
        op.execute('ALTER TABLE assistant_conversations DROP COLUMN source_report_id')
    else:
        op.drop_constraint('fk_assistant_source_report', 'assistant_conversations', type_='foreignkey')
        op.drop_column('assistant_conversations', 'source_report_id')
    _limits(False)
