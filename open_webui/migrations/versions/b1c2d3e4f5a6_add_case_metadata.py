"""add case.metadata json column

Revision ID: b1c2d3e4f5a6
Revises: 8f3d0a2b1c34
Create Date: 2025-08-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "f1e2d3c4b5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    try:
        op.add_column("case", sa.Column("metadata", sa.JSON(), nullable=True))
    except Exception:
        # 若已存在则忽略
        pass


def downgrade() -> None:
    try:
        op.drop_column("case", "metadata")
    except Exception:
        pass
