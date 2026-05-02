"""AI-Manager: voice transcription fields on messages + digests table

Revision ID: 20260503_ai_manager
Revises: 2b5c588b2743
Create Date: 2026-05-03

"""
from alembic import op
import sqlalchemy as sa


revision = '20260503_ai_manager'
down_revision = '2b5c588b2743'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('transcription', sa.Text(), nullable=True))
    op.add_column('messages', sa.Column('transcription_status', sa.String(20), nullable=True))

    op.create_table(
        'digests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('raw_response', sa.JSON(), nullable=True),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('delivery_message_id', sa.Integer(), nullable=True),
        sa.Column('routine_session_url', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_digests_type', 'digests', ['type'])
    op.create_index('ix_digests_created_at', 'digests', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_digests_created_at', table_name='digests')
    op.drop_index('ix_digests_type', table_name='digests')
    op.drop_table('digests')
    op.drop_column('messages', 'transcription_status')
    op.drop_column('messages', 'transcription')
