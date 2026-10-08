from app.utils.encryption import encrypt_data, decrypt_data


def test_encrypt_decrypt_roundtrip():
    original = b"DocuVault secret document content"

    encrypted = encrypt_data(original)

    assert encrypted != original
    assert len(encrypted) > len(original)

    decrypted = decrypt_data(encrypted)

    assert decrypted == original