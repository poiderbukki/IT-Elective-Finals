from __future__ import annotations

import bcrypt


class AuthError(ValueError):
    pass


def hash_password(plain_password: str) -> bytes:
    plain_password = (plain_password or "").strip()
    if len(plain_password) < 6:
        raise AuthError("Password must be at least 6 characters.")
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())


def verify_password(plain_password: str, password_hash: bytes) -> bool:
    try:
        return bcrypt.checkpw((plain_password or "").encode("utf-8"), password_hash)
    except Exception:
        return False

