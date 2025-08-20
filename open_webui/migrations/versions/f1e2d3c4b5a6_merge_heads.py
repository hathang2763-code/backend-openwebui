"""merge multiple heads into single head

Revision ID: f1e2d3c4b5a6
Revises: 8f3d0a2b1c34, d31026856c01
Create Date: 2025-08-18 00:00:00.000000

"""

from typing import Sequence, Union

# Alembic imports are optional here since this is a no-op merge
# from alembic import op
# import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, tuple[str, str], None] = ("8f3d0a2b1c34", "d31026856c01")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This is a merge migration; no schema changes required.
    pass


def downgrade() -> None:
    # This is a merge migration; nothing to downgrade.
    pass

