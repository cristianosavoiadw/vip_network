"""Symmetric encryption for credentials kept in our database (the WeOS token, later others).

Fernet (AES-128-CBC + HMAC). The key comes from ``VIP_FERNET_KEY`` (urlsafe base64,
32 bytes); when it is empty a key is derived from ``VIP_JWT_SECRET`` so dev works out of the
box. Changing either makes stored secrets unreadable: set them once per environment. Never log
the plaintext.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class DecryptError(Exception):
    pass


def _fernet() -> Fernet:
    s = get_settings()
    key = s.fernet_key.strip()
    if not key:
        key = base64.urlsafe_b64encode(hashlib.sha256(s.jwt_secret.encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise DecryptError("credential cannot be decrypted with the current key") from exc


def hint(secret: str) -> str:
    """Last 4 characters, enough for the UI to say "…a3f9" without revealing anything."""
    s = secret.strip()
    return s[-4:] if len(s) >= 12 else ""
