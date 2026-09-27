import pytest

from app.auth.passwords import (
    BCRYPT_ROUNDS,
    PasswordTooLongError,
    dummy_hash,
    hash_password,
    verify_password,
)


def test_hash_is_bcrypt_and_not_plaintext() -> None:
    password_hash = hash_password("s3cret-password")

    assert "s3cret-password" not in password_hash
    assert password_hash.startswith(f"$2b${BCRYPT_ROUNDS:02d}$")


def test_same_password_gives_different_hashes() -> None:
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_accepts_correct_and_rejects_wrong_password() -> None:
    password_hash = hash_password("correct-password")

    assert verify_password("correct-password", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_unicode_password_is_supported() -> None:
    password_hash = hash_password("пароль-с-кириллицей")

    assert verify_password("пароль-с-кириллицей", password_hash) is True


def test_password_longer_than_72_bytes_is_rejected() -> None:
    too_long = "a" * 73

    with pytest.raises(PasswordTooLongError):
        hash_password(too_long)
    assert verify_password(too_long, hash_password("a" * 72)) is False


def test_dummy_hash_is_valid_and_cached() -> None:
    assert dummy_hash() is dummy_hash()
    assert verify_password("anything", dummy_hash()) is False
