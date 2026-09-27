from collections.abc import Iterator

import pytest
from flask import Flask

from app.auth.passwords import verify_password
from app.auth.users import MIN_PASSWORD_LENGTH, UserError, create_user, find_user

GOOD_PASSWORD = "long-enough-password"


@pytest.fixture
def ctx(app: Flask) -> Iterator[None]:
    with app.app_context():
        yield


@pytest.mark.usefixtures("ctx")
def test_create_user_normalizes_username_and_hashes_password() -> None:
    user = create_user("  Alice ", GOOD_PASSWORD)

    assert user.username == "alice"
    assert user.password_hash != GOOD_PASSWORD
    assert verify_password(GOOD_PASSWORD, user.password_hash)


@pytest.mark.usefixtures("ctx")
@pytest.mark.parametrize("username", ["ab", "a" * 65, "bad name", "<script>", "имя"])
def test_create_user_rejects_invalid_username(username: str) -> None:
    with pytest.raises(UserError, match="Логин"):
        create_user(username, GOOD_PASSWORD)


@pytest.mark.usefixtures("ctx")
def test_create_user_rejects_short_password() -> None:
    with pytest.raises(UserError, match="Пароль"):
        create_user("alice", "x" * (MIN_PASSWORD_LENGTH - 1))


@pytest.mark.usefixtures("ctx")
def test_create_user_rejects_password_over_72_bytes() -> None:
    with pytest.raises(UserError, match="72"):
        create_user("alice", "я" * 40)


@pytest.mark.usefixtures("ctx")
def test_create_user_rejects_duplicate_case_insensitive() -> None:
    create_user("alice", GOOD_PASSWORD)

    with pytest.raises(UserError, match="уже существует"):
        create_user("ALICE", GOOD_PASSWORD)


@pytest.mark.usefixtures("ctx")
def test_find_user_is_case_insensitive() -> None:
    created = create_user("alice", GOOD_PASSWORD)

    assert find_user("Alice") is created
    assert find_user("nobody") is None
