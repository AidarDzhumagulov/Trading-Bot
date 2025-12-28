from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5119af54a31f'
down_revision: Union[str, Sequence[str], None] = '7f6337e7d521'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(op.f('bot_configs_user_id_foreign'), 'bot_configs', type_='foreignkey')
    op.drop_column('bot_configs', 'user_id')


def downgrade() -> None:
    op.add_column('bot_configs', sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False))
    op.create_foreign_key(op.f('bot_configs_user_id_foreign'), 'bot_configs', 'users', ['user_id'], ['id'])
