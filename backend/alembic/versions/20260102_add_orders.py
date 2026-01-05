"""Add orders and rejection_reasons tables

Revision ID: 20260102_orders
Revises: 
Create Date: 2026-01-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '20260102_orders'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create orders table
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('service_type', sa.String(50), nullable=False),
        sa.Column('quantity', sa.Integer(), default=1),
        sa.Column('amount', sa.Integer(), nullable=True),
        sa.Column('currency', sa.String(10), default='USD'),
        sa.Column('has_ab_test', sa.Boolean(), default=False),
        sa.Column('has_title', sa.Boolean(), default=False),
        sa.Column('has_urgency', sa.Boolean(), default=False),
        sa.Column('deadline_type', sa.String(20), nullable=True),
        sa.Column('deadline_date', sa.DateTime(), nullable=True),
        sa.Column('deadline_range', sa.String(50), nullable=True),
        sa.Column('deadline_custom', sa.String(255), nullable=True),
        sa.Column('deadline_calculated', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_orders_client', 'orders', ['client_id'])
    op.create_index('ix_orders_status', 'orders', ['status'])
    op.create_index('ix_orders_deadline', 'orders', ['deadline_calculated'])
    
    # Create rejection_reasons table
    op.create_table(
        'rejection_reasons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('emoji', sa.String(10), nullable=True),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )


def downgrade() -> None:
    op.drop_table('orders')
    op.drop_table('rejection_reasons')
