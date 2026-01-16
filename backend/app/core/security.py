import base64
from typing import Optional

from bcrypt import checkpw, hashpw, gensalt
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings
from app.core.logging import logger


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    pwd_bytes = password.encode("utf-8")
    salt = gensalt()
    hashed = hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password"""
    pwd_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return checkpw(pwd_bytes, hashed_bytes)


class EncryptionService:
    """
    Сервис для шифрования/дешифрования API ключей.
    Использует AES-256 через Fernet (симметричное шифрование).
    """

    def __init__(self):
        self._fernet: Optional[Fernet] = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization"""
        if self._initialized:
            return

        master_password = settings.ENCRYPTION_MASTER_KEY
        encryption_salt = settings.ENCRYPTION_SALT

        salt = encryption_salt.encode()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )

        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        self._fernet = Fernet(key)
        self._initialized = True

    def encrypt(self, plaintext: str) -> str:
        """
        Зашифровать строку (API key или secret)

        Args:
            plaintext: Открытый текст (API key)

        Returns:
            Зашифрованная строка (base64)
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty string")

        self._ensure_initialized()

        try:
            encrypted_bytes = self._fernet.encrypt(plaintext.encode())
            return encrypted_bytes.decode("utf-8")

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, encrypted: str) -> str:
        """
        Расшифровать строку

        Args:
            encrypted: Зашифрованная строка (base64)

        Returns:
            Открытый текст (API key)
        """
        if not encrypted:
            raise ValueError("Cannot decrypt empty string")

        self._ensure_initialized()

        try:
            decrypted_bytes = self._fernet.decrypt(encrypted.encode())
            return decrypted_bytes.decode("utf-8")

        except InvalidToken:
            logger.error("Decryption failed: Invalid token or corrupted data")
            raise ValueError("Failed to decrypt API key - invalid or corrupted")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise

_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Получить singleton instance сервиса шифрования"""
    global _encryption_service

    if _encryption_service is None:
        _encryption_service = EncryptionService()

    return _encryption_service


def encrypt_api_key(api_key: str) -> str:
    """Зашифровать API ключ"""
    return get_encryption_service().encrypt(api_key)


def decrypt_api_key(encrypted_key: str) -> str:
    """Расшифровать API ключ"""
    return get_encryption_service().decrypt(encrypted_key)
