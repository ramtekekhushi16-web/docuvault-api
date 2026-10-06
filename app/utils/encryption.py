import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import ENCRYPTION_KEY


def _get_key() -> bytes:
    if not ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY is not configured")

    try:
        key = base64.urlsafe_b64decode(ENCRYPTION_KEY)
    except Exception as exc:
        raise RuntimeError("ENCRYPTION_KEY is not valid Base64") from exc

    if len(key) != 32:
        raise RuntimeError("ENCRYPTION_KEY must decode to exactly 32 bytes")

    return key


def encrypt_data(data: bytes) -> bytes:
    key = _get_key()

    aesgcm = AESGCM(key)

    nonce = os.urandom(12)

    encrypted_data = aesgcm.encrypt(
        nonce,
        data,
        None,
    )

    return nonce + encrypted_data


def decrypt_data(encrypted_data: bytes) -> bytes:
    key = _get_key()

    if len(encrypted_data) < 13:
        raise ValueError("Invalid encrypted data")

    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]

    aesgcm = AESGCM(key)

    return aesgcm.decrypt(
        nonce,
        ciphertext,
        None,
    )