"""v4 PR#1: add 5 nullable columns to conversations for rejection re-engagement.

All NULLABLE, no server_default — keeps the migration instant on Postgres
even with large `conversations` tables (no full-table rewrite).

Revision ID: 20260503_v4_rejection_columns
Revises: 20260503_client_enrichment
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa


revision = '20260503_v4_rejection_columns'
down_revision = '20260503_client_enrichment'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('conversations', sa.Column('rejection_normalized_category', sa.String(50), nullable=True))
    op.add_column('conversations', sa.Column('rejection_classification_confidence', sa.Float(), nullable=True))
    op.add_column('conversations', sa.Column('rejection_classified_at', sa.DateTime(), nullable=True))
    op.add_column('conversations', sa.Column('reactivation_attempts', sa.Integer(), nullable=True))
    op.add_column('conversations', sa.Column('last_reactivation_at', sa.DateTime(), nullable=True))
    op.create_index('ix_conversations_rejection_normalized', 'conversations', ['rejection_normalized_category'])


def downgrade() -> None:
    op.drop_index('ix_conversations_rejection_normalized', table_name='conversations')
    op.drop_column('conversations', 'last_reactivation_at')
    op.drop_column('conversations', 'reactivation_attempts')
    op.drop_column('conversations', 'rejection_classified_at')
    op.drop_column('conversations', 'rejection_classification_confidence')
    op.drop_column('conversations', 'rejection_normalized_category')
