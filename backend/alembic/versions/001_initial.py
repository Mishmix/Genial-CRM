"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2025-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Clients table
    op.create_table(
        'clients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_user_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('first_name', sa.String(255), nullable=False),
        sa.Column('last_name', sa.String(255), nullable=True),
        sa.Column('language_code', sa.String(10), nullable=True),
        sa.Column('avatar_file_id', sa.String(255), nullable=True),
        sa.Column('avatar_local_path', sa.String(512), nullable=True),
        sa.Column('business_connection_id', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='new'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('source', sa.String(100), server_default='telegram-business'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('last_auto_reply_at', sa.DateTime(), nullable=True),
        sa.Column('unread_count', sa.Integer(), server_default='0'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_clients_id', 'clients', ['id'])
    op.create_index('ix_clients_telegram_user_id', 'clients', ['telegram_user_id'], unique=True)
    op.create_index('ix_clients_username', 'clients', ['username'])
    op.create_index('ix_clients_status', 'clients', ['status'])
    op.create_index('ix_clients_last_message', 'clients', ['last_message_at'])

    # Messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('telegram_message_id', sa.Integer(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_messages_id', 'messages', ['id'])
    op.create_index('ix_messages_client_sent', 'messages', ['client_id', 'sent_at'])

    # Tags table
    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('color', sa.String(20), server_default='#3b82f6'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_tags_id', 'tags', ['id'])

    # Client-Tags association
    op.create_table(
        'client_tags',
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('client_id', 'tag_id'),
    )

    # Templates table
    op.create_table(
        'templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('language', sa.String(10), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_auto_reply', sa.Boolean(), server_default='0'),
        sa.Column('is_active', sa.Boolean(), server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_templates_id', 'templates', ['id'])
    op.create_index('ix_templates_lang_active', 'templates', ['language', 'is_active'])

    # Settings table
    op.create_table(
        'settings',
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('key'),
    )

    # Admins table
    op.create_table(
        'admins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_user_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('role', sa.String(50), server_default='admin'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_admins_id', 'admins', ['id'])
    op.create_index('ix_admins_telegram_user_id', 'admins', ['telegram_user_id'], unique=True)

    # Sessions table
    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(255), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=True),
        sa.Column('telegram_user_id', sa.Integer(), nullable=True),
        sa.Column('auth_type', sa.String(50), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['admins.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sessions_id', 'sessions', ['id'])
    op.create_index('ix_sessions_session_id', 'sessions', ['session_id'], unique=True)


def downgrade() -> None:
    op.drop_table('sessions')
    op.drop_table('admins')
    op.drop_table('settings')
    op.drop_table('templates')
    op.drop_table('client_tags')
    op.drop_table('tags')
    op.drop_table('messages')
    op.drop_table('clients')
