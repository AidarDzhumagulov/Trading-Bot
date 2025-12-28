from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5d1be60109b9'
down_revision: Union[str, Sequence[str], None] = 'eaab20cb6495'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("COMMIT"))
    try:
        connection.execute(sa.text("ALTER TYPE orderstatus ADD VALUE 'ACTIVE'"))
    except Exception:
        pass
    connection.execute(sa.text("BEGIN"))


def downgrade() -> None:
    pass
