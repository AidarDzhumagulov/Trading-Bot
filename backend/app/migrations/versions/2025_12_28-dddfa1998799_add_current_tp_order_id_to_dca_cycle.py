from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "dddfa1998799"
down_revision: Union[str, Sequence[str], None] = "5119af54a31f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dca_cycles", sa.Column("current_tp_order_id", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("dca_cycles", "current_tp_order_id")
