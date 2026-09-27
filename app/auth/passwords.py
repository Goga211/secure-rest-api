"""Хэширование паролей bcrypt. Открытый пароль нигде не сохраняется."""

from functools import cache

import bcrypt

BCRYPT_ROUNDS = 12
# bcrypt учитывает только первые 72 байта пароля, более длинные отклоняем явно
BCRYPT_MAX_PASSWORD_BYTES = 72


class PasswordTooLongError(ValueError):
    """Пароль длиннее, чем может обработать bcrypt."""


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(
            f"Пароль не должен превышать {BCRYPT_MAX_PASSWORD_BYTES} байт в UTF-8"
        )
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, password_hash.encode("ascii"))


@cache
def dummy_hash() -> str:
    """Хэш-заглушка для входа несуществующего пользователя.

    Пароль проверяется всегда, поэтому по времени ответа нельзя понять,
    существует ли такой логин.
    """
    return hash_password("timing-equalizer-placeholder")
