"""ClientEnrichment table for AI-Manager v3

Revision ID: 20260503_client_enrichment
Revises: 20260503_todoist_sync
Create Date: 2026-05-03

"""
from alembic import op
import sqlalchemy as sa


revision = '20260503_client_enrichment'
down_revision = '20260503_todoist_sync'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'client_enrichments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('niche', sa.String(50), nullable=True),
        sa.Column('channel_name', sa.String(255), nullable=True),
        sa.Column('channel_size_bucket', sa.String(20), nullable=True),
        sa.Column('temperature', sa.String(20), nullable=True),
        sa.Column('communication_style', sa.String(30), nullable=True),
        sa.Column('price_sensitivity', sa.String(20), nullable=True),
        sa.Column('decision_speed', sa.String(20), nullable=True),
        sa.Column('last_summary', sa.Text(), nullable=True),
        sa.Column('pain_points', sa.JSON(), nullable=True),
        sa.Column('value_drivers', sa.JSON(), nullable=True),
        sa.Column('next_best_action', sa.Text(), nullable=True),
        sa.Column('ai_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_client_enrichments_client_id', 'client_enrichments', ['client_id'])
    op.create_index('ix_client_enrichments_reviewed_at', 'client_enrichments', ['reviewed_at'])


def downgrade() -> None:
    op.drop_index('ix_client_enrichments_reviewed_at', table_name='client_enrichments')
    op.drop_index('ix_client_enrichments_client_id', table_name='client_enrichments')
    op.drop_table('client_enrichments')
