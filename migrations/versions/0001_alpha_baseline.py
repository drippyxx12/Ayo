"""Original alpha schema, unchanged except under migration management.

Revision ID: 0001_alpha
Revises: None
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_alpha'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(320), nullable=False),
        sa.Column('password_hash', sa.String(300), nullable=False),
        sa.Column('joined', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_table('shops',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('token_cipher', sa.Text(), nullable=False),
        sa.Column('refresh_cipher', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.Float(), nullable=True),
        sa.Column('refresh_expires_at', sa.Float(), nullable=True),
        sa.Column('linked_at', sa.Float(), nullable=True),
        sa.Column('granted_scopes', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain'))
    op.create_index('ix_shops_user_id', 'shops', ['user_id'], unique=True)
    op.create_table('snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('currency', sa.String(10), nullable=False),
        sa.Column('shop_name', sa.String(255), nullable=False),
        sa.Column('product_count', sa.Integer(), nullable=False),
        sa.Column('paid_order_count', sa.Integer(), nullable=False),
        sa.Column('paid_order_value_minor', sa.Integer(), nullable=False),
        sa.Column('paid_order_days', sa.Text(), nullable=False),
        sa.Column('products_json', sa.Text(), nullable=False),
        sa.Column('orders_limited', sa.Integer(), nullable=False),
        sa.Column('products_limited', sa.Integer(), nullable=False),
        sa.Column('synced_at', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_snapshots_user_id', 'snapshots', ['user_id'], unique=True)


def downgrade():
    op.drop_table('snapshots')
    op.drop_table('shops')
    op.drop_table('users')
