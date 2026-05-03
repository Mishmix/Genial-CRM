"""Todoist Sync Manager: log table

Revision ID: 20260503_todoist_sync
Revises: 20260503_ai_manager
Create Date: 2026-05-03

"""
from alembic import op
import sqlalchemy as sa


revision = '20260503_todoist_sync'
down_revision = '20260503_ai_manager'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'todoist_sync_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('summary_md', sa.Text(), nullable=True),
        sa.Column('applied_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('failed_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('actions_json', sa.JSON(), nullable=True),
        sa.Column('routine_session_url', sa.String(512), nullable=True),
        sa.Column('telegram_message_id', sa.Integer(), nullable=True),
    )
    op.create_index('ix_todoist_sync_logs_started_at', 'todoist_sync_logs', ['started_at'])


def downgrade() -> None:
    op.drop_index('ix_todoist_sync_logs_started_at', table_name='todoist_sync_logs')
    op.drop_table('todoist_sync_logs')
