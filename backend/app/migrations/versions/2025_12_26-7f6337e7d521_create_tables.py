from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f6337e7d521"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("users_pkey")),
        sa.UniqueConstraint("email", name=op.f("users_email_unique")),
    )
    op.create_table(
        "bot_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("binance_api_key", sa.String(length=255), nullable=False),
        sa.Column("binance_api_secret", sa.Text(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("total_budget", sa.Float(), nullable=False),
        sa.Column("grid_length_pct", sa.Float(), nullable=False),
        sa.Column("first_order_offset_pct", sa.Float(), nullable=False),
        sa.Column("safety_orders_count", sa.Integer(), nullable=False),
        sa.Column("volume_scale_pct", sa.Float(), nullable=False),
        sa.Column("grid_shift_threshold_pct", sa.Float(), nullable=False),
        sa.Column("take_profit_pct", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("bot_configs_user_id_foreign")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("bot_configs_pkey")),
    )
    op.create_table(
        "dca_cycles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("config_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status", sa.Enum("OPEN", "CLOSED", name="cyclestatus"), nullable=False
        ),
        sa.Column("total_base_qty", sa.Float(), nullable=False),
        sa.Column("total_quote_spent", sa.Float(), nullable=False),
        sa.Column("avg_price", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["config_id"], ["bot_configs.id"], name=op.f("dca_cycles_config_id_foreign")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("dca_cycles_pkey")),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cycle_id", sa.Uuid(), nullable=False),
        sa.Column("binance_order_id", sa.String(length=100), nullable=True),
        sa.Column("order_type", sa.String(length=20), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "FILLED", "CANCELED", "PARTIAL", name="orderstatus"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cycle_id"], ["dca_cycles.id"], name=op.f("orders_cycle_id_foreign")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("orders_pkey")),
        sa.UniqueConstraint(
            "binance_order_id", name=op.f("orders_binance_order_id_unique")
        ),
    )


def downgrade() -> None:
    op.drop_table("orders")
    op.drop_table("dca_cycles")
    op.drop_table("bot_configs")
    op.drop_table("users")
