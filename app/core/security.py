import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_SECRET_KEY,
    JWT_SECRET_KEY,
    REFRESH_TOKEN_EXPIRE_DAYS,
)


ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")

    salt = bcrypt.gensalt()

    hashed = bcrypt.hashpw(
        password_bytes,
        salt,
    )

    return hashed.decode("utf-8")


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    password_bytes = password.encode("utf-8")
    hashed_bytes = password_hash.encode("utf-8")

    return bcrypt.checkpw(
        password_bytes,
        hashed_bytes,
    )


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=ALGORITHM,
    )


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )

    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        JWT_REFRESH_SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str):
    return jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[ALGORITHM],
    )


def decode_refresh_token(token: str):
    return jwt.decode(
        token,
        JWT_REFRESH_SECRET_KEY,
        algorithms=[ALGORITHM],
    )


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()