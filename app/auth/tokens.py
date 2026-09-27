"""Выпуск и проверка JWT, подписанных HMAC-SHA256."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "secure-rest-api"
REQUIRED_CLAIMS = ["sub", "iss", "iat", "exp"]


class TokenError(Exception):
    """Токен поддельный, просроченный или некорректный."""


@dataclass(frozen=True)
class IssuedToken:
    token: str
    expires_in: int


def issue_token(
    user_id: int, secret: str, ttl_minutes: int, now: datetime | None = None
) -> IssuedToken:
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iss": JWT_ISSUER,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=ttl_minutes),
    }
    token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    return IssuedToken(token=token, expires_in=ttl_minutes * 60)


def decode_token(token: str, secret: str) -> int:
    """Проверяет подпись, срок действия и издателя. Возвращает id пользователя.

    Список алгоритмов задан жёстко: токен с "alg": "none" или другим
    алгоритмом из заголовка не будет принят.
    """
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.InvalidTokenError as exc:
        raise TokenError("Недействительный токен") from exc

    try:
        return int(payload["sub"])
    except ValueError as exc:
        raise TokenError("Некорректный идентификатор пользователя в токене") from exc
