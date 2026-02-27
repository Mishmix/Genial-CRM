"""add_category_to_templates

Revision ID: 7e9d4483ec88
Revises: a6fee3c6b384
Create Date: 2026-02-27 01:56:41.066323

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e9d4483ec88'
down_revision: Union[str, None] = 'a6fee3c6b384'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add category column
    op.add_column('templates', sa.Column('category', sa.String(length=50), nullable=True))
    
    # Set default category for existing auto-replies
    op.execute("UPDATE templates SET category = 'thumbnail' WHERE is_auto_reply = 1")


def downgrade() -> None:
    op.drop_column('templates', 'category')
