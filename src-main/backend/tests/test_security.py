import pytest

from app.core.security import hash_password, verify_password


def test_hash_password_creates_argon2id_hash() -> None:
    password_hash = hash_password("a-secure-password")

    assert password_hash != "a-secure-password"
    assert password_hash.startswith("$argon2id$")
    assert verify_password("a-secure-password", password_hash) is True


def test_hash_password_uses_unique_salts() -> None:
    first_hash = hash_password("same-password")
    second_hash = hash_password("same-password")

    assert first_hash != second_hash


def test_verify_password_rejects_wrong_password_and_invalid_hash() -> None:
    password_hash = hash_password("correct-password")

    assert verify_password("wrong-password", password_hash) is False
    assert verify_password("correct-password", "not-a-valid-hash") is False


def test_hash_password_rejects_empty_password() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        hash_password("")
