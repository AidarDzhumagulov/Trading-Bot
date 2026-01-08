from bcrypt import checkpw, hashpw, gensalt


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
