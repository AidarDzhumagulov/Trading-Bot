from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fa0666849e2c'
down_revision: Union[str, Sequence[str], None] = 'dddfa1998799'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('dca_cycles', sa.Column('initial_first_order_price', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('dca_cycles', 'initial_first_order_price')
