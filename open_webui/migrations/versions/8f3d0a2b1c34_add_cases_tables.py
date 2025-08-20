"""add cases tables

Revision ID: 8f3d0a2b1c34
Revises: 3781e22d8b01
Create Date: 2025-08-13 03:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from open_webui.migrations.util import get_existing_tables

# revision identifiers, used by Alembic.
revision: str = "8f3d0a2b1c34"
down_revision: Union[str, None] = "3781e22d8b01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = set(get_existing_tables())

    if "case" not in existing:
        op.create_table(
            "case",
            sa.Column("id", sa.Text(), primary_key=True, unique=True, nullable=False),
            sa.Column("user_id", sa.Text(), nullable=True),
            sa.Column("title", sa.Text(), nullable=True),
            sa.Column("query", sa.Text(), nullable=True),
            sa.Column("status", sa.Text(), nullable=True),
            sa.Column("vendor", sa.Text(), nullable=True),
            sa.Column("category", sa.Text(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=True),
            sa.Column("updated_at", sa.BigInteger(), nullable=True),
        )

    if "case_node" not in existing:
        op.create_table(
            "case_node",
            sa.Column("id", sa.Text(), primary_key=True, unique=True, nullable=False),
            sa.Column("case_id", sa.Text(), nullable=True),
            sa.Column("title", sa.Text(), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("node_type", sa.Text(), nullable=True),
            sa.Column("status", sa.Text(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=True),
        )

    if "case_edge" not in existing:
        op.create_table(
            "case_edge",
            sa.Column("id", sa.Text(), primary_key=True, unique=True, nullable=False),
            sa.Column("case_id", sa.Text(), nullable=True),
            sa.Column("source_node_id", sa.Text(), nullable=True),
            sa.Column("target_node_id", sa.Text(), nullable=True),
            sa.Column("edge_type", sa.Text(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("case_edge")
    op.drop_table("case_node")
    op.drop_table("case")

