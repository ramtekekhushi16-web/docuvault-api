from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)


def test_password_hash_and_verify():
    password = "TestPassword123!"

    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("WrongPassword123!", password_hash)


def test_access_token():
    token = create_access_token(123)

    payload = decode_access_token(token)

    assert payload["sub"] == "123"
    assert payload["type"] == "access"


def test_refresh_token():
    token = create_refresh_token(123)

    payload = decode_refresh_token(token)

    assert payload["sub"] == "123"
    assert payload["type"] == "refresh"