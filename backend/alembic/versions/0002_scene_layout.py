"""layout de cena e destaques

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scenes", sa.Column("layout", sa.String(length=20), nullable=False, server_default="auto"))
    op.add_column("scenes", sa.Column("bullets", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("scenes", "bullets")
    op.drop_column("scenes", "layout")
