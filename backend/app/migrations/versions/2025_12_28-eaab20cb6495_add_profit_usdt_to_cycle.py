from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'eaab20cb6495'
down_revision: Union[str, Sequence[str], None] = 'fa0666849e2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('dca_cycles', sa.Column('profit_usdt', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('dca_cycles', 'profit_usdt')
