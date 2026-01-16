from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.security import encrypt_api_key, decrypt_api_key


revision: str = "2f52d499789b"
down_revision: Union[str, Sequence[str], None] = "d3aec828f3c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_encrypted(value: str) -> bool:
    """Fernet tokens start with 'gAAAAA'"""
    return value.startswith("gAAAAA")


def upgrade() -> None:
    connection = op.get_bind()

    result = connection.execute(
        sa.text("SELECT id, binance_api_key, binance_api_secret FROM bot_configs")
    )
    rows = result.fetchall()

    for row in rows:
        config_id, api_key, api_secret = row

        if _is_encrypted(api_key) and _is_encrypted(api_secret):
            continue

        encrypted_key = (
            encrypt_api_key(api_key) if not _is_encrypted(api_key) else api_key
        )
        encrypted_secret = (
            encrypt_api_key(api_secret) if not _is_encrypted(api_secret) else api_secret
        )

        connection.execute(
            sa.text(
                "UPDATE bot_configs SET binance_api_key = :key, binance_api_secret = :secret WHERE id = :id"
            ),
            {"key": encrypted_key, "secret": encrypted_secret, "id": config_id},
        )


def downgrade() -> None:
    connection = op.get_bind()

    result = connection.execute(
        sa.text("SELECT id, binance_api_key, binance_api_secret FROM bot_configs")
    )
    rows = result.fetchall()

    for row in rows:
        config_id, api_key, api_secret = row

        if not _is_encrypted(api_key) and not _is_encrypted(api_secret):
            continue

        decrypted_key = decrypt_api_key(api_key) if _is_encrypted(api_key) else api_key
        decrypted_secret = (
            decrypt_api_key(api_secret) if _is_encrypted(api_secret) else api_secret
        )

        connection.execute(
            sa.text(
                "UPDATE bot_configs SET binance_api_key = :key, binance_api_secret = :secret WHERE id = :id"
            ),
            {"key": decrypted_key, "secret": decrypted_secret, "id": config_id},
        )
