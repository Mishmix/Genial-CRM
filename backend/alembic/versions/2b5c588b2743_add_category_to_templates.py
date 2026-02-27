"""add_category_to_templates

Revision ID: 2b5c588b2743
Revises: 7e9d4483ec88
Create Date: 2026-02-27 02:25:05.747478

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b5c588b2743'
down_revision: Union[str, None] = '7e9d4483ec88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add category column to templates
    op.add_column('templates', sa.Column('category', sa.String(50), nullable=True))
    
    # Set existing auto-reply templates to "thumbnail" category
    op.execute("UPDATE templates SET category = 'thumbnail' WHERE is_auto_reply = true")


def downgrade() -> None:
    op.drop_column('templates', 'category')
